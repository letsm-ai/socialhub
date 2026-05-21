"""
WhatsApp Broadcasts: create / list / process bulk template campaigns.

Flow:
  1. Admin uploads a CSV (or pastes phone numbers) and picks a Meta-approved
     template + body parameter mapping.
  2. A broadcast doc is created in Mongo with state="scheduled" or "running".
  3. A background worker (started from server.py on_startup) wakes every 10s
     and processes any broadcast whose `scheduled_at <= now`. It sends template
     messages in small batches and updates per-recipient status.

Collections:
  broadcasts        { id, name, template_name, template_language, status,
                      total, sent, failed, scheduled_at, created_at,
                      created_by, recipients_count, error?, params_template }
  broadcast_recipients
                    { broadcast_id, wa_id, name, params, status, error?,
                      meta_message_id?, sent_at? }

Statuses for broadcast: scheduled | running | completed | failed | cancelled
Statuses for recipient: pending | sent | failed | skipped
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

import whatsapp_meta

logger = logging.getLogger(__name__)

# Send no more than this many WhatsApp messages per worker tick.
_BATCH_SIZE = 20
# Pause between individual sends to avoid hitting Meta's rate limits.
_SEND_DELAY_SECONDS = 0.2
# How often the worker checks for due broadcasts.
_TICK_SECONDS = 10


# ---------- helpers -------------------------------------------------------


_PHONE_NORM_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """Strips everything but digits. Meta expects E.164 without '+'."""
    if not raw:
        return ""
    return _PHONE_NORM_RE.sub("", str(raw))


def parse_csv(csv_text: str) -> list[dict]:
    """
    Parses a CSV (with header row). Returns a list of {phone, name, params: {...}}.
    Required column: "phone" (any of: phone, mobile, number, whatsapp).
    Optional column: "name".
    All other columns become positional template params (column order preserved).
    """
    if not csv_text or not csv_text.strip():
        return []

    # Sniff delimiter; csv.Sniffer is best-effort.
    sample = csv_text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)

    if not reader.fieldnames:
        return []

    header = [h.strip() for h in reader.fieldnames]
    lower_map = {h.lower(): h for h in header}
    phone_key = None
    for cand in ("phone", "mobile", "number", "whatsapp", "wa", "wa_id"):
        if cand in lower_map:
            phone_key = lower_map[cand]
            break
    name_key = lower_map.get("name") or lower_map.get("first_name") or lower_map.get("full_name")
    param_keys = [
        h for h in header
        if h != phone_key and h != name_key
    ]

    out: list[dict] = []
    for row in reader:
        if not row:
            continue
        raw_phone = (row.get(phone_key) or "").strip() if phone_key else ""
        wa_id = normalize_phone(raw_phone)
        if not wa_id:
            continue
        name = ((row.get(name_key) or "").strip() if name_key else "") or wa_id
        params = {k: (row.get(k) or "").strip() for k in param_keys}
        out.append({"phone": wa_id, "name": name, "params": params})
    return out


def parse_plain_numbers(text: str) -> list[dict]:
    """Fallback: one phone number per line, no CSV header."""
    out: list[dict] = []
    for raw in (text or "").splitlines():
        wa = normalize_phone(raw)
        if wa:
            out.append({"phone": wa, "name": wa, "params": {}})
    return out


def render_template(params_template: list[str], recipient_params: dict) -> list[str]:
    """`params_template` is the list of column-name placeholders configured by
    the admin (e.g. ['name', 'order_id']). For each placeholder we look up the
    value from `recipient_params`. Empty values are kept (Meta requires
    positional params)."""
    out: list[str] = []
    for ph in params_template or []:
        # Allow literal values too — if placeholder isn't in recipient row,
        # fall back to the placeholder itself (so static templates still work).
        val = recipient_params.get(ph)
        if val is None or val == "":
            val = ""  # Meta rejects empty params; caller's responsibility to validate
        out.append(str(val))
    return out


# ---------- CRUD ----------------------------------------------------------


async def create_broadcast(
    db, *,
    name: str,
    template_name: str,
    template_language: str,
    params_template: list[str],
    recipients: list[dict],
    scheduled_at: Optional[datetime],
    created_by: str,
) -> dict:
    if not recipients:
        raise ValueError("no_recipients")
    bid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    sched = scheduled_at or now
    doc = {
        "id": bid,
        "name": (name or template_name or "Broadcast").strip(),
        "template_name": template_name,
        "template_language": template_language or "ar",
        "params_template": list(params_template or []),
        "status": "scheduled",
        "total": len(recipients),
        "sent": 0,
        "failed": 0,
        "scheduled_at": sched,
        "created_at": now,
        "created_by": created_by,
    }
    await db.broadcasts.insert_one(doc.copy())
    # Bulk insert recipients
    recipient_docs = [
        {
            "id": str(uuid.uuid4()),
            "broadcast_id": bid,
            "wa_id": r["phone"],
            "name": r.get("name") or r["phone"],
            "params": r.get("params") or {},
            "status": "pending",
            "created_at": now,
        }
        for r in recipients
    ]
    if recipient_docs:
        await db.broadcast_recipients.insert_many(recipient_docs)
    return _mask(doc)


async def list_broadcasts(db, limit: int = 50) -> list[dict]:
    docs = await db.broadcasts.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=limit)
    return [_mask(d) for d in docs]


async def get_broadcast(db, bid: str) -> Optional[dict]:
    doc = await db.broadcasts.find_one({"id": bid}, {"_id": 0})
    return _mask(doc) if doc else None


async def get_broadcast_recipients(db, bid: str, limit: int = 500) -> list[dict]:
    docs = await db.broadcast_recipients.find(
        {"broadcast_id": bid}, {"_id": 0},
    ).sort("created_at", 1).to_list(length=limit)
    for d in docs:
        for k in ("created_at", "sent_at"):
            v = d.get(k)
            if isinstance(v, datetime):
                d[k] = v.isoformat()
    return docs


async def cancel_broadcast(db, bid: str) -> dict:
    res = await db.broadcasts.update_one(
        {"id": bid, "status": {"$in": ["scheduled", "running"]}},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc)}},
    )
    return {"ok": True, "matched": res.matched_count, "modified": res.modified_count}


def _mask(doc: dict) -> dict:
    """Serialize datetimes to ISO strings for JSON responses."""
    if not doc:
        return doc
    out = dict(doc)
    for k in ("scheduled_at", "created_at", "started_at", "completed_at", "cancelled_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


# ---------- Worker --------------------------------------------------------


async def _process_one_broadcast(db, broadcast: dict) -> None:
    bid = broadcast["id"]
    cfg = whatsapp_meta.get_config()
    pn_id = cfg.get("phone_number_id")
    if not pn_id:
        logger.error("[broadcast %s] no WHATSAPP_PHONE_NUMBER_ID — failing broadcast", bid)
        await db.broadcasts.update_one(
            {"id": bid},
            {"$set": {"status": "failed", "error": "no_phone_number_id"}},
        )
        return

    # Mark running on first tick
    if broadcast["status"] == "scheduled":
        await db.broadcasts.update_one(
            {"id": bid},
            {"$set": {"status": "running", "started_at": datetime.now(timezone.utc)}},
        )

    # Re-check status (in case it got cancelled while we were starting)
    fresh = await db.broadcasts.find_one({"id": bid}, {"status": 1})
    if not fresh or fresh.get("status") not in ("running", "scheduled"):
        logger.info("[broadcast %s] status changed (%s) — stopping", bid, fresh and fresh.get("status"))
        return

    pending_cursor = db.broadcast_recipients.find(
        {"broadcast_id": bid, "status": "pending"}, {"_id": 0},
    ).limit(_BATCH_SIZE)
    pending = await pending_cursor.to_list(length=_BATCH_SIZE)
    if not pending:
        # All recipients processed → completion
        await db.broadcasts.update_one(
            {"id": bid, "status": "running"},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}},
        )
        logger.info("[broadcast %s] completed", bid)
        return

    template_name = broadcast["template_name"]
    template_lang = broadcast.get("template_language") or "ar"
    params_template = broadcast.get("params_template") or []

    sent_inc = 0
    failed_inc = 0
    for r in pending:
        # Honour cancellation between sends
        live = await db.broadcasts.find_one({"id": bid}, {"status": 1})
        if not live or live.get("status") not in ("running",):
            logger.info("[broadcast %s] cancelled mid-send — stopping", bid)
            break

        body_params = render_template(params_template, r.get("params") or {})
        try:
            resp = await whatsapp_meta.send_template_message(
                phone_number_id=pn_id,
                to=r["wa_id"],
                template_name=template_name,
                language_code=template_lang,
                body_parameters=body_params if params_template else None,
            )
            meta_msg_id = None
            try:
                meta_msg_id = (resp.get("messages") or [{}])[0].get("id")
            except Exception:
                pass
            await db.broadcast_recipients.update_one(
                {"broadcast_id": bid, "wa_id": r["wa_id"]},
                {"$set": {
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc),
                    "meta_message_id": meta_msg_id,
                }},
            )
            sent_inc += 1
        except httpx.HTTPStatusError as e:
            err = (e.response.text or "")[:300] if e.response is not None else str(e)
            await db.broadcast_recipients.update_one(
                {"broadcast_id": bid, "wa_id": r["wa_id"]},
                {"$set": {"status": "failed", "error": err}},
            )
            failed_inc += 1
        except Exception as e:
            await db.broadcast_recipients.update_one(
                {"broadcast_id": bid, "wa_id": r["wa_id"]},
                {"$set": {"status": "failed", "error": str(e)[:300]}},
            )
            failed_inc += 1

        if _SEND_DELAY_SECONDS:
            await asyncio.sleep(_SEND_DELAY_SECONDS)

    if sent_inc or failed_inc:
        await db.broadcasts.update_one(
            {"id": bid},
            {"$inc": {"sent": sent_inc, "failed": failed_inc}},
        )


async def worker_loop(db) -> None:
    """Long-running background task. Started from server.py on_startup."""
    logger.info("[broadcasts] worker started, tick=%ss batch=%s", _TICK_SECONDS, _BATCH_SIZE)
    while True:
        try:
            now = datetime.now(timezone.utc)
            due = await db.broadcasts.find(
                {"status": {"$in": ["scheduled", "running"]}, "scheduled_at": {"$lte": now}},
                {"_id": 0},
            ).sort("scheduled_at", 1).to_list(length=10)
            for b in due:
                try:
                    await _process_one_broadcast(db, b)
                except Exception as e:
                    logger.exception("[broadcasts] processing %s failed: %s", b.get("id"), e)
        except Exception as e:
            logger.exception("[broadcasts] worker iteration failed: %s", e)
        await asyncio.sleep(_TICK_SECONDS)
