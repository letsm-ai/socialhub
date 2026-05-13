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
