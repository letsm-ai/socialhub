"""
Bridges Evolution API webhooks → Chatwoot, mirroring `whatsapp_routing.py` but
for QR-based connections. Each user owns one Evolution instance and one
matching Chatwoot API inbox.

Collection `evolution_routes`:
  { user_id, instance, chatwoot_account_id, chatwoot_inbox_id,
    chatwoot_user_token, wa_number, state, created_at }
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from chatwoot_client import (
    create_api_inbox,
    create_contact,
    create_conversation,
    post_message,
)
import evolution_client

logger = logging.getLogger(__name__)


async def get_route(db, *, user_id: str) -> Optional[Dict[str, Any]]:
    return await db.evolution_routes.find_one({"user_id": user_id}, {"_id": 0})


async def get_route_by_instance(db, instance: str) -> Optional[Dict[str, Any]]:
    return await db.evolution_routes.find_one({"instance": instance}, {"_id": 0})


async def ensure_route(db, *, user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Idempotently creates a Chatwoot API inbox + Evolution instance for the
    given user. Returns the route doc.

    Since SocialHub clients run as Chatwoot `agent` (locked-down role), they
    can't create inboxes directly. We momentarily promote them to
    administrator for the inbox-creation call, then demote back to agent.
    """
    existing = await get_route(db, user_id=user_doc["id"])
    if existing:
        return existing

    account_id = user_doc.get("chatwoot_account_id")
    user_token = user_doc.get("chatwoot_access_token")
    cw_user_id = user_doc.get("chatwoot_user_id")
    if not account_id or not user_token or not cw_user_id:
        raise RuntimeError("user is missing chatwoot_account_id / token / user_id")

    backend_public = (
        os.environ.get("BACKEND_PUBLIC_URL")
        or os.environ.get("FRONTEND_URL")
        or ""
    ).rstrip("/")
    if not backend_public:
        raise RuntimeError("BACKEND_PUBLIC_URL / FRONTEND_URL not configured")

    # 1) Briefly promote to administrator so we can create an inbox under
    #    their Chatwoot account, then demote back to agent immediately.
    from chatwoot_client import set_user_role  # local import to avoid cycles
    try:
        await set_user_role(account_id, cw_user_id, role="administrator")
    except Exception as e:
        logger.warning("Could not promote user to admin temporarily: %s", e)
    try:
        inbox_name = "WhatsApp (Lite / QR)"
        cw_webhook = f"{backend_public}/api/webhooks/chatwoot"
        inbox = await create_api_inbox(account_id, user_token, name=inbox_name, webhook_url=cw_webhook)
        inbox_id = inbox.get("id")
    finally:
        try:
            await set_user_role(account_id, cw_user_id, role="agent")
        except Exception as e:
            logger.error(
                "CRITICAL: failed to demote user %s back to agent: %s — manual fix required",
                cw_user_id, e,
            )

    # 2) Evolution instance + register webhook back to us
    instance = evolution_client.instance_name_for_user(user_doc["id"])
    evo_webhook = f"{backend_public}/api/webhooks/evolution"
    create_resp = await evolution_client.create_instance(instance, webhook_url=evo_webhook)

    route = {
        "user_id": user_doc["id"],
        "instance": instance,
        "chatwoot_account_id": account_id,
        "chatwoot_user_token": user_token,
        "chatwoot_inbox_id": inbox_id,
        "inbox_identifier": inbox_name,
        "wa_number": None,
        "state": "qr_pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_qr_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.evolution_routes.insert_one(route.copy())
    route.pop("_id", None)
    route["create_response"] = create_resp
    logger.info("Evolution route created: user=%s instance=%s inbox=%s",
                user_doc["id"], instance, inbox_id)
    return route


async def update_state(db, *, instance: str, state: str, wa_number: Optional[str] = None) -> None:
    patch = {"state": state, "updated_at": datetime.now(timezone.utc).isoformat()}
    if wa_number:
        patch["wa_number"] = wa_number
    await db.evolution_routes.update_one({"instance": instance}, {"$set": patch})


async def delete_route(db, *, user_id: str) -> Dict[str, Any]:
    route = await get_route(db, user_id=user_id)
    if not route:
        return {"ok": True, "missing": True}
    instance = route["instance"]
    try:
        await evolution_client.logout_instance(instance)
    except Exception as e:
        logger.warning("logout_instance failed: %s", e)
    try:
        await evolution_client.delete_instance(instance)
    except Exception as e:
        logger.warning("delete_instance failed: %s", e)
    await db.evolution_routes.delete_one({"user_id": user_id})
    return {"ok": True, "instance": instance}


# ---------------------------------------------------------------------------
# Incoming webhook (Evolution → SocialHub → Chatwoot)
# ---------------------------------------------------------------------------
_WA_ID_RE = re.compile(r"^(\d+)")


def _wa_id_from_remote_jid(jid: str) -> Optional[str]:
    """Evolution sends `remoteJid` like `9689XXXXXXXX@s.whatsapp.net`."""
    if not jid:
        return None
    m = _WA_ID_RE.match(jid.split("@", 1)[0])
    return m.group(1) if m else None


def _extract_text(message_obj: Dict[str, Any]) -> str:
    """Pull plain text out of Baileys' message envelope."""
    if not message_obj:
        return ""
    if "conversation" in message_obj and message_obj["conversation"]:
        return message_obj["conversation"]
    ext = message_obj.get("extendedTextMessage") or {}
    if ext.get("text"):
        return ext["text"]
    img = message_obj.get("imageMessage") or {}
    if img.get("caption"):
        return img["caption"]
    return ""


async def handle_evolution_webhook(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Routes incoming Evolution events. Currently handles:
      - messages.upsert (incoming user message → Chatwoot)
      - connection.update / qrcode.updated → state changes
    """
    event = (payload.get("event") or "").lower()
    instance = payload.get("instance") or payload.get("instanceName") or ""
    data = payload.get("data") or {}

    route = await get_route_by_instance(db, instance)
    if not route:
        logger.warning("Evolution webhook: no route for instance %s", instance)
        return {"ignored": "no_route"}

    if event in ("qrcode.updated", "qrcode_updated"):
        await update_state(db, instance=instance, state="qr_pending")
        return {"ok": True, "state": "qr_pending"}

    if event in ("connection.update", "connection_update"):
        state = (data.get("state") or "").lower()
        wa_number = None
        owner = data.get("wuid") or data.get("ownerJid")
        if owner:
            wa_number = _wa_id_from_remote_jid(owner)
        if state == "open":
            await update_state(db, instance=instance, state="connected", wa_number=wa_number)
            return {"ok": True, "state": "connected"}
        if state == "close":
            await update_state(db, instance=instance, state="disconnected")
            return {"ok": True, "state": "disconnected"}
        await update_state(db, instance=instance, state=state or "unknown")
        return {"ok": True, "state": state}

    if event not in ("messages.upsert", "messages_upsert"):
        return {"ignored": event}

    key = data.get("key") or {}
    if key.get("fromMe"):
        return {"ignored": "from_me"}
    remote_jid = key.get("remoteJid") or ""
    wa_id = _wa_id_from_remote_jid(remote_jid)
    if not wa_id:
        return {"ignored": "no_wa_id"}

    text = _extract_text(data.get("message") or {})
    if not text.strip():
        return {"ignored": "no_text"}

    push_name = data.get("pushName") or wa_id

    # Find-or-create Chatwoot contact + conversation
    cache = await db.evolution_contacts.find_one(
        {"instance": instance, "wa_id": wa_id}, {"_id": 0},
    )

    if cache and cache.get("conversation_id"):
        # Append incoming message
        await post_message(
            account_id=route["chatwoot_account_id"],
            user_token=route["chatwoot_user_token"],
            conversation_id=cache["conversation_id"],
            content=text,
            incoming=True,
        )
        return {"ok": True, "action": "appended", "conversation_id": cache["conversation_id"]}

    # Create new contact + conversation
    account_id = route["chatwoot_account_id"]
    user_token = route["chatwoot_user_token"]
    inbox_id = route["chatwoot_inbox_id"]
    contact = await create_contact(
        account_id=account_id, user_token=user_token, inbox_id=inbox_id,
        name=push_name, phone=f"+{wa_id}",
    )
    payload_inner = contact.get("payload") or {}
    contact_obj = payload_inner.get("contact") or payload_inner
    contact_id = contact_obj.get("id") or contact.get("id")
    source_id = wa_id
    cis = payload_inner.get("contact_inboxes") or contact.get("contact_inboxes") or []
    for ci in cis:
        if ci.get("inbox", {}).get("id") == inbox_id or ci.get("inbox_id") == inbox_id:
            source_id = ci.get("source_id") or source_id
            break
    convo = await create_conversation(
        account_id=account_id, user_token=user_token, inbox_id=inbox_id,
        contact_id=contact_id, source_id=source_id, message=text,
    )
    conversation_id = convo.get("id")
    await db.evolution_contacts.update_one(
        {"instance": instance, "wa_id": wa_id},
        {"$set": {
            "instance": instance, "wa_id": wa_id,
            "contact_id": contact_id, "conversation_id": conversation_id,
            "source_id": source_id, "name": push_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "action": "created", "conversation_id": conversation_id}


# ---------------------------------------------------------------------------
# Outgoing: Chatwoot agent reply → Evolution → user's phone
# ---------------------------------------------------------------------------
async def send_via_chatwoot_outgoing(db, *, conversation_id: int, content: str) -> Dict[str, Any]:
    """Called from the existing /api/webhooks/chatwoot handler when the
    conversation belongs to an Evolution route. Returns {sent: bool}."""
    contact_map = await db.evolution_contacts.find_one(
        {"conversation_id": conversation_id}, {"_id": 0},
    )
    if not contact_map:
        return {"sent": False, "reason": "not_evolution_route"}
    instance = contact_map["instance"]
    wa_id = contact_map["wa_id"]
    try:
        resp = await evolution_client.send_text_message(instance, wa_id, content)
        return {"sent": True, "result": resp}
    except Exception as e:
        logger.exception("Evolution send failed: %s", e)
        return {"sent": False, "error": str(e)[:200]}
