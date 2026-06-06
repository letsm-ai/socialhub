"""
Chatwoot SSO Bridge — generates one-time SSO URLs that drop the user inside
Chatwoot's inbox-creation UI for OAuth-heavy channels (Facebook, Instagram,
WhatsApp Embedded Signup) and simpler API-channel forms (Telegram, Webchat).

The SSO flow uses Chatwoot's Platform API:
  GET  /platform/api/v1/users/{user_id}/login
       → returns {url: "https://inbox.letsm.io/?sso_auth_token=..."}

We then redirect the user (via popup window on the client) to that URL plus a
`redirect_to` querystring that lands them on the right page.

NOTE: opens via window.open from the SocialHub frontend, not via iframe —
Same-Origin Policy prevents iframe manipulation of a cross-domain Chatwoot.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


# Supported channel routes inside Chatwoot's UI
# (Chatwoot v3+ uses /settings/inboxes/new/{channel_type})
_CHANNEL_PATHS: Dict[str, str] = {
    "telegram": "/settings/inboxes/new/telegram",
    "facebook": "/settings/inboxes/new/facebook",
    "instagram": "/settings/inboxes/new/instagram",
    "whatsapp_embedded": "/settings/inboxes/new/whatsapp",
    "webchat": "/settings/inboxes/new/website",
    "email": "/settings/inboxes/new/email",
}


def _platform_token() -> str:
    # Accept either the new `CHATWOOT_PLATFORM_TOKEN` or the legacy
    # `CHATWOOT_PLATFORM_API_KEY` already used by chatwoot_client.py.
    t = (
        os.environ.get("CHATWOOT_PLATFORM_TOKEN")
        or os.environ.get("CHATWOOT_PLATFORM_API_KEY")
        or ""
    ).strip()
    if not t:
        raise RuntimeError(
            "CHATWOOT_PLATFORM_TOKEN (or CHATWOOT_PLATFORM_API_KEY) not configured — "
            "create one in Chatwoot Super Admin → Platform Apps"
        )
    return t


def _chatwoot_base() -> str:
    base = (os.environ.get("CHATWOOT_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("CHATWOOT_URL not configured")
    return base


def is_configured() -> bool:
    return bool(
        (
            (os.environ.get("CHATWOOT_PLATFORM_TOKEN") or "").strip()
            or (os.environ.get("CHATWOOT_PLATFORM_API_KEY") or "").strip()
        )
        and (os.environ.get("CHATWOOT_URL") or "").strip()
    )


def supported_channels() -> list[str]:
    return list(_CHANNEL_PATHS.keys())


async def generate_sso_link(
    *,
    chatwoot_user_id: int,
    chatwoot_account_id: int,
    channel: str,
) -> Dict[str, Any]:
    """
    Returns {url: "..."} — a one-time SSO URL that lands the user on the
    inbox-creation page for the requested channel inside Chatwoot.
    """
    if channel not in _CHANNEL_PATHS:
        raise ValueError(f"unsupported_channel: {channel}")

    base = _chatwoot_base()
    token = _platform_token()

    async with httpx.AsyncClient(timeout=15.0) as cx:
        r = await cx.get(
            f"{base}/platform/api/v1/users/{chatwoot_user_id}/login",
            headers={"api_access_token": token},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"sso_token_failed {r.status_code}: {r.text[:200]}")
        data = r.json()

    sso_url = data.get("url") or ""
    if not sso_url:
        raise RuntimeError("sso_url_missing_in_response")

    # Append the per-channel redirect_to so the user lands directly inside the
    # right inbox-creation page after Chatwoot consumes the SSO token.
    redirect_path = (
        f"/app/accounts/{chatwoot_account_id}{_CHANNEL_PATHS[channel]}"
    )
    sep = "&" if "?" in sso_url else "?"
    final_url = f"{sso_url}{sep}redirect_to={quote(redirect_path, safe='')}"
    logger.info(
        "[SSO] generated link channel=%s cw_user=%s cw_account=%s",
        channel, chatwoot_user_id, chatwoot_account_id,
    )
    return {"url": final_url, "channel": channel, "redirect_to": redirect_path}


async def list_user_inboxes(
    *, chatwoot_account_id: int, chatwoot_user_token: str,
) -> list[Dict[str, Any]]:
    """
    Polled by the frontend (via /api/me/channels/status) to detect when a new
    inbox was just created inside Chatwoot via the SSO popup.
    """
    base = _chatwoot_base()
    async with httpx.AsyncClient(timeout=10.0) as cx:
        r = await cx.get(
            f"{base}/api/v1/accounts/{chatwoot_account_id}/inboxes",
            headers={"api_access_token": chatwoot_user_token},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"list_inboxes {r.status_code}: {r.text[:200]}")
        payload = r.json() or {}
        return payload.get("payload") or payload.get("data") or []


_CHANNEL_TYPE_MAP: Dict[str, str] = {
    "Channel::Telegram": "telegram",
    "Channel::FacebookPage": "facebook",
    "Channel::Instagram": "instagram",
    "Channel::Whatsapp": "whatsapp",
    "Channel::WebWidget": "webchat",
    "Channel::Email": "email",
    "Channel::Api": "api",
}


def normalize_inbox(inbox: Dict[str, Any]) -> Dict[str, Any]:
    """Project Chatwoot inbox JSON to a UI-friendly shape."""
    return {
        "id": inbox.get("id"),
        "name": inbox.get("name"),
        "channel_type_raw": inbox.get("channel_type"),
        "channel_type": _CHANNEL_TYPE_MAP.get(inbox.get("channel_type") or "", "unknown"),
        "phone_number": inbox.get("phone_number"),
        "page_id": inbox.get("page_id"),
        "instagram_id": inbox.get("instagram_id"),
        "website_url": inbox.get("website_url"),
        "created_at": inbox.get("created_at"),
    }


async def find_user_by_email_brute_force(
    email: str, *, max_id: int = 200,
) -> Optional[Dict[str, Any]]:
    """
    Chatwoot's Platform API lacks a `list_users` or `find_by_email` endpoint.
    This brute-force walks `GET /platform/api/v1/users/{id}` from 1..max_id
    until it finds a match or exhausts the range.

    Used by the self-healing SSO endpoint to repair MongoDB records whose
    stored chatwoot_user_id is stale (e.g. after a Chatwoot DB restore).
    Returns the user JSON (incl. access_token + accounts) or None.
    """
    base = _chatwoot_base()
    token = _platform_token()
    target = email.lower().strip()
    async with httpx.AsyncClient(timeout=8.0) as cx:
        for uid in range(1, max_id + 1):
            try:
                r = await cx.get(
                    f"{base}/platform/api/v1/users/{uid}",
                    headers={"api_access_token": token},
                )
            except Exception:
                continue
            if r.status_code == 404:
                continue
            if r.status_code >= 400:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            if (data.get("email") or "").lower().strip() == target:
                logger.info("[SSO] Self-heal: email=%s found at chatwoot_user_id=%s", email, uid)
                return data
    return None


async def get_user_account_ids(chatwoot_user_id: int) -> list[int]:
    """Returns list of account IDs the user is a member of (via Platform API)."""
    base = _chatwoot_base()
    token = _platform_token()
    async with httpx.AsyncClient(timeout=10.0) as cx:
        r = await cx.get(
            f"{base}/platform/api/v1/users/{chatwoot_user_id}",
            headers={"api_access_token": token},
        )
        if r.status_code >= 400:
            return []
        data = r.json() or {}
        accounts = data.get("accounts") or []
        return [a.get("id") for a in accounts if a.get("id")]
