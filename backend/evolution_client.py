"""
Evolution API client — wraps the self-hosted Evolution API REST endpoints
(https://github.com/EvolutionAPI/evolution-api) so SocialHub can offer QR-based
WhatsApp linking for clients without a Meta developer account.

Env vars (read at request time):
  EVOLUTION_API_URL       e.g. https://evo.letsm.io
  EVOLUTION_API_KEY       global API key set in Evolution's .env

We use one Evolution `instance` per client account. The instance name is
"socialhub-{user_id_prefix}" so each tenant is isolated.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class EvolutionError(RuntimeError):
    pass


def _base() -> str:
    url = (os.environ.get("EVOLUTION_API_URL") or "").strip().rstrip("/")
    if not url:
        raise EvolutionError("EVOLUTION_API_URL not configured")
    return url


def _key() -> str:
    k = (os.environ.get("EVOLUTION_API_KEY") or "").strip()
    if not k:
        raise EvolutionError("EVOLUTION_API_KEY not configured")
    return k


def _headers() -> Dict[str, str]:
    return {"apikey": _key(), "Content-Type": "application/json"}


def is_configured() -> bool:
    return bool(
        (os.environ.get("EVOLUTION_API_URL") or "").strip()
        and (os.environ.get("EVOLUTION_API_KEY") or "").strip()
    )


def instance_name_for_user(user_id: str) -> str:
    """Stable per-user instance name. Evolution accepts alphanumerics + dashes."""
    safe = "".join(c for c in (user_id or "") if c.isalnum() or c == "-")[:32]
    return f"socialhub-{safe}"


# ---------------------------------------------------------------------------
# Instance lifecycle
# ---------------------------------------------------------------------------
async def create_instance(instance: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """POST /instance/create — creates a new WhatsApp instance and returns the
    initial QR (base64 image) the user must scan."""
    payload: Dict[str, Any] = {
        "instanceName": instance,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True,
    }
    if webhook_url:
        payload["webhook"] = {
            "url": webhook_url,
            "byEvents": False,
            "base64": False,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
        }
    async with httpx.AsyncClient(timeout=30.0) as cx:
        r = await cx.post(f"{_base()}/instance/create", headers=_headers(), json=payload)
        if r.status_code == 403 and "already in use" in r.text.lower():
            # Instance already exists — fetch its current QR/state
            logger.info("Evolution instance %s already exists — reusing", instance)
            return await connect_instance(instance)
        if r.status_code >= 400:
            raise EvolutionError(f"create_instance {r.status_code}: {r.text[:300]}")
        return r.json()


async def connect_instance(instance: str) -> Dict[str, Any]:
    """GET /instance/connect/{instance} — returns the current QR or connection state."""
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.get(f"{_base()}/instance/connect/{instance}", headers=_headers())
        if r.status_code >= 400:
            raise EvolutionError(f"connect_instance {r.status_code}: {r.text[:300]}")
        return r.json()


async def get_connection_state(instance: str) -> Dict[str, Any]:
    """GET /instance/connectionState/{instance} — returns {state: 'open'|'close'|'connecting'}."""
    async with httpx.AsyncClient(timeout=15.0) as cx:
        r = await cx.get(
            f"{_base()}/instance/connectionState/{instance}",
            headers=_headers(),
        )
        if r.status_code == 404:
            return {"instance": {"state": "not_found"}}
        if r.status_code >= 400:
            raise EvolutionError(f"connection_state {r.status_code}: {r.text[:300]}")
        return r.json()


async def logout_instance(instance: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as cx:
        r = await cx.delete(f"{_base()}/instance/logout/{instance}", headers=_headers())
        # Allow 404 (already disconnected)
        if r.status_code >= 400 and r.status_code != 404:
            raise EvolutionError(f"logout_instance {r.status_code}: {r.text[:300]}")
        return r.json() if r.text else {"ok": True}


async def delete_instance(instance: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as cx:
        r = await cx.delete(f"{_base()}/instance/delete/{instance}", headers=_headers())
        if r.status_code >= 400 and r.status_code != 404:
            raise EvolutionError(f"delete_instance {r.status_code}: {r.text[:300]}")
        return r.json() if r.text else {"ok": True}


# ---------------------------------------------------------------------------
# Messaging (outgoing — replies sent by human agent in Chatwoot)
# ---------------------------------------------------------------------------
async def send_text_message(instance: str, wa_number: str, text: str) -> Dict[str, Any]:
    """POST /message/sendText/{instance}"""
    payload = {"number": wa_number, "text": text}
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(
            f"{_base()}/message/sendText/{instance}",
            headers=_headers(),
            json=payload,
        )
        if r.status_code >= 400:
            raise EvolutionError(f"send_text {r.status_code}: {r.text[:300]}")
        return r.json()
