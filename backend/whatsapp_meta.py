"""
WhatsApp Cloud API integration as Meta Tech Provider.

Activated automatically when these env vars are present in backend/.env:
  - META_APP_ID
  - META_APP_SECRET
  - META_GRAPH_API_VERSION    (default: v20.0)
  - META_SYSTEM_USER_TOKEN     (long-lived, with whatsapp_business_management + whatsapp_business_messaging)
  - META_EMBEDDED_SIGNUP_CONFIG_ID
  - META_OAUTH_REDIRECT_URI    (default: https://app.letsm.io/api/meta/oauth/callback)
  - WHATSAPP_WEBHOOK_VERIFY_TOKEN

If any required var is missing, `is_configured()` returns False and the frontend
falls back to mock signup (current behavior is preserved).
"""
from __future__ import annotations

import hmac
import hashlib
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.facebook.com"


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------
def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


def get_config() -> Dict[str, str]:
    return {
        "app_id": _env("META_APP_ID"),
        "app_secret": _env("META_APP_SECRET"),
        "graph_version": _env("META_GRAPH_API_VERSION", "v20.0"),
        "system_user_token": _env("META_SYSTEM_USER_TOKEN"),
        "config_id": _env("META_EMBEDDED_SIGNUP_CONFIG_ID"),
        "redirect_uri": _env("META_OAUTH_REDIRECT_URI", "https://app.letsm.io/api/meta/oauth/callback"),
        "verify_token": _env("WHATSAPP_WEBHOOK_VERIFY_TOKEN"),
        "tech_provider_business_id": _env("META_TECH_PROVIDER_BUSINESS_ID"),
        "phone_number_id": _env("WHATSAPP_PHONE_NUMBER_ID"),
        "waba_id": _env("WHATSAPP_BUSINESS_ACCOUNT_ID"),
        "display_phone_number": _env("WHATSAPP_DISPLAY_PHONE_NUMBER"),
    }


def is_configured() -> bool:
    cfg = get_config()
    # Allow operation if we have system token + phone (Embedded Signup config is optional for single-tenant)
    return bool(cfg["app_id"] and cfg["app_secret"] and cfg["system_user_token"] and cfg["phone_number_id"])


def public_config_for_frontend() -> Dict[str, str]:
    """Safe values the frontend may consume — never the secret/token."""
    cfg = get_config()
    return {
        "enabled": is_configured(),
        "app_id": cfg["app_id"],
        "config_id": cfg["config_id"],
        "graph_version": cfg["graph_version"],
    }


def _graph_url(path: str) -> str:
    cfg = get_config()
    return f"{GRAPH_BASE_URL}/{cfg['graph_version']}/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# Webhook signature verification (X-Hub-Signature-256)
# ---------------------------------------------------------------------------
def verify_signature(raw_body: bytes, x_hub_signature_256: Optional[str]) -> bool:
    """Verify HMAC-SHA256 signature of webhook request body using App Secret."""
    if not x_hub_signature_256 or not x_hub_signature_256.startswith("sha256="):
        return False
    cfg = get_config()
    if not cfg["app_secret"]:
        return False
    received = x_hub_signature_256.split("=", 1)[1]
    expected = hmac.new(
        key=cfg["app_secret"].encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(received, expected)


# ---------------------------------------------------------------------------
# Graph API calls
# ---------------------------------------------------------------------------
async def exchange_code_for_token(auth_code: str) -> Dict[str, Any]:
    """Exchange the FB.login code for a (short-lived) user access token."""
    cfg = get_config()
    params = {
        "client_id": cfg["app_id"],
        "client_secret": cfg["app_secret"],
        "redirect_uri": cfg["redirect_uri"],
        "code": auth_code,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_graph_url("oauth/access_token"), params=params)
        resp.raise_for_status()
        return resp.json()


async def subscribe_waba(waba_id: str) -> Dict[str, Any]:
    """Subscribe our app to the tenant's WABA so we start receiving webhooks."""
    cfg = get_config()
    params = {"access_token": cfg["system_user_token"]}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _graph_url(f"{waba_id}/subscribed_apps"),
            params=params,
        )
        if resp.status_code >= 400:
            logger.error("subscribe_waba failed [%s]: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()


async def register_phone_number(phone_number_id: str, pin: str = "000000") -> Dict[str, Any]:
    """
    Register the phone number with WhatsApp Cloud API.
    The PIN is the 6-digit two-step verification PIN. For freshly onboarded numbers
    via Embedded Signup, Meta lets the Tech Provider set a fresh PIN here.
    """
    cfg = get_config()
    params = {"access_token": cfg["system_user_token"]}
    data = {"messaging_product": "whatsapp", "pin": pin}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_graph_url(f"{phone_number_id}/register"), params=params, data=data)
        if resp.status_code >= 400:
            logger.error("register_phone_number failed [%s]: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()


async def get_phone_number_details(phone_number_id: str) -> Dict[str, Any]:
    cfg = get_config()
    params = {
        "access_token": cfg["system_user_token"],
        "fields": "display_phone_number,verified_name,quality_rating,code_verification_status",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_graph_url(phone_number_id), params=params)
        resp.raise_for_status()
        return resp.json()


async def send_text_message(phone_number_id: str, to: str, body: str) -> Dict[str, Any]:
    """Send a freeform text message (only within 24h customer-service window)."""
    cfg = get_config()
    headers = {
        "Authorization": f"Bearer {cfg['system_user_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_graph_url(f"{phone_number_id}/messages"), headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error("send_text_message failed [%s]: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Full provisioning flow
# ---------------------------------------------------------------------------
async def provision_whatsapp(
    *,
    auth_code: Optional[str],
    waba_id: str,
    phone_number_id: str,
    business_id: Optional[str],
    pin: str = "000000",
) -> Dict[str, Any]:
    """
    Full provisioning pipeline. Returns a dict with everything we need to persist.
    Steps:
      1. (optional) exchange code → short-lived user token (mainly to bootstrap)
      2. subscribe our app to the WABA
      3. register the phone number on Cloud API
      4. fetch verified display name + phone for storage
    Any step failing raises httpx.HTTPStatusError; caller decides how to handle.
    """
    result: Dict[str, Any] = {
        "waba_id": waba_id,
        "phone_number_id": phone_number_id,
        "business_id": business_id,
    }

    # 1. (best-effort) code exchange — we don't strictly need the user token
    if auth_code:
        try:
            token_data = await exchange_code_for_token(auth_code)
            result["user_access_token_short"] = token_data.get("access_token")
        except Exception as e:
            logger.warning("code exchange failed (non-fatal): %s", e)

    # 2. subscribe WABA
    sub_result = await subscribe_waba(waba_id)
    result["subscribed_apps_response"] = sub_result

    # 3. register phone number
    try:
        reg_result = await register_phone_number(phone_number_id, pin=pin)
        result["register_response"] = reg_result
    except httpx.HTTPStatusError as e:
        # 400 with "already registered" is fine — capture but don't fail
        if e.response is not None and e.response.status_code == 400 and "already" in e.response.text.lower():
            result["register_response"] = {"already_registered": True}
        else:
            raise

    # 4. fetch display details
    try:
        details = await get_phone_number_details(phone_number_id)
        result["display_phone_number"] = details.get("display_phone_number")
        result["verified_name"] = details.get("verified_name")
        result["quality_rating"] = details.get("quality_rating")
    except Exception as e:
        logger.warning("get_phone_number_details failed (non-fatal): %s", e)

    return result
