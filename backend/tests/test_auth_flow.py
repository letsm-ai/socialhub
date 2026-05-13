"""Backend regression tests for SocialHub auth + role flows.

Covers:
- /api/health smoke
- /api/auth/register (success, duplicate 409, validation 422)
- /api/auth/login (admin, client, bad password 401)
- Brute-force lockout (429 after 5 fails)
- /api/auth/me (Bearer success + 401 unauth)
- /api/auth/logout idempotency
- Admin seed exists + role preserved
- Subscription + Wallet documents created on register
- Mongo unique index on users.email
"""
import os
import time
import uuid
import asyncio
import pytest
import requests

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if BASE_URL is None:
    # Fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@socialhub.om"
ADMIN_PASSWORD = "Admin@2026"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


# ---------- module-level helpers ----------
def _unique_email(prefix="testuser"):
    # Backend lowercases emails — keep prefix lower for stable assertions
    return f"test_{prefix}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture(scope="module")
def session():
    return requests.Session()


@pytest.fixture(scope="module")
def mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_users():
    """Delete TEST_-prefixed users after the module completes."""
    yield
    from pymongo import MongoClient
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    # cleanup TEST_* docs
    user_emails = [u["email"] for u in db.users.find({"email": {"$regex": "^test_"}})]
    user_ids = [u["id"] for u in db.users.find({"email": {"$regex": "^test_"}})]
    db.users.delete_many({"email": {"$regex": "^test_"}})
    if user_ids:
        db.subscriptions.delete_many({"user_id": {"$in": user_ids}})
        db.wallets.delete_many({"user_id": {"$in": user_ids}})
    # also clear lockout attempts for those emails
    for e in user_emails:
        db.login_attempts.delete_many({"identifier": {"$regex": e}})
    c.close()


# ---------- Health ----------
class TestHealth:
    def test_health(self, session):
        r = session.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert "timestamp" in body


# ---------- Register ----------
class TestRegister:
    def test_register_success_creates_user_subscription_wallet(self, session):
        email = _unique_email("reg")
        r = session.post(f"{API}/auth/register", json={
            "name": "Reg User", "email": email, "password": "Pass@1234"
        }, timeout=15)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["email"] == email
        assert body["role"] == "CLIENT"
        assert body["name"] == "Reg User"
        assert "id" in body and isinstance(body["id"], str)
        assert "access_token" in body and len(body["access_token"]) > 20
        assert "password_hash" not in body
        assert "_id" not in body

        # Verify subscription + wallet exist in DB via direct mongo
        from pymongo import MongoClient
        c = MongoClient(MONGO_URL)
        db = c[DB_NAME]
        sub = db.subscriptions.find_one({"user_id": body["id"]})
        wal = db.wallets.find_one({"user_id": body["id"]})
        assert sub is not None, "Subscription not provisioned on register"
        assert sub["plan_tier"] == "GROWTH"
        assert sub["status"] == "TRIALING"
        assert wal is not None, "Wallet not provisioned on register"
        assert wal["balance_omr"] == 0.0
        c.close()

    def test_register_duplicate_email_returns_409(self, session):
        email = _unique_email("dup")
        body = {"name": "Dup User", "email": email, "password": "Pass@1234"}
        r1 = session.post(f"{API}/auth/register", json=body, timeout=15)
        assert r1.status_code == 201
        r2 = session.post(f"{API}/auth/register", json=body, timeout=15)
        assert r2.status_code == 409
        assert "already registered" in r2.json()["detail"].lower()

    def test_register_weak_password_returns_422(self, session):
        r = session.post(f"{API}/auth/register", json={
            "name": "Weak", "email": _unique_email("weak"), "password": "short"
        }, timeout=10)
        assert r.status_code == 422

    def test_register_missing_fields_returns_422(self, session):
        r = session.post(f"{API}/auth/register", json={"email": "noname@test.com"}, timeout=10)
        assert r.status_code == 422
        # Should include helpful detail
        detail = r.json().get("detail")
        assert detail and isinstance(detail, list) and len(detail) > 0

    def test_register_bad_email_format_returns_422(self, session):
        r = session.post(f"{API}/auth/register", json={
            "name": "Bad", "email": "not-an-email", "password": "Pass@1234"
        }, timeout=10)
        assert r.status_code == 422


# ---------- Login ----------
class TestLogin:
    def test_admin_login_role_preserved(self, session):
        r = session.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        }, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "ADMIN"
        assert body["email"] == ADMIN_EMAIL
        assert "access_token" in body
        assert "password_hash" not in body

    def test_client_login_after_register(self, session):
        email = _unique_email("login")
        password = "Pass@1234"
        reg = session.post(f"{API}/auth/register", json={
            "name": "Login User", "email": email, "password": password
        }, timeout=15)
        assert reg.status_code == 201

        r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "CLIENT"
        assert body["email"] == email

    def test_wrong_password_returns_401(self, session):
        # Use a fresh unique email so brute-force counter doesn't interfere
        email = _unique_email("badpass")
        session.post(f"{API}/auth/register", json={
            "name": "BadPass", "email": email, "password": "Pass@1234"
        }, timeout=15)
        r = session.post(f"{API}/auth/login", json={"email": email, "password": "WrongPass1!"}, timeout=10)
        assert r.status_code == 401
        assert "invalid" in r.json()["detail"].lower()


# ---------- Brute force ----------
class TestBruteForce:
    def test_lockout_after_5_fails(self, session):
        email = _unique_email("brute")
        session.post(f"{API}/auth/register", json={
            "name": "Brute", "email": email, "password": "Pass@1234"
        }, timeout=15)
        # 5 bad attempts -> all 401
        for i in range(5):
            r = session.post(f"{API}/auth/login", json={"email": email, "password": "Wrong!1"}, timeout=10)
            assert r.status_code == 401, f"attempt {i+1} expected 401 got {r.status_code}"
        # 6th attempt should be locked
        r6 = session.post(f"{API}/auth/login", json={"email": email, "password": "Wrong!1"}, timeout=10)
        assert r6.status_code == 429, f"6th attempt should be 429, got {r6.status_code} body={r6.text}"
        assert "too many" in r6.json()["detail"].lower()


# ---------- /me ----------
class TestMe:
    def test_me_with_bearer_returns_user_no_hash(self, session):
        email = _unique_email("me")
        reg = session.post(f"{API}/auth/register", json={
            "name": "Me User", "email": email, "password": "Pass@1234"
        }, timeout=15)
        assert reg.status_code == 201
        token = reg.json()["access_token"]

        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == email
        assert body["role"] == "CLIENT"
        assert "password_hash" not in body
        assert "_id" not in body

    def test_me_without_token_returns_401(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_me_with_invalid_token_returns_401(self):
        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": "Bearer not.a.valid.jwt"}, timeout=10)
        assert r.status_code == 401


# ---------- Logout ----------
class TestLogout:
    def test_logout_requires_auth(self):
        r = requests.post(f"{API}/auth/logout", timeout=10)
        assert r.status_code == 401

    def test_logout_with_token_idempotent(self, session):
        email = _unique_email("logout")
        reg = session.post(f"{API}/auth/register", json={
            "name": "Logout", "email": email, "password": "Pass@1234"
        }, timeout=15)
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r1 = requests.post(f"{API}/auth/logout", headers=headers, timeout=10)
        assert r1.status_code == 200
        assert r1.json().get("ok") is True
        # Idempotent: same token still works (we don't revoke server-side)
        r2 = requests.post(f"{API}/auth/logout", headers=headers, timeout=10)
        assert r2.status_code == 200


# ---------- DB Schema ----------
class TestDBSchema:
    def test_admin_seeded(self):
        from pymongo import MongoClient
        c = MongoClient(MONGO_URL)
        db = c[DB_NAME]
        admin = db.users.find_one({"email": ADMIN_EMAIL})
        assert admin is not None, "Admin user not seeded"
        assert admin["role"] == "ADMIN"
        assert admin.get("password_hash", "").startswith("$2"), "bcrypt hash not in $2 format"
        c.close()

    def test_users_email_unique_index(self):
        from pymongo import MongoClient
        c = MongoClient(MONGO_URL)
        db = c[DB_NAME]
        indexes = list(db.users.list_indexes())
        email_idx = [i for i in indexes if "email" in i.get("key", {})]
        assert any(i.get("unique") for i in email_idx), "users.email is not unique"
        # Also try inserting duplicate directly -> DuplicateKeyError
        dup_email = ADMIN_EMAIL
        with pytest.raises(DuplicateKeyError):
            db.users.insert_one({"id": str(uuid.uuid4()), "email": dup_email})
        c.close()
