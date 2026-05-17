"""
Authentication module — JWT-based with bcrypt password hashing.
Models follow the same business shape as the Prisma schema requested:
- User: id, name, email, password_hash, role (CLIENT/ADMIN), chatwoot_account_id, stripe_customer_id
- Subscription: user_id, plan_tier (GROWTH/PRO/ENTERPRISE), status
- Wallet: user_id, balance_omr, total_promotional_messages_sent
"""
import os
import bcrypt
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, ConfigDict

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7

# Brute-force settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


# ============================
# Password helpers
# ============================
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ============================
# JWT helpers
# ============================
def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


# ============================
# Pydantic schemas
# ============================
class UserPublic(BaseModel):
    """User shape returned to the client (no password)."""
    model_config = ConfigDict(extra="ignore")
    id: str
    email: EmailStr
    name: str
    role: Literal["CLIENT", "ADMIN"]
    chatwoot_account_id: Optional[int] = None
    stripe_customer_id: Optional[str] = None
    created_at: Optional[datetime] = None


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    company_name: Optional[str] = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


# ============================
# Auth helpers (DB-aware)
# ============================
async def get_current_user(request: Request, db) -> dict:
    """Resolve the currently authenticated user from cookie or Bearer token."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(request: Request, db) -> dict:
    user = await get_current_user(request, db)
    if user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ============================
# Brute force protection
# ============================
async def check_login_lockout(db, identifier: str) -> None:
    """Raise 429 if account is currently locked out due to failed attempts."""
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if doc and doc.get("locked_until"):
        locked_until = doc["locked_until"]
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Try again in a few minutes.",
            )


async def record_failed_login(db, identifier: str) -> None:
    now = datetime.now(timezone.utc)
    doc = await db.login_attempts.find_one({"identifier": identifier})
    attempts = (doc.get("attempts", 0) if doc else 0) + 1
    update = {"attempts": attempts, "last_failed_at": now.isoformat()}
    if attempts >= MAX_FAILED_ATTEMPTS:
        update["locked_until"] = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        update["attempts"] = 0
    await db.login_attempts.update_one(
        {"identifier": identifier}, {"$set": update}, upsert=True
    )


async def clear_failed_logins(db, identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})


# ============================
# User factory + Admin seeding
# ============================
def new_user_doc(name: str, email: str, password_hash: str, role: str = "CLIENT") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email.lower().strip(),
        "password_hash": password_hash,
        "role": role,  # 'CLIENT' or 'ADMIN'
        "chatwoot_account_id": None,
        "stripe_customer_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def new_subscription_doc(user_id: str, plan_tier: str = "GROWTH") -> dict:
    """plan_tier: GROWTH | PRO | ENTERPRISE"""
    now = datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "plan_tier": plan_tier,
        "status": "TRIALING",  # TRIALING | ACTIVE | PAST_DUE | CANCELED
        "stripe_subscription_id": None,
        "trial_started_at": now.isoformat(),
        "trial_ends_at": (now + timedelta(days=7)).isoformat(),
        "current_period_start": now.isoformat(),
        "current_period_end": (now + timedelta(days=7)).isoformat(),
        "created_at": now.isoformat(),
    }


def new_wallet_doc(user_id: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "balance_omr": 0.0,
        "promotional_credits": 50,  # 50 welcome messages (gift)
        "promotional_credits_initial": 50,
        "total_promotional_messages_sent": 0,
        "welcome_gift_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def seed_admin(db) -> None:
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@socialhub.om").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@2026")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        doc = new_user_doc("SocialHub Admin", admin_email, hash_password(admin_password), role="ADMIN")
        await db.users.insert_one(doc)
        # Provision empty subscription + wallet for completeness
        await db.subscriptions.insert_one(new_subscription_doc(doc["id"], plan_tier="ENTERPRISE"))
        await db.wallets.insert_one(new_wallet_doc(doc["id"]))
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password), "role": "ADMIN"}},
        )


async def ensure_indexes(db) -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.subscriptions.create_index("user_id")
    await db.wallets.create_index("user_id", unique=True)
    await db.login_attempts.create_index("identifier")
