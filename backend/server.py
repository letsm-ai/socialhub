"""SocialHub API — FastAPI + MongoDB."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
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
    # Provision default subscription (TRIALING on GROWTH) + empty wallet
    await db.subscriptions.insert_one(new_subscription_doc(user_doc["id"], plan_tier="GROWTH"))
    await db.wallets.insert_one(new_wallet_doc(user_doc["id"]))

    access = create_access_token(user_doc["id"], email, role="CLIENT")
    refresh = create_refresh_token(user_doc["id"])
    set_auth_cookies(response, access, refresh)

    return {**_user_public(dict(user_doc)), "access_token": access}


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
    return {"packages": TOPUP_PACKAGES, "price_per_message_omr": MESSAGE_PRICE_OMR}


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
async def topup_wallet(payload: TopupRequest, user: dict = Depends(_current_user)):
    """
    MOCK Stripe checkout — instantly credits the wallet.
    In production this would create a Stripe Checkout Session and only credit
    after the `checkout.session.completed` webhook.
    """
    pkg = next((p for p in TOPUP_PACKAGES if p["id"] == payload.package_id), None)
    if not pkg:
        raise HTTPException(status_code=400, detail="Unknown top-up package")
    now = datetime.now(timezone.utc).isoformat()
    # Atomic balance + credits update
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
        "created_at": now,
    }
    await db.wallet_transactions.insert_one(dict(txn))
    wallet = await db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    balance = float(wallet.get("balance_omr", 0))
    return {
        "ok": True,
        "stub": True,
        "wallet": wallet,
        "transaction": txn,
        "estimated_messages_remaining": int(balance / MESSAGE_PRICE_OMR),
    }


# ----- /me/account: aggregated dashboard view -----
@api_router.get("/me/account")
async def my_account(user: dict = Depends(_current_user)):
    """Aggregated view used by the client dashboard: user + subscription + wallet + chatwoot link."""
    sub = await db.subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})
    wallet = await db.wallets.find_one({"user_id": user["id"]}, {"_id": 0})
    return {
        "user": user,
        "subscription": sub,
        "wallet": wallet,
        "chatwoot_url": os.environ.get("CHATWOOT_URL", ""),
    }


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
    return {"ok": True}


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
