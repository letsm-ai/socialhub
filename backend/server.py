"""SocialHub API — FastAPI + MongoDB."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

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
import chatwoot_client
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
        # Either it's not a WhatsApp conversation, or we haven't tracked it
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
    """
    owner_user_id = (payload or {}).get("owner_user_id") or user.get("id")
    owner = await db.users.find_one({"id": owner_user_id}, {"_id": 0})
    if not owner:
        raise HTTPException(status_code=404, detail="owner_user_not_found")
    if not owner.get("chatwoot_account_id"):
        raise HTTPException(status_code=400, detail="owner has no chatwoot account")

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
    logger.info("SocialHub API started — indexes ensured, admin seeded.")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
