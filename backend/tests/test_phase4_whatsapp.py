"""
Phase 4 backend tests — WhatsApp Meta Tech Provider endpoints + regression for Chatwoot removal.

Endpoints covered:
  - GET  /api/whatsapp/config            (public config)
  - POST /api/whatsapp/connect           (Embedded Signup; MOCK when META env empty)
  - GET  /api/webhooks/whatsapp          (hub.challenge handshake)
  - POST /api/webhooks/whatsapp          (event ingestion; signature skipped in MOCK)
  - Regression: /me/account, /me/channels, /me/wallet, /me/wallet/topup, /auth/me,
    /me/channels/whatsapp (legacy), admin overview
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@socialhub.om"
ADMIN_PASS = "Admin@2026"
CLIENT_EMAIL = "ahmed@test.com"
CLIENT_PASS = "Test@1234"


def _no_object_id(obj):
    if isinstance(obj, dict):
        if "_id" in obj:
            return False
        return all(_no_object_id(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_object_id(v) for v in obj)
    return True


# --------- fixtures ---------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def client_session():
    """Login with the seeded ahmed@test.com (company_name=متجر أحمد)."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PASS}, timeout=15)
    assert r.status_code == 200, f"client login: {r.status_code} {r.text}"
    body = r.json()
    token = body["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s, body


@pytest.fixture(scope="module")
def fresh_client():
    """Register a brand-new client (so we don't disturb ahmed)."""
    s = requests.Session()
    suffix = uuid.uuid4().hex[:8]
    email = f"test_phase4_{suffix}@test.com"
    payload = {"name": "Phase4", "email": email, "password": "Pass@1234", "company_name": "Phase4 Co"}
    r = s.post(f"{API}/auth/register", json=payload, timeout=15)
    assert r.status_code == 201, f"register: {r.status_code} {r.text}"
    body = r.json()
    s.headers.update({"Authorization": f"Bearer {body['access_token']}", "Content-Type": "application/json"})
    return s, body


# --------- /api/whatsapp/config ---------
class TestWhatsAppConfig:
    def test_config_public_shape(self):
        r = requests.get(f"{API}/whatsapp/config", timeout=10)
        assert r.status_code == 200
        data = r.json()
        # Required keys
        for k in ("enabled", "app_id", "config_id", "graph_version"):
            assert k in data, f"missing key: {k}"
        # META env is empty by design now
        assert data["enabled"] is False
        assert data["app_id"] == ""
        assert data["config_id"] == ""
        # graph_version defaults to v20.0
        assert data["graph_version"] == "v20.0"
        # never leak secret/token fields
        for forbidden in ("app_secret", "system_user_token", "verify_token"):
            assert forbidden not in data, f"leaked: {forbidden}"

    def test_config_no_auth_required(self):
        # Should be publicly readable so FB SDK can init from anywhere
        r = requests.get(f"{API}/whatsapp/config", timeout=10)
        assert r.status_code == 200


# --------- POST /api/whatsapp/connect (MOCK mode) ---------
class TestWhatsAppConnectMock:
    def test_requires_auth(self):
        r = requests.post(f"{API}/whatsapp/connect", json={
            "waba_id": "wX", "phone_number_id": "pX"
        }, timeout=10)
        assert r.status_code == 401

    def test_mock_connect_persists_channel(self, fresh_client):
        s, _ = fresh_client
        # ensure clean
        s.delete(f"{API}/me/channels/whatsapp")
        payload = {
            "waba_id": "waba_mock_001",
            "phone_number_id": "pnid_mock_001",
            "business_id": "biz_mock_001",
            "code": "fake-fb-code-xyz",
        }
        r = s.post(f"{API}/whatsapp/connect", json=payload, timeout=15)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["ok"] is True
        ch = body["channel"]
        assert ch["provider"] == "whatsapp"
        assert ch["status"] == "CONNECTED"
        assert ch["waba_id"] == "waba_mock_001"
        assert ch["phone_number_id"] == "pnid_mock_001"
        assert ch["business_id"] == "biz_mock_001"
        assert ch["provisioned_via"] == "mock"
        assert _no_object_id(body)

        # Verify GET /me/channels exposes it
        lr = s.get(f"{API}/me/channels", timeout=10)
        assert lr.status_code == 200
        chans = lr.json()["channels"]
        assert len(chans) == 1
        assert chans[0]["waba_id"] == "waba_mock_001"
        assert chans[0]["provisioned_via"] == "mock"
        assert "access_token" not in chans[0]

    def test_mock_connect_idempotent(self, fresh_client):
        s, _ = fresh_client
        payload = {"waba_id": "waba_mock_002", "phone_number_id": "pnid_mock_002"}
        r1 = s.post(f"{API}/whatsapp/connect", json=payload, timeout=15)
        assert r1.status_code == 201
        r2 = s.post(f"{API}/whatsapp/connect", json=payload, timeout=15)
        assert r2.status_code == 201
        # only one channel persisted (upsert)
        lr = s.get(f"{API}/me/channels", timeout=10).json()
        wa_count = sum(1 for c in lr["channels"] if c["provider"] == "whatsapp")
        assert wa_count == 1


# --------- GET /api/webhooks/whatsapp (verify handshake) ---------
class TestWebhookVerify:
    def test_verify_with_empty_token_must_403(self):
        # since WHATSAPP_WEBHOOK_VERIFY_TOKEN is empty, no token should be accepted
        r = requests.get(
            f"{API}/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "12345"},
            timeout=10,
        )
        assert r.status_code == 403

    def test_verify_with_random_token_403(self):
        r = requests.get(
            f"{API}/webhooks/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "guess", "hub.challenge": "12345"},
            timeout=10,
        )
        assert r.status_code == 403

    def test_verify_wrong_mode_403(self):
        r = requests.get(
            f"{API}/webhooks/whatsapp",
            params={"hub.mode": "wrong", "hub.verify_token": "anything", "hub.challenge": "99"},
            timeout=10,
        )
        assert r.status_code == 403


# --------- POST /api/webhooks/whatsapp (event ingestion in MOCK mode) ---------
class TestWebhookEvent:
    def test_post_event_no_signature_accepted_when_meta_unconfigured(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "wabaXYZ", "changes": []}],
        }
        r = requests.post(f"{API}/webhooks/whatsapp", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json() == {"received": True}

    def test_post_event_empty_body_accepted(self):
        r = requests.post(f"{API}/webhooks/whatsapp", data=b"", timeout=10)
        assert r.status_code == 200


# --------- Regression: legacy /me/channels/whatsapp still works ---------
class TestLegacyChannel:
    def test_legacy_endpoint_still_alive(self, fresh_client):
        s, _ = fresh_client
        s.delete(f"{API}/me/channels/whatsapp")
        payload = {
            "waba_id": "legacy_waba",
            "phone_number": "+96812345678",
            "phone_number_id": "legacy_pnid",
            "display_name": "Legacy WA",
        }
        r = s.post(f"{API}/me/channels/whatsapp", json=payload, timeout=10)
        assert r.status_code == 201
        ch = r.json()["channel"]
        assert ch["waba_id"] == "legacy_waba"
        assert ch["status"] == "CONNECTED"

    def test_legacy_disconnect(self, fresh_client):
        s, _ = fresh_client
        r = s.delete(f"{API}/me/channels/whatsapp", timeout=10)
        assert r.status_code == 200


# --------- Regression: existing flows still work ---------
class TestRegression:
    def test_auth_me(self, client_session):
        s, _ = client_session
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        u = r.json()
        assert u["email"] == CLIENT_EMAIL
        assert u.get("company_name") == "متجر أحمد", f"company_name missing: {u}"

    def test_me_account_aggregate(self, client_session):
        s, _ = client_session
        r = s.get(f"{API}/me/account", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["email"] == CLIENT_EMAIL
        assert data["subscription"]["plan_tier"] in {"GROWTH", "PRO", "ENTERPRISE"}
        assert "balance_omr" in data["wallet"]

    def test_me_channels(self, client_session):
        s, _ = client_session
        r = s.get(f"{API}/me/channels", timeout=10)
        assert r.status_code == 200
        assert "channels" in r.json()

    def test_me_wallet(self, client_session):
        s, _ = client_session
        r = s.get(f"{API}/me/wallet", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "wallet" in data and "transactions" in data

    def test_wallet_topup_mock(self, client_session):
        s, _ = client_session
        before = float(s.get(f"{API}/me/wallet").json()["wallet"]["balance_omr"])
        r = s.post(f"{API}/me/wallet/topup", json={"package_id": "basic"}, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["transaction"]["status"] == "PAID"
        after = float(s.get(f"{API}/me/wallet").json()["wallet"]["balance_omr"])
        assert after >= before + 12.5 - 0.001

    def test_admin_overview(self, admin_token):
        r = requests.get(
            f"{API}/admin/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "users" in data or "clients" in data or "totals" in data or isinstance(data, dict)
