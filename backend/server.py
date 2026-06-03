"""SocialHub API — FastAPI + MongoDB."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from auth import (
    RegisterRequest, LoginRequest, UserPublic,
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    set_auth_cookies, clear_auth_cookies,
    get_current_user, check_login_lockout, record_failed_login, clear_failed_logins,
    new_user_doc, new_subscription_doc, new_wallet_doc,
    seed_admin, ensure_indexes,
)
import ai_agent
import broadcasts as broadcasts_mod
import chatwoot_client
import email_service
import evolution_client
import evolution_routing
import whatsapp_byok
import whatsapp_meta
import whatsapp_routing
import thawani  # noqa: F401  -- gated by env

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="SocialHub API", version="0.2.0")
api_router = APIRouter(prefix="/api")


# ============================
# Auth dependency wrappers (inject db)
# ============================
async def _current_user(request: Request) -> dict:
    return await get_current_user(request, db)


async def _current_admin(request: Request) -> dict:
    user = await get_current_user(request, db)
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def _user_public(doc: dict) -> dict:
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ============================
# Health / Root
# ============================
@api_router.get("/")
async def root():
    return {"service": "SocialHub API", "status": "ok", "version": "0.2.0"}


@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ============================
# Lead capture (marketing)
# ============================
class LeadCapture(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    source: str = "landing"
    plan_interest: Optional[str] = None
    locale: str = "ar"


@api_router.post("/leads", status_code=201)
async def capture_lead(lead: LeadCapture):
    doc = lead.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.leads.insert_one(doc)
    return {"id": doc["id"], "ok": True}


# ============================
# Auth endpoints
# ============================
@api_router.post("/auth/register", status_code=201)
async def register(payload: RegisterRequest, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user_doc = new_user_doc(payload.name.strip(), email, hash_password(payload.password), role="CLIENT")
    if payload.company_name:
        user_doc["company_name"] = payload.company_name.strip()
    await db.users.insert_one(user_doc)
    await db.subscriptions.insert_one(new_subscription_doc(user_doc["id"], plan_tier="GROWTH"))
    await db.wallets.insert_one(new_wallet_doc(user_doc["id"]))

    # Fire-and-forget Chatwoot provisioning (does not block registration)
    asyncio.create_task(_provision_chatwoot_async(user_doc["id"]))

    # Fire-and-forget welcome email (does not block registration)
    try:
        asyncio.create_task(email_service.send_welcome(
            to=email,
            name=user_doc["name"],
            lang="ar",
        ))
    except Exception as e:
        logger.warning("failed to schedule welcome email: %s", e)

    access = create_access_token(user_doc["id"], email, role="CLIENT")
    refresh = create_refresh_token(user_doc["id"])
    set_auth_cookies(response, access, refresh)

    return {**_user_public(dict(user_doc)), "access_token": access}


async def _provision_chatwoot_async(user_id: str) -> None:
    """Provision a Chatwoot account in the background. Idempotent."""
    try:
        user = await db.users.find_one({"id": user_id})
        if not user or user.get("chatwoot_account_id"):
            return
        result = await chatwoot_client.provision_for_user(user)
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "chatwoot_account_id": result["account_id"],
                "chatwoot_user_id": result["user_id"],
                "chatwoot_access_token": result.get("access_token"),
                "chatwoot_provisioning_error": None,
                "chatwoot_provisioned_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        logger.info("Chatwoot provisioned for user %s: account=%s", user_id, result["account_id"])
    except Exception as e:
        logger.exception("Chatwoot provisioning failed for user %s", user_id)
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"chatwoot_provisioning_error": str(e)[:500]}},
        )


@api_router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    email = payload.email.lower().strip()
    identifier = f"{_client_ip(request)}:{email}"
    await check_login_lockout(db, identifier)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await record_failed_login(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await clear_failed_logins(db, identifier)
    access = create_access_token(user["id"], user["email"], role=user["role"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {**_user_public(dict(user)), "access_token": access}


@api_router.post("/auth/logout")
async def logout(response: Response, _: dict = Depends(_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(_current_user)):
    return user


# ----- Password reset flow -----------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    lang: Optional[str] = "ar"


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@api_router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    """Always returns OK (no user enumeration). Sends a reset email if the
    address is registered. Token is opaque and stored hashed."""
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "name": 1, "email": 1})
    if user:
        import secrets as _secrets
        from hashlib import sha256

        raw_token = _secrets.token_urlsafe(32)
        token_hash = sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        await db.password_resets.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "token_hash": token_hash,
            "expires_at": expires_at.isoformat(),
            "used": False,
            "ip": _client_ip(request),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        frontend = os.environ.get("FRONTEND_URL", "https://app.letsm.io").rstrip("/")
        reset_url = f"{frontend}/auth/reset-password?token={raw_token}"
        try:
            await email_service.send_password_reset(
                to=email,
                name=user.get("name") or email.split("@")[0],
                reset_url=reset_url,
                lang=payload.lang or "ar",
            )
        except Exception as e:
            logger.exception("failed to send password reset email: %s", e)

    return {"ok": True, "message": "If the email is registered, a reset link has been sent."}


@api_router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    """Consumes a reset token and sets a new password (single-use)."""
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    from hashlib import sha256
    token_hash = sha256(payload.token.encode()).hexdigest()

    record = await db.password_resets.find_one({"token_hash": token_hash, "used": False}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=400, detail="invalid_or_used_token")

    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="expired_token")

    user = await db.users.find_one({"id": record["user_id"]})
    if not user:
        raise HTTPException(status_code=400, detail="user_not_found")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    await db.password_resets.update_one(
        {"token_hash": token_hash},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}},
    )

    return {"ok": True, "email": user["email"]}


# Promotional message pricing — Solution Partner economics (we pay Meta)
MESSAGE_PRICE_OMR = 0.025

# Top-up packages (msg count → OMR price)
TOPUP_PACKAGES = [
    {"id": "basic", "messages": 500, "price_omr": 12.5, "name_ar": "أساسية", "name_en": "Basic"},
    {"id": "pro", "messages": 2000, "price_omr": 50.0, "name_ar": "احترافية", "name_en": "Pro"},
    {"id": "enterprise", "messages": 5000, "price_omr": 125.0, "name_ar": "مؤسسات", "name_en": "Enterprise"},
]


@api_router.get("/wallet/packages")
async def list_packages():
    return {
        "packages": TOPUP_PACKAGES,
        "price_per_message_omr": MESSAGE_PRICE_OMR,
        "payment_gateway": "thawani" if thawani.is_configured() else "mock",
    }


@api_router.get("/me/wallet")
async def my_wallet(user: dict = Depends(_current_user)):
    wallet = await db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    if not wallet:
        wallet = new_wallet_doc(user["id"])
        await db.wallets.insert_one(wallet)
        wallet.pop("_id", None)
    txns = await db.wallet_transactions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(length=20)
    balance = float(wallet.get("balance_omr", 0))
    return {
        "wallet": wallet,
        "transactions": txns,
        "estimated_messages_remaining": int(balance / MESSAGE_PRICE_OMR) if balance > 0 else 0,
        "price_per_message_omr": MESSAGE_PRICE_OMR,
    }


class TopupRequest(BaseModel):
    package_id: str


@api_router.post("/me/wallet/topup")
async def topup_wallet(payload: TopupRequest, request: Request, user: dict = Depends(_current_user)):
    """
    If Thawani is configured: creates a Thawani Checkout Session and returns
    `payment_url` for the frontend to redirect to. Wallet is credited only after
    the `payment.succeeded` webhook arrives.
    Otherwise (mock mode): instantly credits the wallet.
    """
    pkg = next((p for p in TOPUP_PACKAGES if p["id"] == payload.package_id), None)
    if not pkg:
        raise HTTPException(status_code=400, detail="Unknown top-up package")
    now = datetime.now(timezone.utc).isoformat()

    # ---------- Real payment via Thawani ----------
    if thawani.is_configured():
        txn_id = str(uuid.uuid4())
        # Frontend origin (use request origin or fallback to default)
        origin = request.headers.get("origin") or os.environ.get("FRONTEND_ORIGIN", "https://app.letsm.io")
        try:
            session = await thawani.create_checkout_session(
                amount_omr=pkg["price_omr"],
                products=[{
                    "name": f"SocialHub {pkg['name_en']} - {pkg['messages']} messages",
                    "quantity": 1,
                    "unit_amount_omr": pkg["price_omr"],
                }],
                client_reference_id=txn_id,
                success_url=f"{origin}/dashboard/wallet?topup=success",
                cancel_url=f"{origin}/dashboard/wallet?topup=cancelled",
                metadata={
                    "user_id": user["id"],
                    "package_id": pkg["id"],
                    "txn_id": txn_id,
                },
            )
        except Exception as e:
            logger.exception("Thawani checkout creation failed for user %s", user["id"])
            raise HTTPException(status_code=502, detail=f"payment_gateway_error: {e}")

        # Record pending transaction
        txn = {
            "id": txn_id,
            "user_id": user["id"],
            "type": "TOPUP",
            "package_id": pkg["id"],
            "package_name": pkg["name_en"],
            "messages": pkg["messages"],
            "amount_omr": pkg["price_omr"],
            "status": "PENDING",
            "gateway": "thawani",
            "gateway_session_id": session.get("session_id"),
            "created_at": now,
        }
        await db.wallet_transactions.insert_one(dict(txn))
        return {
            "ok": True,
            "stub": False,
            "gateway": "thawani",
            "payment_url": thawani.build_payment_url(session["session_id"]),
            "session_id": session.get("session_id"),
            "transaction": txn,
        }

    # ---------- MOCK Stripe checkout — instantly credits the wallet ----------
    await db.wallets.update_one(
        {"user_id": user["id"]},
        {
            "$inc": {"balance_omr": pkg["price_omr"], "promotional_credits": pkg["messages"]},
            "$set": {"last_topup_at": now, "updated_at": now},
        },
        upsert=True,
    )
    # Record transaction
    txn = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "type": "TOPUP",
        "package_id": pkg["id"],
        "package_name": pkg["name_en"],
        "messages": pkg["messages"],
        "amount_omr": pkg["price_omr"],
        "status": "PAID",  # MOCK
        "gateway": "mock",
        "created_at": now,
    }
    await db.wallet_transactions.insert_one(dict(txn))
    wallet = await db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    balance = float(wallet.get("balance_omr", 0))
    return {
        "ok": True,
        "stub": True,
        "gateway": "mock",
        "wallet": wallet,
        "transaction": txn,
        "estimated_messages_remaining": int(balance / MESSAGE_PRICE_OMR),
    }


@api_router.post("/webhooks/thawani")
async def thawani_webhook(request: Request):
    """
    Thawani sends payment lifecycle events here. Events of interest:
      - checkout.completed → mark txn PAID and credit wallet
      - payment.succeeded  → ditto (for direct payments via PaymentIntent flow)
      - payment.failed     → mark txn FAILED
    Signature: HMAC-SHA256 of `body + '-' + timestamp` with webhook secret.
    """
    raw = await request.body()
    timestamp = request.headers.get("thawani-timestamp")
    signature = request.headers.get("thawani-signature")

    if thawani.is_configured() and thawani.get_config()["webhook_secret"]:
        if not thawani.verify_signature(raw, timestamp, signature):
            logger.warning("Thawani webhook signature mismatch")
            raise HTTPException(status_code=403, detail="invalid_signature")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    event_type = payload.get("event_type") or ""
    data = payload.get("data") or {}
    client_ref = data.get("client_reference_id") or data.get("checkout_invoice")
    session_id = data.get("session_id")
    now = datetime.now(timezone.utc).isoformat()

    # Persist raw event for audit
    await db.wallet_events.insert_one({
        "id": str(uuid.uuid4()),
        "received_at": now,
        "event_type": event_type,
        "session_id": session_id,
        "client_reference_id": client_ref,
        "raw": payload,
    })

    if event_type in ("checkout.completed", "payment.succeeded"):
        # Find the pending transaction
        txn = None
        if client_ref:
            txn = await db.wallet_transactions.find_one({"id": client_ref}, {"_id": 0})
        if not txn and session_id:
            txn = await db.wallet_transactions.find_one({"gateway_session_id": session_id}, {"_id": 0})
        if not txn:
            logger.warning("Thawani webhook: no matching txn for ref=%s session=%s", client_ref, session_id)
            return {"received": True, "matched": False}
        if txn.get("status") == "PAID":
            return {"received": True, "already_paid": True}

        # Credit the wallet
        await db.wallets.update_one(
            {"user_id": txn["user_id"]},
            {
                "$inc": {
                    "balance_omr": float(txn["amount_omr"]),
                    "promotional_credits": int(txn["messages"]),
                },
                "$set": {"last_topup_at": now, "updated_at": now},
            },
            upsert=True,
        )
        await db.wallet_transactions.update_one(
            {"id": txn["id"]},
            {"$set": {"status": "PAID", "paid_at": now}},
        )
        logger.info("Wallet credited via Thawani: user=%s amount=%s", txn["user_id"], txn["amount_omr"])
        return {"received": True, "matched": True, "credited": True}

    if event_type == "payment.failed":
        if client_ref:
            await db.wallet_transactions.update_one(
                {"id": client_ref},
                {"$set": {"status": "FAILED", "failed_at": now, "failure_reason": data.get("reason")}},
            )
        return {"received": True, "matched": True, "credited": False}

    return {"received": True}


@api_router.get("/payments/config")
async def payments_public_config():
    """Frontend can detect which payment provider is active."""
    return {
        "active_gateway": "thawani" if thawani.is_configured() else "mock",
        "thawani": thawani.public_config_for_frontend(),
        "currency": "OMR",
    }


# ----- /me/account: aggregated dashboard view -----
@api_router.get("/me/account")
async def my_account(user: dict = Depends(_current_user)):
    """Aggregated view used by the client dashboard: user + subscription + wallet + chatwoot link."""
    sub = await db.subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})
    wallet = await db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})

    # Compute trial countdown info
    trial = None
    if sub and sub.get("status") == "TRIALING" and sub.get("trial_ends_at"):
        try:
            ends_at = datetime.fromisoformat(sub["trial_ends_at"])
            now = datetime.now(timezone.utc)
            remaining = ends_at - now
            seconds = int(remaining.total_seconds())
            days = max(0, seconds // 86400)
            hours = max(0, (seconds % 86400) // 3600)
            trial = {
                "active": seconds > 0,
                "days_remaining": days,
                "hours_remaining": hours,
                "total_seconds_remaining": max(0, seconds),
                "trial_ends_at": sub["trial_ends_at"],
                "welcome_gift_messages": wallet.get("promotional_credits_initial", 0) if wallet else 0,
            }
        except Exception:
            trial = None

    return {
        "user": user,
        "subscription": sub,
        "wallet": wallet,
        "trial": trial,
        "chatwoot_url": os.environ.get("CHATWOOT_URL", ""),
        "chatwoot_account_id": user.get("chatwoot_account_id"),
        "chatwoot_provisioning_error": user.get("chatwoot_provisioning_error"),
    }


@api_router.post("/me/chatwoot/sso")
async def my_chatwoot_sso(user: dict = Depends(_current_user)):
    """Generate a fresh, one-time SSO login URL for the user's Chatwoot account."""
    cw_user_id = user.get("chatwoot_user_id")
    if not cw_user_id:
        # Try to provision now if missing
        asyncio.create_task(_provision_chatwoot_async(user["id"]))
        raise HTTPException(status_code=409, detail="Chatwoot account is still being provisioned. Try again in a few seconds.")
    try:
        sso_url = await chatwoot_client.get_sso_url(int(cw_user_id))
        return {"sso_url": sso_url}
    except Exception as e:
        logger.exception("SSO generation failed")
        raise HTTPException(status_code=502, detail=f"Failed to generate Chatwoot login URL: {e}")


@api_router.post("/admin/chatwoot/heal")
async def admin_chatwoot_heal(admin: dict = Depends(_current_admin)):
    """Retry Chatwoot provisioning for any client whose chatwoot_account_id is null."""
    pending = await db.users.find(
        {"role": "CLIENT", "chatwoot_account_id": None},
        {"_id": 0, "id": 1, "email": 1, "name": 1},
    ).to_list(length=1000)
    healed = 0
    errors = []
    for u in pending:
        try:
            await _provision_chatwoot_async(u["id"])
            fresh = await db.users.find_one({"id": u["id"]}, {"chatwoot_account_id": 1, "_id": 0})
            if fresh and fresh.get("chatwoot_account_id"):
                healed += 1
            else:
                errors.append({"id": u["id"], "email": u["email"]})
        except Exception as e:
            errors.append({"id": u["id"], "email": u["email"], "error": str(e)})
    return {"ok": True, "total_pending": len(pending), "healed": healed, "errors": errors}


# Plan catalog used by the billing page
PLAN_CATALOG = [
    {
        "tier": "GROWTH",
        "name_ar": "النمو",
        "name_en": "Growth",
        "price_omr": 35,
        "users": 3,
        "features_ar": ["٣ مستخدمين", "ربط واتساب + انستقرام + فيسبوك", "صندوق رسائل موحّد", "تقارير أساسية", "دعم فني بالعربية"],
        "features_en": ["3 users", "WhatsApp + Instagram + Facebook", "Unified inbox", "Basic reports", "Arabic support"],
    },
    {
        "tier": "PRO",
        "name_ar": "المحترف",
        "name_en": "Pro",
        "price_omr": 75,
        "users": 10,
        "features_ar": ["١٠ مستخدمين", "جميع القنوات + البريد الإلكتروني", "ردود تلقائية وقواعد ذكية", "تقارير متقدمة وتحليلات", "حملات رسائل ترويجية", "دعم أولوية ٢٤/٧"],
        "features_en": ["10 users", "All channels + Email", "Auto-replies & smart rules", "Advanced analytics", "Promotional campaigns", "Priority 24/7 support"],
    },
    {
        "tier": "ENTERPRISE",
        "name_ar": "المؤسسات",
        "name_en": "Enterprise",
        "price_omr": 150,
        "users": -1,  # unlimited
        "features_ar": ["مستخدمون غير محدودين", "روبوت ذكاء اصطناعي بالعربية", "تكامل CRM مخصّص", "API كامل ومخصص", "مدير حساب مخصّص", "اتفاقية مستوى خدمة SLA"],
        "features_en": ["Unlimited users", "Arabic-native AI bot", "Custom CRM integration", "Full custom API", "Dedicated account manager", "SLA agreement"],
    },
]


@api_router.get("/plans")
async def list_plans():
    return {"plans": PLAN_CATALOG}


class UpgradeRequest(BaseModel):
    target_tier: str  # GROWTH | PRO | ENTERPRISE


@api_router.post("/me/subscription/upgrade")
async def upgrade_subscription(payload: UpgradeRequest, user: dict = Depends(_current_user)):
    """Upgrade/downgrade the user's plan tier. Stripe flow is mocked — this just updates the tier."""
    tier = payload.target_tier.upper()
    if tier not in {"GROWTH", "PRO", "ENTERPRISE"}:
        raise HTTPException(status_code=400, detail="Invalid plan tier")
    plan = next((p for p in PLAN_CATALOG if p["tier"] == tier), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    update_doc = {
        "plan_tier": tier,
        "status": "ACTIVE",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.subscriptions.update_one({"user_id": user["id"]}, {"$set": update_doc})
    sub = await db.subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})
    return {"ok": True, "subscription": sub, "stripe_checkout_url": None, "stub": True}


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    import jwt
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(user["id"], user["email"], role=user["role"])
        response.set_cookie(
            key="access_token", value=access,
            httponly=True, secure=True, samesite="none",
            max_age=15 * 60, path="/",
        )
        return {"ok": True}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# ============================
# Admin endpoints
# ============================
PLAN_PRICE = {"GROWTH": 35.0, "PRO": 75.0, "ENTERPRISE": 150.0}


@api_router.get("/admin/overview")
async def admin_overview(admin: dict = Depends(_current_admin)):
    """KPIs for the super-admin overview page."""
    # MRR: sum of plan prices for ACTIVE subscriptions
    active_subs = await db.subscriptions.find({"status": "ACTIVE"}, {"_id": 0}).to_list(length=10000)
    trial_subs = await db.subscriptions.count_documents({"status": "TRIALING"})
    mrr = sum(PLAN_PRICE.get(s.get("plan_tier", "GROWTH"), 0.0) for s in active_subs)

    # Tier breakdown
    tier_counts = {"GROWTH": 0, "PRO": 0, "ENTERPRISE": 0}
    for s in active_subs:
        tier_counts[s.get("plan_tier", "GROWTH")] = tier_counts.get(s.get("plan_tier", "GROWTH"), 0) + 1

    # Wallet totals + messages
    wallets = await db.wallets.find({}, {"_id": 0, "balance_omr": 1, "total_promotional_messages_sent": 1}).to_list(length=10000)
    total_wallet = sum(float(w.get("balance_omr", 0) or 0) for w in wallets)
    total_messages = sum(int(w.get("total_promotional_messages_sent", 0) or 0) for w in wallets)

    total_clients = await db.users.count_documents({"role": "CLIENT"})

    return {
        "mrr_omr": round(mrr, 2),
        "active_subscribers": len(active_subs),
        "trialing_subscribers": trial_subs,
        "total_clients": total_clients,
        "total_promotional_messages_sent": total_messages,
        "total_wallet_balance_omr": round(total_wallet, 2),
        "tier_breakdown": tier_counts,
    }


@api_router.get("/admin/clients")
async def admin_list_clients(admin: dict = Depends(_current_admin)):
    """List all CLIENT users joined with their subscription + wallet + whatsapp channel."""
    users = await db.users.find({"role": "CLIENT"}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(length=10000)
    user_ids = [u["id"] for u in users]
    subs = {s["user_id"]: s async for s in db.subscriptions.find({"user_id": {"$in": user_ids}}, {"_id": 0})}
    wallets = {w["user_id"]: w async for w in db.wallets.find({"user_id": {"$in": user_ids}}, {"_id": 0})}
    channels = {c["user_id"]: c async for c in db.channels.find({"user_id": {"$in": user_ids}, "provider": "whatsapp"}, {"_id": 0, "access_token": 0})}

    rows = []
    for u in users:
        sub = subs.get(u["id"]) or {}
        wal = wallets.get(u["id"]) or {}
        ch = channels.get(u["id"]) or {}
        rows.append({
            "id": u["id"],
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "company_name": u.get("company_name"),
            "is_active": u.get("is_active", True),
            "chatwoot_account_id": u.get("chatwoot_account_id"),
            "plan_tier": sub.get("plan_tier", "—"),
            "status": sub.get("status", "—"),
            "current_period_end": sub.get("current_period_end"),
            "balance_omr": float(wal.get("balance_omr", 0) or 0),
            "promotional_credits": int(wal.get("promotional_credits", 0) or 0),
            "whatsapp_phone": ch.get("phone_number"),
            "whatsapp_waba_id": ch.get("waba_id"),
            "created_at": u.get("created_at"),
        })
    return {"clients": rows, "total": len(rows)}


class AdminCreditRequest(BaseModel):
    amount_omr: float
    note: Optional[str] = None


@api_router.post("/admin/clients/{client_id}/wallet/credit")
async def admin_credit_wallet(client_id: str, payload: AdminCreditRequest, admin: dict = Depends(_current_admin)):
    if payload.amount_omr == 0:
        raise HTTPException(status_code=400, detail="Amount must be non-zero")
    user = await db.users.find_one({"id": client_id})
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    now = datetime.now(timezone.utc).isoformat()
    # Adjust both balance and equivalent credits (positive or negative)
    credit_delta = int(payload.amount_omr / MESSAGE_PRICE_OMR)
    await db.wallets.update_one(
        {"user_id": client_id},
        {
            "$inc": {"balance_omr": payload.amount_omr, "promotional_credits": credit_delta},
            "$set": {"last_topup_at": now if payload.amount_omr > 0 else None, "updated_at": now},
        },
        upsert=True,
    )
    txn = {
        "id": str(uuid.uuid4()),
        "user_id": client_id,
        "type": "ADMIN_ADJUSTMENT",
        "package_id": "manual",
        "package_name": "Admin adjustment",
        "messages": credit_delta,
        "amount_omr": payload.amount_omr,
        "status": "POSTED",
        "note": payload.note,
        "admin_id": admin["id"],
        "created_at": now,
    }
    await db.wallet_transactions.insert_one(dict(txn))
    wallet = await db.wallets.find_one({"user_id": client_id}, {"_id": 0})
    return {"ok": True, "wallet": wallet, "transaction": txn}


class AdminStatusRequest(BaseModel):
    is_active: bool


class AdminRoleRequest(BaseModel):
    role: str  # "CLIENT" | "ADMIN"


@api_router.post("/admin/clients/{client_id}/role")
async def admin_set_role(client_id: str, payload: AdminRoleRequest, admin: dict = Depends(_current_admin)):
    role = (payload.role or "").upper().strip()
    if role not in ("CLIENT", "ADMIN"):
        raise HTTPException(status_code=422, detail="role must be CLIENT or ADMIN")
    user = await db.users.find_one({"id": client_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": client_id},
        {"$set": {"role": role, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "user_id": client_id, "role": role, "email": user.get("email")}


@api_router.post("/admin/chatwoot/downgrade-clients-to-agent")
async def admin_downgrade_chatwoot_clients(admin: dict = Depends(_current_admin)):
    """One-shot tool: every CLIENT user with a Chatwoot account is downgraded
    from administrator → agent so they can no longer create inboxes/integrations
    inside Chatwoot. WhatsApp & channel setup must go through SocialHub.

    Idempotent: re-running just re-asserts the agent role for everyone."""
    clients = await db.users.find(
        {"role": "CLIENT", "chatwoot_account_id": {"$ne": None}, "chatwoot_user_id": {"$ne": None}},
        {"_id": 0, "id": 1, "email": 1, "chatwoot_account_id": 1, "chatwoot_user_id": 1},
    ).to_list(length=10000)
    results = []
    for u in clients:
        try:
            await chatwoot_client.set_user_role(
                account_id=u["chatwoot_account_id"],
                user_id=u["chatwoot_user_id"],
                role="agent",
            )
            results.append({"email": u["email"], "ok": True})
        except Exception as e:
            results.append({"email": u["email"], "ok": False, "error": str(e)[:200]})
    return {"total": len(clients), "results": results}


@api_router.post("/admin/clients/{client_id}/status")
async def admin_set_status(client_id: str, payload: AdminStatusRequest, admin: dict = Depends(_current_admin)):
    user = await db.users.find_one({"id": client_id})
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.users.update_one(
        {"id": client_id},
        {"$set": {"is_active": payload.is_active, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    new_status = "ACTIVE" if payload.is_active else "CANCELED"
    await db.subscriptions.update_one(
        {"user_id": client_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "is_active": payload.is_active}


@api_router.get("/admin/billing/overview")
async def admin_billing_overview(admin: dict = Depends(_current_admin)):
    """Aggregated billing metrics for /admin/billing."""
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    active_subs = await db.subscriptions.find({"status": "ACTIVE"}, {"_id": 0}).to_list(length=10000)
    mrr = sum(PLAN_PRICE.get(s.get("plan_tier", "GROWTH"), 0.0) for s in active_subs)

    # Topup revenue
    all_topups = await db.wallet_transactions.find({"type": "TOPUP"}, {"_id": 0}).to_list(length=10000)
    this_month_topups = [t for t in all_topups if t.get("created_at", "") >= this_month_start]

    total_topup_revenue = sum(float(t.get("amount_omr", 0) or 0) for t in all_topups)
    mtd_topup_revenue = sum(float(t.get("amount_omr", 0) or 0) for t in this_month_topups)

    # ARPU
    total_clients = await db.users.count_documents({"role": "CLIENT"})
    arpu = (mrr / total_clients) if total_clients else 0

    # Recent stripe events
    stripe_events = await db.stripe_events.find({}, {"_id": 0}).sort("received_at", -1).limit(10).to_list(length=10)

    return {
        "mrr_omr": round(mrr, 2),
        "mtd_topup_revenue_omr": round(mtd_topup_revenue, 2),
        "ltv_topup_revenue_omr": round(total_topup_revenue, 2),
        "arpu_omr": round(arpu, 2),
        "active_subscribers": len(active_subs),
        "total_topup_count": len(all_topups),
        "stripe_events_recent": stripe_events,
    }


@api_router.get("/admin/transactions")
async def admin_transactions(admin: dict = Depends(_current_admin), limit: int = 100):
    """All wallet transactions across all clients, enriched with user info."""
    txns = await db.wallet_transactions.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)
    user_ids = list({t["user_id"] for t in txns})
    users = {u["id"]: u async for u in db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1})}
    for t in txns:
        u = users.get(t["user_id"]) or {}
        t["user_name"] = u.get("name", "—")
        t["user_email"] = u.get("email", "—")
    return {"transactions": txns, "total": len(txns)}


@api_router.get("/admin/quotas")
async def admin_quotas(admin: dict = Depends(_current_admin)):
    """Per-client messaging quotas: wallet + usage."""
    users = await db.users.find({"role": "CLIENT"}, {"_id": 0, "id": 1, "name": 1, "email": 1, "is_active": 1}).to_list(length=10000)
    uids = [u["id"] for u in users]
    wallets = {w["user_id"]: w async for w in db.wallets.find({"user_id": {"$in": uids}}, {"_id": 0})}
    subs = {s["user_id"]: s async for s in db.subscriptions.find({"user_id": {"$in": uids}}, {"_id": 0})}

    total_sent = 0
    total_credits = 0
    total_balance = 0.0
    rows = []
    for u in users:
        w = wallets.get(u["id"]) or {}
        s = subs.get(u["id"]) or {}
        sent = int(w.get("total_promotional_messages_sent", 0) or 0)
        credits = int(w.get("promotional_credits", 0) or 0)
        balance = float(w.get("balance_omr", 0) or 0)
        total_sent += sent
        total_credits += credits
        total_balance += balance
        rows.append({
            "user_id": u["id"],
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "is_active": u.get("is_active", True),
            "plan_tier": s.get("plan_tier", "—"),
            "balance_omr": balance,
            "promotional_credits": credits,
            "total_promotional_messages_sent": sent,
            "last_topup_at": w.get("last_topup_at"),
        })
    return {
        "rows": rows,
        "summary": {
            "total_messages_sent": total_sent,
            "total_credits_remaining": total_credits,
            "total_balance_omr": round(total_balance, 2),
            "avg_credits_per_client": int(total_credits / len(rows)) if rows else 0,
            "client_count": len(rows),
        },
    }


class BulkGrantRequest(BaseModel):
    credits_per_client: int = 0
    omr_per_client: float = 0.0
    note: Optional[str] = "Bulk admin grant"


@api_router.post("/admin/quotas/bulk-grant")
async def admin_bulk_grant(payload: BulkGrantRequest, admin: dict = Depends(_current_admin)):
    """Grant the same credits/OMR to every active client (promo campaign)."""
    if payload.credits_per_client == 0 and payload.omr_per_client == 0:
        raise HTTPException(status_code=400, detail="Provide credits_per_client or omr_per_client")
    clients = await db.users.find({"role": "CLIENT", "is_active": True}, {"_id": 0, "id": 1}).to_list(length=10000)
    now = datetime.now(timezone.utc).isoformat()
    granted = 0
    for c in clients:
        await db.wallets.update_one(
            {"user_id": c["id"]},
            {
                "$inc": {
                    "balance_omr": payload.omr_per_client,
                    "promotional_credits": payload.credits_per_client,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
        await db.wallet_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": c["id"],
            "type": "ADMIN_BULK_GRANT",
            "package_id": "bulk",
            "package_name": "Bulk grant",
            "messages": payload.credits_per_client,
            "amount_omr": payload.omr_per_client,
            "status": "POSTED",
            "note": payload.note,
            "admin_id": admin["id"],
            "created_at": now,
        })
        granted += 1
    return {"ok": True, "granted_to": granted}


# ============================
# Channels (WhatsApp Embedded Signup)
# ============================
class WhatsAppConnectRequest(BaseModel):
    waba_id: str
    phone_number: str
    phone_number_id: Optional[str] = None
    business_id: Optional[str] = None
    display_name: Optional[str] = None
    access_token: Optional[str] = None  # received from FB SDK exchange (stored encrypted in prod)


@api_router.get("/me/channels")
async def list_my_channels(user: dict = Depends(_current_user)):
    """Return the user's connected messaging channels."""
    channels = await db.channels.find({"user_id": user["id"]}, {"_id": 0, "access_token": 0}).to_list(length=50)
    return {"channels": channels}


@api_router.post("/me/channels/whatsapp", status_code=201)
async def connect_whatsapp(payload: WhatsAppConnectRequest, user: dict = Depends(_current_user)):
    """
    Persist a WhatsApp Business Account connection made via Facebook Embedded Signup.
    In production, this also pushes the inbox into Chatwoot via the platform API.
    """
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "provider": "whatsapp",
        "status": "CONNECTED",
        "waba_id": payload.waba_id,
        "phone_number": payload.phone_number,
        "phone_number_id": payload.phone_number_id,
        "business_id": payload.business_id,
        "display_name": payload.display_name or payload.phone_number,
        "connected_at": now,
        "updated_at": now,
    }
    # Upsert: one WhatsApp channel per user for MVP
    await db.channels.update_one(
        {"user_id": user["id"], "provider": "whatsapp"},
        {"$set": doc},
        upsert=True,
    )
    saved = await db.channels.find_one({"user_id": user["id"], "provider": "whatsapp"}, {"_id": 0, "access_token": 0})
    return {"ok": True, "channel": saved}


@api_router.delete("/me/channels/whatsapp")
async def disconnect_whatsapp(user: dict = Depends(_current_user)):
    await db.channels.delete_one({"user_id": user["id"], "provider": "whatsapp"})
    # Reset demo-seed flag so next connect re-seeds (only matters if user re-connects demo)
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"chatwoot_demo_seeded": ""}},
    )
    return {"ok": True}


@api_router.post("/me/channels/whatsapp/demo/simulate")
async def whatsapp_demo_simulate(user: dict = Depends(_current_user)):
    """
    Simulates a brand-new incoming WhatsApp message into the user's demo Chatwoot inbox.
    Only works for users with an active demo channel + seeded inbox.
    """
    channel = await db.channels.find_one(
        {"user_id": user["id"], "provider": "whatsapp", "is_demo": True},
        {"_id": 0},
    )
    if not channel:
        raise HTTPException(status_code=400, detail="no_demo_channel")

    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    inbox_id = fresh.get("chatwoot_demo_inbox_id")
    cw_account_id = fresh.get("chatwoot_account_id")
    cw_token = fresh.get("chatwoot_access_token")
    if not (inbox_id and cw_account_id and cw_token):
        raise HTTPException(status_code=400, detail="demo_inbox_missing")

    result = await chatwoot_client.simulate_incoming_message(
        account_id=cw_account_id, user_token=cw_token, inbox_id=inbox_id,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "simulate_failed"))
    return result


# ============================
# WhatsApp Meta Tech Provider — real integration (gated by env)
# ============================
class WhatsAppEmbeddedSignupRequest(BaseModel):
    """Payload from frontend after FB.login(config_id, response_type=code) succeeds."""
    waba_id: str
    phone_number_id: str
    business_id: Optional[str] = None
    code: Optional[str] = None        # OAuth code from FB.login
    pin: Optional[str] = "000000"     # 2FA PIN to set on the number


@api_router.get("/whatsapp/config")
async def whatsapp_public_config():
    """Expose only safe Meta config to the frontend (app_id + config_id + enabled flag)."""
    return whatsapp_meta.public_config_for_frontend()


@api_router.post("/whatsapp/connect", status_code=201)
async def whatsapp_connect(payload: WhatsAppEmbeddedSignupRequest, user: dict = Depends(_current_user)):
    """
    Real Tech-Provider provisioning flow.
    Called by the frontend AFTER Meta's Embedded Signup popup returns
    {waba_id, phone_number_id, business_id, code}.

    If META env vars are not set, we accept the payload and persist a mock-style
    channel (same shape as /me/channels/whatsapp) so the UI stays functional.
    """
    now = datetime.now(timezone.utc).isoformat()

    if whatsapp_meta.is_configured():
        try:
            prov = await whatsapp_meta.provision_whatsapp(
                auth_code=payload.code,
                waba_id=payload.waba_id,
                phone_number_id=payload.phone_number_id,
                business_id=payload.business_id,
                pin=payload.pin or "000000",
            )
        except Exception as e:
            logger.exception("WhatsApp provisioning failed for user %s", user.get("id"))
            raise HTTPException(status_code=502, detail=f"meta_provisioning_failed: {e}")

        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "provider": "whatsapp",
            "status": "CONNECTED",
            "waba_id": prov["waba_id"],
            "phone_number_id": prov["phone_number_id"],
            "business_id": prov.get("business_id"),
            "phone_number": prov.get("display_phone_number") or "—",
            "display_name": prov.get("verified_name") or "—",
            "quality_rating": prov.get("quality_rating"),
            "provisioned_via": "meta_tech_provider",
            "connected_at": now,
            "updated_at": now,
        }
    else:
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "provider": "whatsapp",
            "status": "CONNECTED",
            "waba_id": payload.waba_id,
            "phone_number_id": payload.phone_number_id,
            "business_id": payload.business_id,
            "phone_number": "+968 9999 8888",
            "display_name": (user.get("company_name") or "Demo Store") + " (Demo)",
            "is_demo": True,
            "provisioned_via": "demo",
            "connected_at": now,
            "updated_at": now,
        }

        # Seed demo conversations into the user's Chatwoot workspace (best-effort, async)
        cw_account_id = user.get("chatwoot_account_id")
        cw_token = user.get("chatwoot_access_token")
        if cw_account_id and cw_token and not user.get("chatwoot_demo_seeded"):
            try:
                seed = await chatwoot_client.seed_demo_conversations(
                    account_id=cw_account_id,
                    user_token=cw_token,
                    lang="ar",
                )
                if seed.get("ok"):
                    await db.users.update_one(
                        {"id": user["id"]},
                        {"$set": {
                            "chatwoot_demo_seeded": True,
                            "chatwoot_demo_inbox_id": seed.get("inbox_id"),
                        }},
                    )
                    doc["demo_inbox_id"] = seed.get("inbox_id")
                    logger.info("Demo conversations seeded for user %s", user["id"])
            except Exception as e:
                logger.warning("Demo seed failed (non-fatal) for user %s: %s", user["id"], e)

    await db.channels.update_one(
        {"user_id": user["id"], "provider": "whatsapp"},
        {"$set": doc},
        upsert=True,
    )
    saved = await db.channels.find_one(
        {"user_id": user["id"], "provider": "whatsapp"},
        {"_id": 0, "access_token": 0},
    )
    return {"ok": True, "channel": saved}


# ----- Webhook (Meta → SocialHub) -----
@api_router.get("/webhooks/whatsapp")
async def whatsapp_webhook_verify(request: Request):
    """GET handshake — echoes hub.challenge (plain text) when hub.verify_token matches."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge") or ""
    expected = whatsapp_meta.get_config()["verify_token"]
    if mode == "subscribe" and token and expected and token == expected:
        return PlainTextResponse(challenge, status_code=200)
    raise HTTPException(status_code=403, detail="verify_token_mismatch")


@api_router.post("/webhooks/whatsapp")
async def whatsapp_webhook_event(request: Request):
    """POST events from Meta. Verifies signature, then routes incoming text
    messages into the appropriate Chatwoot inbox."""
    raw = await request.body()
    sig = request.headers.get("x-hub-signature-256")

    if whatsapp_meta.is_configured() and not whatsapp_meta.verify_signature(raw, sig):
        logger.warning("webhook signature verification failed")
        raise HTTPException(status_code=403, detail="invalid_signature")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Persist raw event for audit/replay
    event_doc = {
        "id": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "object": payload.get("object"),
        "entry_count": len(payload.get("entry", []) or []),
        "raw": payload,
        "routing": [],
    }

    # Route any incoming text messages to Chatwoot
    try:
        messages = whatsapp_routing.extract_incoming_messages(payload)
        for m in messages:
            pn_id = m["phone_number_id"]
            route = await whatsapp_routing.find_route_for_pn(db, pn_id)
            if not route:
                logger.warning("no whatsapp_route for phone_number_id=%s — message dropped", pn_id)
                event_doc["routing"].append({"wa_id": m["wa_id"], "status": "no_route"})
                continue
            try:
                result = await whatsapp_routing.append_incoming_message(
                    db,
                    route=route,
                    wa_id=m["wa_id"],
                    name=m["name"],
                    text=m["text"],
                    meta_message_id=m.get("message_id"),
                )
                event_doc["routing"].append({"wa_id": m["wa_id"], "status": "ok", **result})
            except Exception as e:
                logger.exception("failed to route message into chatwoot: %s", e)
                event_doc["routing"].append({"wa_id": m["wa_id"], "status": "error", "error": str(e)})
    except Exception as e:
        logger.exception("webhook routing failed: %s", e)

    await db.whatsapp_events.insert_one(event_doc)
    return {"received": True, "routed": len(event_doc["routing"])}


@api_router.post("/webhooks/chatwoot")
async def chatwoot_webhook(request: Request):
    """
    Outgoing pipeline: Chatwoot agent reply → Meta WhatsApp.

    Chatwoot fires a webhook on every event in the API inbox we created.
    We only act on `message_created` events with message_type=outgoing
    that originate from a known WhatsApp conversation.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    event = payload.get("event") or payload.get("message_type")
    if event != "message_created":
        return {"ignored": True, "reason": "not_message_created", "event": event}

    # In Chatwoot's webhook for message_created, fields are flat
    if payload.get("message_type") != "outgoing":
        return {"ignored": True, "reason": "not_outgoing"}
    if payload.get("private"):
        return {"ignored": True, "reason": "private_note"}

    content = payload.get("content") or ""
    if not content.strip():
        return {"ignored": True, "reason": "empty_content"}

    conversation = payload.get("conversation") or {}
    conversation_id = conversation.get("id") or payload.get("conversation_id")
    if not conversation_id:
        return {"ignored": True, "reason": "no_conversation_id"}

    contact_map = await db.whatsapp_contacts.find_one({"conversation_id": conversation_id}, {"_id": 0})
    if not contact_map:
        # Try Evolution (QR) route before giving up
        evo_result = await evolution_routing.send_via_chatwoot_outgoing(
            db, conversation_id=conversation_id, content=content,
        )
        if evo_result.get("sent"):
            logger.info(
                "Evolution outgoing sent: convo=%s result=%s",
                conversation_id, str(evo_result)[:200],
            )
            return {"sent": True, "via": "evolution", **evo_result}
        if evo_result.get("reason") != "not_evolution_route":
            logger.warning("Evolution send failed: %s", evo_result)
        return {"ignored": True, "reason": "no_whatsapp_contact_for_conversation"}

    wa_id = contact_map["wa_id"]
    pn_id = contact_map["phone_number_id"]

    try:
        send_result = await whatsapp_meta.send_text_message(pn_id, wa_id, content)
        logger.info("WhatsApp outgoing sent: wa_id=%s convo=%s id=%s", wa_id, conversation_id, send_result)
        return {"sent": True, "wa_id": wa_id, "result": send_result}
    except Exception as e:
        logger.exception("Failed to send outgoing WhatsApp message: %s", e)
        raise HTTPException(status_code=502, detail=f"meta_send_failed: {e}")


# ============================
# Admin: WhatsApp setup
# ============================
@api_router.post("/admin/whatsapp/setup-routing")
async def admin_setup_whatsapp_routing(payload: dict | None = None, user: dict = Depends(_current_admin)):
    """
    One-time setup: create the WhatsApp API inbox inside the admin's Chatwoot
    and register the route. Body is optional — if omitted, the route is bound
    to the current authenticated user.

    If the owner has no Chatwoot account yet, we provision one first.
    """
    owner_user_id = (payload or {}).get("owner_user_id") or user.get("id")
    owner = await db.users.find_one({"id": owner_user_id}, {"_id": 0})
    if not owner:
        raise HTTPException(status_code=404, detail="owner_user_not_found")

    # Auto-provision Chatwoot if missing (covers seeded admin who never went through registration)
    if not owner.get("chatwoot_account_id"):
        try:
            await _provision_chatwoot_async(owner_user_id)
            owner = await db.users.find_one({"id": owner_user_id}, {"_id": 0})
        except Exception as e:
            logger.exception("auto-provision failed for owner")
            raise HTTPException(status_code=500, detail=f"chatwoot_provision_failed: {e}")
        if not owner or not owner.get("chatwoot_account_id"):
            raise HTTPException(status_code=500, detail="provisioning_did_not_complete")

    # Backfill: if user was provisioned in a legacy run without storing access_token,
    # recover it from Chatwoot Platform API now.
    if owner.get("chatwoot_account_id") and not owner.get("chatwoot_access_token"):
        cw_user_id = owner.get("chatwoot_user_id")
        if cw_user_id:
            try:
                cw_user = await chatwoot_client.get_user(cw_user_id)
                token = cw_user.get("access_token")
                if token:
                    await db.users.update_one(
                        {"id": owner_user_id},
                        {"$set": {"chatwoot_access_token": token}},
                    )
                    owner["chatwoot_access_token"] = token
                    logger.info("Backfilled chatwoot_access_token for user %s", owner_user_id)
            except Exception as e:
                logger.exception("Failed to backfill chatwoot_access_token: %s", e)

    try:
        route = await whatsapp_routing.ensure_route(db, owner_user_doc=owner)
    except Exception as e:
        logger.exception("ensure_route failed")
        raise HTTPException(status_code=500, detail=f"ensure_route_failed: {e}")

    return {
        "route": {
            "phone_number_id": route["phone_number_id"],
            "display_phone_number": route.get("display_phone_number"),
            "chatwoot_account_id": route["chatwoot_account_id"],
            "chatwoot_inbox_id": route["chatwoot_inbox_id"],
            "inbox_identifier": route["inbox_identifier"],
            "owner_user_id": route["user_id"],
        }
    }


@api_router.get("/admin/whatsapp/route")
async def admin_get_whatsapp_route(user: dict = Depends(_current_admin)):
    """Returns the active WhatsApp route, if any."""
    cfg = whatsapp_meta.get_config()
    pn_id = cfg.get("phone_number_id")
    if not pn_id:
        return {"configured": False, "reason": "WHATSAPP_PHONE_NUMBER_ID not set"}
    route = await whatsapp_routing.find_route_for_pn(db, pn_id)
    if not route:
        return {"configured": True, "routed": False, "phone_number_id": pn_id}
    route.pop("chatwoot_user_token", None)  # never leak the token
    return {"configured": True, "routed": True, "route": route}


@api_router.delete("/admin/whatsapp/route")
async def admin_delete_whatsapp_route(user: dict = Depends(_current_admin)):
    """Removes the current WhatsApp route (forces a fresh setup on next call).
    Note: this does NOT delete the Chatwoot inbox; it only removes our route mapping.
    """
    cfg = whatsapp_meta.get_config()
    pn_id = cfg.get("phone_number_id")
    if not pn_id:
        raise HTTPException(status_code=400, detail="WHATSAPP_PHONE_NUMBER_ID not set")
    result = await db.whatsapp_routes.delete_one({"phone_number_id": pn_id})
    # Also clear conversation cache so new conversations are created in the new account
    cache_cleared = await db.whatsapp_contacts.delete_many({"phone_number_id": pn_id})
    return {
        "deleted": result.deleted_count,
        "cache_cleared": cache_cleared.deleted_count,
    }


# ============================
# WhatsApp Lite (Evolution / QR) — per-user
# ============================
async def _resolve_user_for_whatsapp(user: dict) -> dict:
    """Ensure the user has a Chatwoot account (provision if missing) and return
    the fresh user doc."""
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not fresh:
        raise HTTPException(status_code=404, detail="user_not_found")
    if not fresh.get("chatwoot_account_id") or not fresh.get("chatwoot_access_token"):
        try:
            await _provision_chatwoot_async(user["id"])
            fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
        except Exception as e:
            logger.exception("auto-provision failed")
            raise HTTPException(status_code=500, detail=f"chatwoot_provision_failed: {e}")
    if not fresh or not fresh.get("chatwoot_account_id"):
        raise HTTPException(status_code=500, detail="chatwoot_not_provisioned")
    return fresh


@api_router.get("/me/channels/whatsapp/qr/config")
async def me_whatsapp_qr_config(user: dict = Depends(_current_user)):
    """Whether QR-based linking is available on this deployment."""
    return {"enabled": evolution_client.is_configured()}


# ============================
# WhatsApp BYOK (Manual Meta credentials)
# ============================
class BYOKConnectPayload(BaseModel):
    phone_number_id: str
    waba_id: str
    access_token: str


@api_router.get("/me/channels/whatsapp/byok")
async def me_whatsapp_byok_get(user: dict = Depends(_current_user)):
    doc = await whatsapp_byok.get_for_user(db, user["id"])
    return {
        "connected": bool(doc),
        "data": whatsapp_byok.mask_for_client(doc),
    }


@api_router.post("/me/channels/whatsapp/byok")
async def me_whatsapp_byok_connect(
    payload: BYOKConnectPayload, user: dict = Depends(_current_user),
):
    fresh = await _resolve_user_for_whatsapp(user)
    try:
        record = await whatsapp_byok.connect_user(
            db, user_doc=fresh,
            phone_number_id=payload.phone_number_id.strip(),
            waba_id=payload.waba_id.strip(),
            access_token=payload.access_token.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("BYOK connect failed")
        raise HTTPException(status_code=500, detail=f"byok_failed: {e}")
    return {"ok": True, "data": whatsapp_byok.mask_for_client(record)}


@api_router.delete("/me/channels/whatsapp/byok")
async def me_whatsapp_byok_delete(user: dict = Depends(_current_user)):
    return await whatsapp_byok.disconnect_user(db, user["id"])


@api_router.get("/me/channels/whatsapp/qr/debug")
async def me_whatsapp_qr_debug(user: dict = Depends(_current_user)):
    """Diagnostic: returns the raw Evolution responses so we can see what shape
    the QR is in. Safe to expose — only returns the user's own instance state."""
    if not evolution_client.is_configured():
        raise HTTPException(status_code=400, detail="evolution_not_configured")
    route = await evolution_routing.get_route(db, user_id=user["id"])
    if not route:
        return {"error": "no_route", "hint": "call POST /qr/create first"}
    instance = route["instance"]
    out: dict = {"instance": instance, "stored_state": route.get("state")}
    try:
        out["connection_state_raw"] = await evolution_client.get_connection_state(instance)
    except Exception as e:
        out["connection_state_error"] = str(e)[:300]
    try:
        out["connect_raw"] = await evolution_client.connect_instance(instance)
    except Exception as e:
        out["connect_error"] = str(e)[:300]
    return out


@api_router.post("/me/channels/whatsapp/qr/create")
async def me_whatsapp_qr_create(user: dict = Depends(_current_user)):
    """Creates (or reuses) the user's Evolution instance and returns the QR
    image they need to scan with their WhatsApp app."""
    if not evolution_client.is_configured():
        raise HTTPException(status_code=400, detail="evolution_not_configured")
    fresh = await _resolve_user_for_whatsapp(user)
    try:
        route = await evolution_routing.ensure_route(db, user_doc=fresh)
    except Exception as e:
        logger.exception("evolution ensure_route failed")
        raise HTTPException(status_code=502, detail=f"evolution_setup_failed: {e}")
    instance = route["instance"]

    # Pull a fresh QR. If Evolution returns "instance does not exist" (404),
    # we have a stale row pointing at a deleted instance — purge it and
    # auto-recreate, then retry one time.
    async def _fetch_qr() -> dict:
        try:
            return await evolution_client.connect_instance(instance)
        except evolution_client.EvolutionInstanceNotFound:
            raise  # bubble up so the caller can heal
        except Exception as e:
            logger.exception("evolution connect failed")
            raise HTTPException(status_code=502, detail=f"evolution_qr_failed: {e}")

    try:
        raw = await _fetch_qr()
    except evolution_client.EvolutionInstanceNotFound:
        logger.warning(
            "[QR] stale route for instance %s — Evolution returned 404. Purging route and recreating.",
            instance,
        )
        await db.evolution_routes.delete_one({"user_id": fresh["id"]})
        await db.evolution_contacts.delete_many({"instance": instance})
        # Re-create the route (this also creates a brand-new Evolution instance)
        try:
            route = await evolution_routing.ensure_route(db, user_doc=fresh)
        except Exception as e:
            logger.exception("evolution recreate-after-stale failed")
            raise HTTPException(status_code=502, detail=f"evolution_setup_failed: {e}")
        instance = route["instance"]
        try:
            raw = await evolution_client.connect_instance(instance)
        except Exception as e:
            logger.exception("evolution connect (post-heal) failed")
            raise HTTPException(status_code=502, detail=f"evolution_qr_failed: {e}")

    qr_b64 = _extract_qr_base64(raw)
    qr_code = _extract_qr_code(raw)

    if not qr_b64 and not qr_code:
        logger.info(
            "[QR] no QR in initial response (raw=%s) — restarting instance %s",
            str(raw)[:200], instance,
        )
        try:
            await evolution_client.restart_instance(instance)
        except Exception as e:
            logger.warning("[QR] restart failed (non-fatal): %s", e)
        import asyncio as _aio
        await _aio.sleep(1.5)
        try:
            raw = await evolution_client.connect_instance(instance)
        except Exception as e:
            logger.exception("evolution connect post-restart failed")
            raise HTTPException(status_code=502, detail=f"evolution_qr_failed: {e}")
        qr_b64 = _extract_qr_base64(raw)
        qr_code = _extract_qr_code(raw)

    logger.info(
        "[QR] user=%s instance=%s has_b64=%s has_code=%s raw_keys=%s",
        user.get("id"), instance, bool(qr_b64), bool(qr_code),
        list((raw or {}).keys()),
    )
    return {
        "instance": instance,
        "state": route.get("state"),
        "qr_base64": qr_b64,
        "qr_code": qr_code,
        "qr": qr_b64 or qr_code,
        "raw_keys": list((raw or {}).keys()),
    }


def _extract_qr_base64(raw: Any) -> Optional[str]:
    """Walk known paths in Evolution's varied responses to find a base64 PNG."""
    if not raw:
        return None
    candidates = [
        raw.get("base64") if isinstance(raw, dict) else None,
        (raw.get("qrcode") or {}).get("base64") if isinstance(raw, dict) else None,
        (raw.get("qr") or {}).get("base64") if isinstance(raw, dict) else None,
    ]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c
    return None


def _extract_qr_code(raw: Any) -> Optional[str]:
    """Raw `2@...` string (we can render with qrcode lib client-side)."""
    if not raw:
        return None
    candidates = [
        raw.get("code") if isinstance(raw, dict) else None,
        (raw.get("qrcode") or {}).get("code") if isinstance(raw, dict) else None,
        (raw.get("qr") or {}).get("code") if isinstance(raw, dict) else None,
    ]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c
    return None


@api_router.get("/me/channels/whatsapp/qr/status")
async def me_whatsapp_qr_status(user: dict = Depends(_current_user)):
    route = await evolution_routing.get_route(db, user_id=user["id"])
    if not route:
        return {"linked": False, "state": "not_linked"}
    try:
        live = await evolution_client.get_connection_state(route["instance"])
        state = ((live.get("instance") or {}).get("state")) or route.get("state")
    except Exception as e:
        logger.warning("evolution status failed: %s", e)
        state = route.get("state")
    return {
        "linked": state == "open",
        "state": state,
        "instance": route["instance"],
        "wa_number": route.get("wa_number"),
    }


@api_router.delete("/me/channels/whatsapp/qr")
async def me_whatsapp_qr_delete(user: dict = Depends(_current_user)):
    """Disconnects and deletes the Evolution instance for this user."""
    result = await evolution_routing.delete_route(db, user_id=user["id"])
    return result


@api_router.post("/webhooks/evolution")
async def evolution_webhook(request: Request):
    """Receives all events from Evolution API (messages, connection state, QR
    updates) and routes them appropriately."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    try:
        result = await evolution_routing.handle_evolution_webhook(db, payload)
    except Exception as e:
        logger.exception("evolution webhook failed: %s", e)
        result = {"error": str(e)[:200]}
    await db.evolution_events.insert_one({
        "id": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "event": payload.get("event"),
        "instance": payload.get("instance") or payload.get("instanceName"),
        "result": result,
    })
    return {"received": True, "result": result}


# ============================
# AI Agent administration
# ============================
class AISettingsPatch(BaseModel):
    enabled: Optional[bool] = None
    persona_ar: Optional[str] = None
    persona_en: Optional[str] = None
    handoff_message_ar: Optional[str] = None
    handoff_message_en: Optional[str] = None
    fallback_message_ar: Optional[str] = None
    fallback_message_en: Optional[str] = None
    website_url: Optional[str] = None
    model: Optional[str] = None
    llm_provider: Optional[str] = None  # "emergent" | "openai"
    openai_api_key: Optional[str] = None  # empty → keep existing
    auto_handoff_enabled: Optional[bool] = None
    auto_handoff_fallback_threshold: Optional[int] = None
    auto_handoff_repeat_threshold: Optional[int] = None
    auto_handoff_repeat_window_seconds: Optional[int] = None


class AIKnowledgePayload(BaseModel):
    title: str
    content: str
    lang: str = "both"  # "ar" | "en" | "both"


@api_router.get("/admin/ai/settings")
async def admin_get_ai_settings(admin: dict = Depends(_current_admin)):
    s = await ai_agent.get_settings(db)
    return ai_agent.mask_settings_for_client(s)


@api_router.put("/admin/ai/settings")
async def admin_update_ai_settings(patch: AISettingsPatch, admin: dict = Depends(_current_admin)):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    s = await ai_agent.update_settings(db, data)
    return ai_agent.mask_settings_for_client(s)


@api_router.get("/admin/ai/knowledge")
async def admin_list_knowledge(lang: Optional[str] = None, admin: dict = Depends(_current_admin)):
    return {"items": await ai_agent.list_knowledge(db, lang=lang)}


@api_router.post("/admin/ai/knowledge")
async def admin_add_knowledge(payload: AIKnowledgePayload, admin: dict = Depends(_current_admin)):
    if payload.lang not in ("ar", "en", "both"):
        raise HTTPException(status_code=422, detail="lang must be ar, en, or both")
    doc = {
        "id": str(uuid.uuid4()),
        "title": payload.title.strip(),
        "content": payload.content.strip(),
        "lang": payload.lang,
        "scope": "global",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_knowledge.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@api_router.delete("/admin/ai/knowledge/{kid}")
async def admin_delete_knowledge(kid: str, admin: dict = Depends(_current_admin)):
    result = await db.ai_knowledge.delete_one({"id": kid})
    return {"deleted": result.deleted_count}


@api_router.post("/admin/ai/conversation/{conversation_id}/takeover")
async def admin_takeover(conversation_id: int, admin: dict = Depends(_current_admin)):
    """Agent reclaims a conversation from the bot (stops AI replies)."""
    await ai_agent.set_handoff(db, conversation_id, True)
    return {"ok": True, "conversation_id": conversation_id, "handoff": True}


@api_router.post("/admin/ai/conversation/{conversation_id}/release")
async def admin_release(conversation_id: int, admin: dict = Depends(_current_admin)):
    """Re-enables the bot for a previously handoff conversation."""
    await ai_agent.set_handoff(db, conversation_id, False)
    return {"ok": True, "conversation_id": conversation_id, "handoff": False}


@api_router.get("/admin/conversations/active")
async def admin_list_active_conversations(admin: dict = Depends(_current_admin)):
    """Live view of every WhatsApp conversation the bot has touched, including
    handoff state, message count, last reply, and the customer's wa_id/name."""
    convos = await db.ai_conversations.find({}, {"_id": 0}).sort("last_reply_at", -1).to_list(length=200)
    # Enrich with contact info from whatsapp_contacts
    out = []
    for c in convos:
        cid = c.get("conversation_id")
        contact = await db.whatsapp_contacts.find_one(
            {"conversation_id": cid}, {"_id": 0, "wa_id": 1, "name": 1, "phone_number_id": 1},
        ) or {}
        out.append({
            "conversation_id": cid,
            "wa_id": contact.get("wa_id"),
            "contact_name": contact.get("name"),
            "phone_number_id": contact.get("phone_number_id"),
            "handoff": bool(c.get("handoff")),
            "handoff_at": c.get("handoff_at"),
            "last_reply_at": c.get("last_reply_at"),
            "message_count": c.get("message_count") or 0,
            "consecutive_fallbacks": c.get("consecutive_fallbacks") or 0,
        })
    return {"items": out}


@api_router.get("/admin/ai/diagnostics")
async def admin_ai_diagnostics(admin: dict = Depends(_current_admin)):
    """
    Returns the live status of the AI subsystem so the admin can see at a
    glance why the bot may not be replying.
    """
    settings_raw = await ai_agent.get_settings(db)
    settings = ai_agent.mask_settings_for_client(settings_raw)
    provider = (settings_raw.get("llm_provider") or "emergent").lower()
    emergent_key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    openai_key_stored = bool((settings_raw.get("openai_api_key") or "").strip())
    kb_count = await db.ai_knowledge.count_documents({})
    routes_count = await db.whatsapp_routes.count_documents({})
    last_events = await db.whatsapp_events.find(
        {}, {"_id": 0, "received_at": 1, "routing": 1}
    ).sort("received_at", -1).to_list(length=5)

    # provider readiness check
    if provider == "openai":
        provider_ready = bool(getattr(ai_agent, "_OPENAI_SDK_AVAILABLE", False)) and openai_key_stored
    else:
        provider_ready = bool(getattr(ai_agent, "_LLM_AVAILABLE", False)) and bool(emergent_key)

    return {
        "provider": provider,
        "provider_ready": provider_ready,
        "llm_available": getattr(ai_agent, "_LLM_AVAILABLE", False),
        "openai_sdk_available": getattr(ai_agent, "_OPENAI_SDK_AVAILABLE", False),
        "emergent_llm_key_present": bool(emergent_key),
        "emergent_llm_key_preview": (emergent_key[:6] + "…" + emergent_key[-4:]) if emergent_key else None,
        "openai_api_key_stored": openai_key_stored,
        "openai_api_key_preview": settings.get("openai_api_key_preview"),
        "settings": settings,
        "knowledge_entries": kb_count,
        "whatsapp_routes": routes_count,
        "recent_webhook_events": last_events,
    }


class AITestReplyPayload(BaseModel):
    text: str
    conversation_id: Optional[int] = 999999


@api_router.post("/admin/ai/test-reply")
async def admin_ai_test_reply(payload: AITestReplyPayload, admin: dict = Depends(_current_admin)):
    """
    Runs the full AI handler against a fake conversation so the admin can
    verify the bot end-to-end without sending a real WhatsApp message.
    Does NOT call Meta or Chatwoot.
    """
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    convo_id = payload.conversation_id or 999999
    try:
        result = await ai_agent.handle_incoming(
            db, conversation_id=convo_id, incoming_text=text,
        )
    except Exception as e:
        logger.exception("[AI test-reply] failed: %s", e)
        raise HTTPException(status_code=500, detail=f"ai_error: {e}")
    return {
        "input": text,
        "conversation_id": convo_id,
        **result,
    }


# ============================
# WhatsApp Broadcasts (admin)
# ============================
class BroadcastRecipientIn(BaseModel):
    phone: str
    name: Optional[str] = None
    params: Optional[dict] = None


class CreateBroadcastPayload(BaseModel):
    name: Optional[str] = None
    template_name: str
    template_language: str = "ar"
    params_template: list[str] = Field(default_factory=list)
    scheduled_at: Optional[datetime] = None  # ISO; None or past → send immediately
    # One of these three must be present:
    csv_text: Optional[str] = None
    plain_numbers: Optional[str] = None
    recipients: Optional[list[BroadcastRecipientIn]] = None


@api_router.get("/admin/whatsapp/templates")
async def admin_whatsapp_templates(admin: dict = Depends(_current_admin)):
    """Fetches Meta-approved templates for the configured WABA."""
    cfg = whatsapp_meta.get_config()
    waba_id = cfg.get("waba_id")
    if not waba_id:
        raise HTTPException(status_code=400, detail="WHATSAPP_BUSINESS_ACCOUNT_ID not configured")
    try:
        resp = await whatsapp_meta.list_message_templates(waba_id)
    except Exception as e:
        logger.exception("list_message_templates failed: %s", e)
        raise HTTPException(status_code=502, detail=f"meta_templates_failed: {e}")
    items = resp.get("data") or []
    # Pre-process: extract body placeholders from each template
    out = []
    for t in items:
        body_text = ""
        placeholder_count = 0
        for c in t.get("components") or []:
            if (c.get("type") or "").upper() == "BODY":
                body_text = c.get("text") or ""
                # Count {{1}}, {{2}}, ...
                import re as _re
                placeholder_count = len(set(_re.findall(r"\{\{\s*(\d+)\s*\}\}", body_text)))
                break
        out.append({
            "name": t.get("name"),
            "language": t.get("language"),
            "status": t.get("status"),
            "category": t.get("category"),
            "body": body_text,
            "placeholder_count": placeholder_count,
        })
    return {"items": out}


@api_router.post("/admin/whatsapp/broadcasts")
async def admin_create_broadcast(
    payload: CreateBroadcastPayload, admin: dict = Depends(_current_admin),
):
    # Resolve recipients
    recipients: list[dict] = []
    if payload.csv_text:
        recipients = broadcasts_mod.parse_csv(payload.csv_text)
    elif payload.plain_numbers:
        recipients = broadcasts_mod.parse_plain_numbers(payload.plain_numbers)
    elif payload.recipients:
        for r in payload.recipients:
            wa = broadcasts_mod.normalize_phone(r.phone)
            if wa:
                recipients.append({
                    "phone": wa,
                    "name": r.name or wa,
                    "params": r.params or {},
                })
    if not recipients:
        raise HTTPException(status_code=422, detail="no_valid_recipients")
    # Dedupe within request (preserve order, keep first)
    seen = set()
    deduped = []
    for r in recipients:
        if r["phone"] in seen:
            continue
        seen.add(r["phone"])
        deduped.append(r)

    try:
        broadcast = await broadcasts_mod.create_broadcast(
            db,
            name=payload.name or payload.template_name,
            template_name=payload.template_name,
            template_language=payload.template_language,
            params_template=payload.params_template,
            recipients=deduped,
            scheduled_at=payload.scheduled_at,
            created_by=admin.get("id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return broadcast


@api_router.get("/admin/whatsapp/broadcasts")
async def admin_list_broadcasts(admin: dict = Depends(_current_admin)):
    return {"items": await broadcasts_mod.list_broadcasts(db)}


@api_router.get("/admin/whatsapp/broadcasts/{bid}")
async def admin_get_broadcast(bid: str, admin: dict = Depends(_current_admin)):
    b = await broadcasts_mod.get_broadcast(db, bid)
    if not b:
        raise HTTPException(status_code=404, detail="not_found")
    return b


@api_router.get("/admin/whatsapp/broadcasts/{bid}/recipients")
async def admin_get_broadcast_recipients(bid: str, admin: dict = Depends(_current_admin)):
    return {"items": await broadcasts_mod.get_broadcast_recipients(db, bid)}


@api_router.post("/admin/whatsapp/broadcasts/{bid}/cancel")
async def admin_cancel_broadcast(bid: str, admin: dict = Depends(_current_admin)):
    return await broadcasts_mod.cancel_broadcast(db, bid)


# ============================
# Stripe webhook (placeholder)
# ============================
@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    await db.stripe_events.insert_one({
        "id": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "size": len(payload),
        "signed": bool(sig_header),
    })
    return {"received": True}


# ============================
# Chatwoot Super Admin (placeholder)
# ============================
@api_router.post("/chatwoot/accounts")
async def create_chatwoot_account(user_email: str, company_name: str):
    return {
        "stub": True,
        "user_email": user_email,
        "company_name": company_name,
        "message": "Chatwoot provisioning will be wired in next phase.",
    }


# ============================
# App lifecycle
# ============================
app.include_router(api_router)

# CORS - explicit origin required when allow_credentials=True
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes(db)
    await seed_admin(db)
    # Background broadcast processor
    app.state.broadcasts_task = asyncio.create_task(broadcasts_mod.worker_loop(db))
    logger.info("SocialHub API started — indexes ensured, admin seeded, broadcasts worker started.")


@app.on_event("shutdown")
async def on_shutdown():
    task = getattr(app.state, "broadcasts_task", None)
    if task:
        task.cancel()
    client.close()
