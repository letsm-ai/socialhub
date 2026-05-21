"""
WhatsApp ↔ Chatwoot routing.

Single-tenant for now: incoming WhatsApp messages to the SocialHub-owned
phone number are routed to the admin user's Chatwoot account.

Multi-tenant extension (later): the `whatsapp_routes` collection keys by
`phone_number_id` so each tenant's WABA can map to their own Chatwoot.

Collection schema (whatsapp_routes):
{
  "phone_number_id": "1138885239301614",   # Meta phone number id
  "user_id": "<socialhub uuid>",
  "chatwoot_account_id": 4,
  "chatwoot_user_token": "<user access token>",
  "chatwoot_inbox_id": 12,
  "inbox_identifier": "letsmAI WhatsApp",
  "created_at": "..."
}
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from chatwoot_client import (
    create_api_inbox,
    create_contact,
    create_conversation,
    post_message,
)
import whatsapp_meta

logger = logging.getLogger(__name__)


async def ensure_route(db, *, owner_user_doc: dict) -> dict:
    """
    Idempotently ensures a WhatsApp → Chatwoot route exists for the owner.
    Creates an API channel inbox inside the owner's Chatwoot account if missing.
    Returns the route document.
    """
    cfg = whatsapp_meta.get_config()
    pn_id = cfg["phone_number_id"]
    if not pn_id:
        raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID env var is required")

    existing = await db.whatsapp_routes.find_one({"phone_number_id": pn_id}, {"_id": 0})
    if existing:
        return existing

    account_id = owner_user_doc.get("chatwoot_account_id")
    user_token = owner_user_doc.get("chatwoot_access_token") or owner_user_doc.get("access_token")
    if not account_id or not user_token:
        raise RuntimeError("owner is missing chatwoot_account_id / chatwoot_user_access_token")

    backend_public = os.environ.get("BACKEND_PUBLIC_URL") or os.environ.get("FRONTEND_URL", "")
    webhook_url = f"{backend_public.rstrip('/')}/api/webhooks/chatwoot"
    inbox_name = "letsmAI WhatsApp"

    inbox = await create_api_inbox(account_id, user_token, name=inbox_name, webhook_url=webhook_url)
    inbox_id = inbox.get("id")

    route = {
        "phone_number_id": pn_id,
        "display_phone_number": cfg.get("display_phone_number") or os.environ.get("WHATSAPP_DISPLAY_PHONE_NUMBER", ""),
        "user_id": owner_user_doc.get("id"),
        "chatwoot_account_id": account_id,
        "chatwoot_user_token": user_token,
        "chatwoot_inbox_id": inbox_id,
        "inbox_identifier": inbox_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.whatsapp_routes.insert_one(route.copy())
    route.pop("_id", None)
    logger.info("WhatsApp route created: pn=%s inbox=%s", pn_id, inbox_id)
    return route


async def find_route_for_pn(db, phone_number_id: str) -> Optional[dict]:
    return await db.whatsapp_routes.find_one({"phone_number_id": phone_number_id}, {"_id": 0})


async def find_or_create_contact_conversation(
    db,
    *,
    route: dict,
    wa_id: str,
    name: str,
    first_text: str,
) -> dict:
    """Returns {contact_id, conversation_id, created_new}."""
    cache = await db.whatsapp_contacts.find_one(
        {"phone_number_id": route["phone_number_id"], "wa_id": wa_id},
        {"_id": 0},
    )
    if cache and cache.get("conversation_id"):
        return {
            "contact_id": cache["contact_id"],
            "conversation_id": cache["conversation_id"],
            "created_new": False,
        }

    account_id = route["chatwoot_account_id"]
    user_token = route["chatwoot_user_token"]
    inbox_id = route["chatwoot_inbox_id"]

    contact = await create_contact(
        account_id=account_id,
        user_token=user_token,
        inbox_id=inbox_id,
        name=name or wa_id,
        phone=f"+{wa_id}",
    )

    payload = contact.get("payload") or {}
    contact_obj = payload.get("contact") or payload
    contact_id = contact_obj.get("id") or contact.get("id")

    # Inbox-specific source_id (Chatwoot returns it in contact_inboxes)
    source_id = wa_id
    cis = payload.get("contact_inboxes") or contact.get("contact_inboxes") or []
    for ci in cis:
        if ci.get("inbox", {}).get("id") == inbox_id or ci.get("inbox_id") == inbox_id:
            source_id = ci.get("source_id") or source_id
            break

    convo = await create_conversation(
        account_id=account_id,
        user_token=user_token,
        inbox_id=inbox_id,
        contact_id=contact_id,
        source_id=source_id,
        message=first_text,
    )
    conversation_id = convo.get("id")

    await db.whatsapp_contacts.update_one(
        {"phone_number_id": route["phone_number_id"], "wa_id": wa_id},
        {"$set": {
            "phone_number_id": route["phone_number_id"],
            "wa_id": wa_id,
            "contact_id": contact_id,
            "conversation_id": conversation_id,
            "source_id": source_id,
            "name": name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return {"contact_id": contact_id, "conversation_id": conversation_id, "created_new": True}


async def append_incoming_message(db, *, route: dict, wa_id: str, name: str, text: str,
                                  meta_message_id: Optional[str] = None) -> dict:
    """Routes a WhatsApp incoming text message into Chatwoot, then asks the AI
    agent to optionally reply (auto-reply / handoff).

    `meta_message_id` is the `wamid.XXXX` from Meta. When provided, we dedupe
    so Meta webhook retries don't cause double AI replies.
    """
    import ai_agent
    import whatsapp_meta

    # Idempotency: short-circuit if we've already processed this exact wamid
    if meta_message_id:
        existing = await db.whatsapp_processed_messages.find_one(
            {"meta_message_id": meta_message_id}, {"_id": 0}
        )
        if existing:
            logger.info(
                "[AI] Duplicate webhook for wamid=%s — skipping (already processed)",
                meta_message_id,
            )
            return {"action": "duplicate_skipped", "meta_message_id": meta_message_id}
        # Best-effort record (race-safe via unique index created on startup)
        try:
            await db.whatsapp_processed_messages.insert_one({
                "meta_message_id": meta_message_id,
                "wa_id": wa_id,
                "processed_at": datetime.now(timezone.utc),
            })
        except Exception:
            # If another concurrent worker won the race, treat as duplicate
            logger.info("[AI] Race on wamid=%s — skipping", meta_message_id)
            return {"action": "duplicate_skipped", "meta_message_id": meta_message_id}

    found = await find_or_create_contact_conversation(
        db, route=route, wa_id=wa_id, name=name, first_text=text,
    )
    action = "created_conversation"
    if not found["created_new"]:
        msg = await post_message(
            account_id=route["chatwoot_account_id"],
            user_token=route["chatwoot_user_token"],
            conversation_id=found["conversation_id"],
            content=text,
            incoming=True,
        )
        action = "appended_message"
        message_id = msg.get("id")
    else:
        message_id = None

    # ---- AI auto-reply path ---------------------------------------------
    ai_result = {"action": "skipped"}
    logger.info(
        "[AI] Attempting auto-reply | convo=%s wa_id=%s text=%r",
        found["conversation_id"], wa_id, (text or "")[:120],
    )
    try:
        ai_result = await ai_agent.handle_incoming(
            db,
            conversation_id=found["conversation_id"],
            incoming_text=text,
        )
        logger.info(
            "[AI] handle_incoming -> action=%s lang=%s handoff=%s has_reply=%s",
            ai_result.get("action"), ai_result.get("lang"),
            ai_result.get("handoff"), bool(ai_result.get("reply")),
        )
        reply_text = ai_result.get("reply")
        if not reply_text:
            logger.warning(
                "[AI] No reply text generated. action=%s — check ai_settings.enabled, "
                "EMERGENT_LLM_KEY, and emergentintegrations install.",
                ai_result.get("action"),
            )
        if reply_text:
            logger.info("[AI] Reply preview: %r", reply_text[:160])
            # 1) Send to the user via Meta
            try:
                meta_resp = await whatsapp_meta.send_text_message(
                    route["phone_number_id"], wa_id, reply_text
                )
                logger.info("[AI] Meta send OK: %s", str(meta_resp)[:200])
            except Exception as e:
                logger.exception("[AI] failed to send via Meta: %s", e)

            # 2) Mirror as a PRIVATE NOTE in Chatwoot so the human agent sees
            #    what the bot said without Chatwoot's webhook firing back and
            #    causing a duplicate WhatsApp send.
            try:
                await post_message(
                    account_id=route["chatwoot_account_id"],
                    user_token=route["chatwoot_user_token"],
                    conversation_id=found["conversation_id"],
                    content=f"🤖 {reply_text}",
                    incoming=False,
                    private=True,
                )
                logger.info("[AI] Mirrored reply into Chatwoot as private note")
            except Exception as e:
                logger.exception("[AI] failed to mirror to Chatwoot: %s", e)

        # 3) Auto-handoff: send extra handoff message to user (if any) and
        #    drop a 🚨 private note alerting the team.
        extra_reply = ai_result.get("extra_reply")
        if extra_reply:
            try:
                await whatsapp_meta.send_text_message(
                    route["phone_number_id"], wa_id, extra_reply
                )
                logger.info("[AI] Sent extra handoff message via Meta")
            except Exception as e:
                logger.exception("[AI] failed to send handoff extra reply: %s", e)

        team_note = ai_result.get("team_note")
        if team_note:
            try:
                await post_message(
                    account_id=route["chatwoot_account_id"],
                    user_token=route["chatwoot_user_token"],
                    conversation_id=found["conversation_id"],
                    content=team_note,
                    incoming=False,
                    private=True,
                )
                logger.info("[AI] Posted team handoff alert as private note")
            except Exception as e:
                logger.exception("[AI] failed to post team note: %s", e)
    except Exception as e:
        logger.exception("[AI] handler failed: %s", e)
        ai_result = {"action": "error", "error": str(e)}

    return {
        "action": action,
        "message_id": message_id,
        "ai": ai_result,
        **found,
    }


def extract_incoming_messages(payload: dict) -> list[dict]:
    """
    Parses a Meta WhatsApp webhook payload and returns a list of normalized message dicts:
      {phone_number_id, wa_id, name, text, message_id, timestamp}
    Skips statuses (delivered/read) and non-text messages for the first iteration.
    """
    out: list[dict] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            if change.get("field") != "messages":
                continue
            val = change.get("value") or {}
            meta = val.get("metadata") or {}
            pn_id = meta.get("phone_number_id")
            contacts = {c.get("wa_id"): c for c in (val.get("contacts") or [])}
            for m in val.get("messages") or []:
                wa_id = m.get("from")
                if not wa_id:
                    continue
                if m.get("type") != "text":
                    # later: handle image/audio/document
                    continue
                text = (m.get("text") or {}).get("body") or ""
                profile = (contacts.get(wa_id) or {}).get("profile") or {}
                out.append({
                    "phone_number_id": pn_id,
                    "wa_id": wa_id,
                    "name": profile.get("name") or wa_id,
                    "text": text,
                    "message_id": m.get("id"),
                    "timestamp": m.get("timestamp"),
                })
    return out
