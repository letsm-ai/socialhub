"""
Thawani Pay integration (Oman's main local payment gateway).

Activated automatically when these env vars are present in backend/.env:
  - THAWANI_SECRET_KEY
  - THAWANI_PUBLISHABLE_KEY
  - THAWANI_WEBHOOK_SECRET           (set in Thawani merchant portal)
  - THAWANI_ENV                       (uat | production; default: uat)

When THAWANI_SECRET_KEY is missing, `is_configured()` returns False and the
frontend falls back to mock top-up (preserving current behavior).

API docs: https://thawani-technologies.stoplight.io/docs/thawani-ecommerce-api
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

UAT_BASE_URL = "https://uatcheckout.thawani.om/api/v1"
PROD_BASE_URL = "https://checkout.thawani.om/api/v1"
UAT_CHECKOUT_URL = "https://uatcheckout.thawani.om/pay"
PROD_CHECKOUT_URL = "https://checkout.thawani.om/pay"


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


def get_config() -> Dict[str, str]:
    return {
        "secret_key": _env("THAWANI_SECRET_KEY"),
        "publishable_key": _env("THAWANI_PUBLISHABLE_KEY"),
        "webhook_secret": _env("THAWANI_WEBHOOK_SECRET"),
        "env": _env("THAWANI_ENV", "uat").lower(),
    }


def is_configured() -> bool:
    cfg = get_config()
    return bool(cfg["secret_key"] and cfg["publishable_key"])


def _base_url() -> str:
    return PROD_BASE_URL if get_config()["env"] == "production" else UAT_BASE_URL


def _checkout_base() -> str:
    return PROD_CHECKOUT_URL if get_config()["env"] == "production" else UAT_CHECKOUT_URL


def public_config_for_frontend() -> Dict[str, Any]:
    cfg = get_config()
    return {
        "enabled": is_configured(),
        "publishable_key": cfg["publishable_key"],
        "env": cfg["env"],
    }


# ---------------------------------------------------------------------------
# Webhook signature verification (HMAC-SHA256)
# ---------------------------------------------------------------------------
def verify_signature(raw_body: bytes, timestamp: Optional[str], signature: Optional[str]) -> bool:
    """
    Webhook signature is HMAC-SHA256 of `body + '-' + timestamp` using webhook secret.
    Headers from Thawani: `thawani-timestamp`, `thawani-signature`.
    """
    cfg = get_config()
    if not (timestamp and signature and cfg["webhook_secret"]):
        return False
    try:
        body_text = raw_body.decode("utf-8", errors="ignore")
        msg = f"{body_text}-{timestamp}"
        expected = hmac.new(
            key=cfg["webhook_secret"].encode("utf-8"),
            msg=msg.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.warning("verify_signature error: %s", e)
        return False


# ---------------------------------------------------------------------------
# Checkout Session API
# ---------------------------------------------------------------------------
async def create_checkout_session(
    *,
    amount_omr: float,
    products: List[Dict[str, Any]],
    client_reference_id: str,
    success_url: str,
    cancel_url: str,
    metadata: Optional[Dict[str, str]] = None,
    customer_id: Optional[str] = None,
    save_card_on_success: bool = False,
) -> Dict[str, Any]:
    """
    Creates a Thawani Checkout Session.
    Amount unit: BAISA (1 OMR = 1000 baisa). Items also use baisa.
    Returns the full session payload incl. session_id.
    """
    cfg = get_config()
    if not is_configured():
        raise RuntimeError("Thawani not configured")

    # Normalize all amounts to baisa (Thawani only accepts integer baisa)
    products_in_baisa = [
        {
            "name": p["name"][:50],
            "quantity": int(p.get("quantity", 1)),
            "unit_amount": int(round(float(p["unit_amount_omr"]) * 1000)),
        }
        for p in products
    ]

    payload: Dict[str, Any] = {
        "client_reference_id": client_reference_id,
        "mode": "payment",
        "products": products_in_baisa,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "save_card_on_success": save_card_on_success,
        "metadata": metadata or {},
    }
    if customer_id:
        payload["customer_id"] = customer_id

    headers = {
        "thawani-api-key": cfg["secret_key"],
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f"{_base_url()}/checkout/session", headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error("Thawani create_checkout_session %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Thawani error: {data}")
    return data["data"]


async def get_checkout_session(session_id: str) -> Dict[str, Any]:
    cfg = get_config()
    if not is_configured():
        raise RuntimeError("Thawani not configured")
    headers = {"thawani-api-key": cfg["secret_key"]}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{_base_url()}/checkout/session/{session_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", {})


def build_payment_url(session_id: str) -> str:
    """Compose the URL the customer is redirected to."""
    cfg = get_config()
    return f"{_checkout_base()}/{session_id}?key={cfg['publishable_key']}"
