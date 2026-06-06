"""
WhatsApp BYOK (Bring Your Own Key) — lets clients connect their own Meta
WhatsApp Cloud API credentials manually, before/without Embedded Signup.

The client gets these from Meta Business Manager → WhatsApp:
  - Phone number ID (numeric)
  - WhatsApp Business Account ID (WABA ID, numeric)
  - Access token (System User permanent token, starts with EAA…)
  - Display phone number (for UI only)

We store them in `whatsapp_byok` (one doc per user) and provision a matching
Chatwoot inbox so incoming messages route into their account.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from chatwoot_client import create_api_inbox, set_user_role

logger = logging.getLogger(__name__)


META_GRAPH = "https://graph.facebook.com/v21.0"


# ---------------------------------------------------------------------------
# Validation against Meta
# ---------------------------------------------------------------------------
async def verify_credentials(
    phone_number_id: str, access_token: str
) -> Dict[str, Any]:
    """Calls Meta Graph to confirm the phone_number_id + token are valid and
    returns the phone number's display info. Raises on failure with a
    human-friendly message that distinguishes between expired/invalid tokens."""
    async with httpx.AsyncClient(timeout=15.0) as cx:
        r = await cx.get(
            f"{META_GRAPH}/{phone_number_id}",
            params={
                "access_token": access_token,
                "fields": "display_phone_number,verified_name,quality_rating,id",
            },
        )
        if r.status_code >= 400:
            # Parse Meta's structured error to map to friendlier messages
            try:
                err = r.json().get("error", {})
                code = err.get("code")
                sub = err.get("error_subcode")
                meta_msg = err.get("message", "")
            except Exception:
                code, sub, meta_msg = None, None, r.text[:200]
            # 190 = OAuthException, sub 463 = expired session
            if code == 190 and sub == 463:
                raise ValueError(
                    "token_expired: Session expired. The token you pasted is a "
                    "TEMPORARY token (24h validity). You need a PERMANENT System "
                    "User token. Steps: Meta Business Manager → Business Settings "
                    "→ Users → System Users → Create → Generate token with "
                    "'whatsapp_business_management' + 'whatsapp_business_messaging' "
                    "permissions → Set 'Never' expiry."
                )
            if code == 190:
                raise ValueError(
                    f"invalid_access_token: {meta_msg}. Re-copy the token from Meta "
                    "Business Manager and make sure no spaces or line breaks."
                )
            if code == 100 and "phone_number_id" in meta_msg.lower():
                raise ValueError(
                    "invalid_phone_number_id: The Phone Number ID you pasted "
                    "doesn't match the token's account. Copy both from the same "
                    "WhatsApp app in Meta Business Manager."
                )
            raise ValueError(f"meta_verify_failed [{r.status_code}]: {meta_msg}")
        return r.json()


# ---------------------------------------------------------------------------
# DB lookup / management
# ---------------------------------------------------------------------------
async def get_for_user(db, user_id: str) -> Optional[Dict[str, Any]]:
    return await db.whatsapp_byok.find_one({"user_id": user_id}, {"_id": 0})


async def get_by_phone_number_id(db, phone_number_id: str) -> Optional[Dict[str, Any]]:
    """Used by the incoming webhook to find which user owns a phone_number_id."""
    return await db.whatsapp_byok.find_one(
        {"phone_number_id": phone_number_id}, {"_id": 0},
    )


def mask_for_client(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Returns a copy safe to send to the frontend — token is masked."""
    if not doc:
        return None
    out = dict(doc)
    token = out.pop("access_token", "") or ""
    out["access_token"] = ""
    out["access_token_preview"] = (
        (token[:6] + "…" + token[-4:]) if len(token) > 12 else ("set" if token else None)
    )
    return out


async def connect_user(
    db,
    *,
    user_doc: Dict[str, Any],
    phone_number_id: str,
    waba_id: str,
    access_token: str,
) -> Dict[str, Any]:
    """Validates against Meta, persists credentials, provisions Chatwoot inbox.
    Idempotent: re-running updates the stored token and refreshes display info."""

    # 1) Validate with Meta
    meta_info = await verify_credentials(phone_number_id, access_token)
    display_phone = meta_info.get("display_phone_number") or ""
    verified_name = meta_info.get("verified_name") or ""

    # 2) Ensure a Chatwoot inbox exists. Because the user is locked to `agent`,
    #    promote → create inbox → demote (same pattern as Evolution route).
    account_id = user_doc.get("chatwoot_account_id")
    user_token_cw = user_doc.get("chatwoot_access_token")
    cw_user_id = user_doc.get("chatwoot_user_id")
    if not account_id or not user_token_cw or not cw_user_id:
        raise RuntimeError("chatwoot_not_provisioned_for_user")

    existing = await get_for_user(db, user_doc["id"])
    inbox_id = (existing or {}).get("chatwoot_inbox_id")

    if not inbox_id:
        backend_public = (
            os.environ.get("BACKEND_PUBLIC_URL")
            or os.environ.get("FRONTEND_URL")
            or ""
        ).rstrip("/")
        if not backend_public:
            raise RuntimeError("BACKEND_PUBLIC_URL_not_configured")
        cw_webhook = f"{backend_public}/api/webhooks/chatwoot"
        try:
            await set_user_role(account_id, cw_user_id, role="administrator")
        except Exception as e:
            logger.warning("could not temp-promote user to admin: %s", e)
        try:
            inbox = await create_api_inbox(
                account_id, user_token_cw,
                name=f"WhatsApp ({display_phone or phone_number_id})",
                webhook_url=cw_webhook,
            )
            inbox_id = inbox.get("id")
        finally:
            try:
                await set_user_role(account_id, cw_user_id, role="agent")
            except Exception as e:
                logger.error("CRITICAL: failed to demote user %s: %s", cw_user_id, e)

    # 3) Persist
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "user_id": user_doc["id"],
        "phone_number_id": phone_number_id,
        "waba_id": waba_id,
        "access_token": access_token,
        "display_phone": display_phone,
        "verified_name": verified_name,
        "chatwoot_account_id": account_id,
        "chatwoot_inbox_id": inbox_id,
        "chatwoot_user_token": user_token_cw,
        "status": "connected",
        "verified_at": now,
        "updated_at": now,
    }
    if not existing:
        record["created_at"] = now
    await db.whatsapp_byok.update_one(
        {"user_id": user_doc["id"]},
        {"$set": record},
        upsert=True,
    )
    logger.info(
        "[BYOK] user=%s phone_number_id=%s waba=%s display=%s inbox=%s",
        user_doc["id"], phone_number_id, waba_id, display_phone, inbox_id,
    )
    return record


async def disconnect_user(db, user_id: str) -> Dict[str, Any]:
    res = await db.whatsapp_byok.delete_one({"user_id": user_id})
    return {"ok": True, "deleted": res.deleted_count}
