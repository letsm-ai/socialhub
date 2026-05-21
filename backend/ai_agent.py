"""
AI Agent for SocialHub WhatsApp customer support.

Behavior:
  • Replies to every new incoming message via GPT-4o (strict — knowledge-grounded).
  • Detects human-handoff intent ("أبي أتكلم مع موظف", "talk to human", etc.) and
    once detected, marks the conversation; the bot stops replying for that
    conversation until an admin reactivates it.
  • Knowledge base is a Mongo collection (`ai_knowledge`). The agent receives
    these snippets in the system prompt; if the answer isn't in them, the
    agent says so (no hallucinations).

Collections used:
  ai_settings              { _id="global", enabled: bool, persona: str,
                             handoff_message: str, fallback_message: str,
                             website_url: str }
  ai_knowledge             { id, title, content, lang, scope, created_at }
  ai_conversations         { conversation_id, handoff: bool, handoff_at,
                             last_reply_at, message_count }
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import so the module can be imported even when emergentintegrations
# isn't installed (e.g. in environments where AI is disabled).
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    _LLM_AVAILABLE = True
except Exception as e:  # pragma: no cover
    logger.warning("emergentintegrations not available: %s — AI replies disabled", e)
    _LLM_AVAILABLE = False

try:
    from openai import AsyncOpenAI  # type: ignore
    _OPENAI_SDK_AVAILABLE = True
except Exception as e:  # pragma: no cover
    logger.warning("openai SDK not available: %s — direct OpenAI provider disabled", e)
    _OPENAI_SDK_AVAILABLE = False


# ---------- Constants ----------------------------------------------------

DEFAULT_PERSONA_AR = (
    "أنت مساعد ذكاء اصطناعي ودود ومحترف لمنصة SocialHub (letsmAI). "
    "أنت تردّ على عملاء عبر واتساب باسم الفريق. أسلوبك:\n"
    "- ودود وقريب من العميل دون مبالغة.\n"
    "- مختصر ومباشر. لا تذكر تفاصيل غير مطلوبة.\n"
    "- محترف، تستخدم العربية الفصحى البسيطة في الردود العربية.\n"
    "- لا تذكر أبداً أنك ChatGPT أو OpenAI. تعرّف فقط بأنك مساعد SocialHub.\n"
    "\n"
    "⚠️ قاعدة صارمة — لا تخمين أبداً:\n"
    "اعتمد فقط على المعلومات الموجودة في قسم \"معلومات SocialHub\" أدناه. "
    "إذا لم يكن الجواب موجوداً، اعتذر باختصار واطلب من العميل الانتظار "
    "ليتواصل معه أحد أعضاء الفريق. لا تخترع أسعاراً ولا ميزاتٍ ولا أرقام "
    "اتصال غير موجودة في المعلومات."
)

DEFAULT_PERSONA_EN = (
    "You are a friendly, professional AI assistant for SocialHub (letsmAI). "
    "You reply to customers on WhatsApp on behalf of the team. Style:\n"
    "- Warm but concise. Plain language, never robotic.\n"
    "- Direct. Do not add information that wasn't asked for.\n"
    "- Never reveal you are ChatGPT or OpenAI; introduce yourself only as the SocialHub assistant.\n"
    "\n"
    "⚠️ STRICT RULE — never guess:\n"
    "Answer ONLY from the \"SocialHub Knowledge\" section below. If the answer "
    "isn't there, briefly apologize and tell the customer a team member will "
    "follow up shortly. Never invent prices, features, or contact info."
)


# Human handoff signals (Arabic + English)
_HANDOFF_PATTERNS = [
    r"\bتحويل\b.*?(موظف|إنسان|انسان|بشر|شخص)",
    r"\b(أبي|ابي|أبغى|ابغى|أريد|اريد)\b.*?(موظف|إنسان|انسان|بشر|شخص)",
    r"\bموظف\b",
    r"\bخدمة\s*العملاء\b",
    r"\btalk to (a |an )?(human|agent|person|representative)\b",
    r"\b(speak|chat) (to|with) (a |an )?(human|agent|person)\b",
    r"\bhuman agent\b",
    r"\breal person\b",
    r"\boperator\b",
]
_HANDOFF_RE = re.compile("|".join(_HANDOFF_PATTERNS), re.IGNORECASE)


# ---------- Settings helpers ---------------------------------------------

async def get_settings(db) -> dict:
    s = await db.ai_settings.find_one({"_id": "global"}, {"_id": 0})
    if not s:
        s = {
            "enabled": True,
            "persona_ar": DEFAULT_PERSONA_AR,
            "persona_en": DEFAULT_PERSONA_EN,
            "handoff_message_ar": "تم تحويلك لأحد أعضاء الفريق، سيتواصلون معك خلال لحظات. شكراً لصبرك! 🙏",
            "handoff_message_en": "Got it — connecting you to our team. Someone will be with you shortly. Thanks for your patience! 🙏",
            "fallback_message_ar": "اعذرني، لست متأكداً من إجابة دقيقة لهذا السؤال. سأطلب من أحد أعضاء الفريق التواصل معك قريباً.",
            "fallback_message_en": "I'm not sure about that one. Let me have a team member follow up with you shortly.",
            "website_url": "https://app.letsm.io",
            "model": "gpt-4o",
            "llm_provider": "emergent",   # "emergent" | "openai"
            "openai_api_key": "",          # used only when llm_provider == "openai"
            # Auto-handoff configuration
            "auto_handoff_enabled": True,
            "auto_handoff_fallback_threshold": 2,    # N consecutive fallback replies
            "auto_handoff_repeat_threshold": 3,      # N near-identical msgs from user
            "auto_handoff_repeat_window_seconds": 120,
        }
    # Ensure newer fields exist for older rows
    s.setdefault("llm_provider", "emergent")
    s.setdefault("openai_api_key", "")
    s.setdefault("auto_handoff_enabled", True)
    s.setdefault("auto_handoff_fallback_threshold", 2)
    s.setdefault("auto_handoff_repeat_threshold", 3)
    s.setdefault("auto_handoff_repeat_window_seconds", 120)
    # Backfill fallback messages — required by _is_fallback_reply to detect
    # the bot's "I don't know" replies for auto-handoff. Older settings docs
    # may have these set to None / missing.
    if not (s.get("fallback_message_ar") or "").strip():
        s["fallback_message_ar"] = "اعذرني، لست متأكداً من إجابة دقيقة لهذا السؤال. سأطلب من أحد أعضاء الفريق التواصل معك قريباً."
    if not (s.get("fallback_message_en") or "").strip():
        s["fallback_message_en"] = "I'm not sure about that one. Let me have a team member follow up with you shortly."
    if not (s.get("handoff_message_ar") or "").strip():
        s["handoff_message_ar"] = "تم تحويلك لأحد أعضاء الفريق، سيتواصلون معك خلال لحظات. شكراً لصبرك! 🙏"
    if not (s.get("handoff_message_en") or "").strip():
        s["handoff_message_en"] = "Got it — connecting you to our team. Someone will be with you shortly. Thanks for your patience! 🙏"
    return s


def mask_settings_for_client(s: dict) -> dict:
    """Returns a copy of settings safe to send to the admin UI:
    replaces openai_api_key with a preview only."""
    out = dict(s)
    key = (out.get("openai_api_key") or "").strip()
    if key:
        out["openai_api_key_preview"] = (key[:6] + "…" + key[-4:]) if len(key) > 12 else "set"
    else:
        out["openai_api_key_preview"] = None
    out["openai_api_key"] = ""  # never leak the raw key
    return out


async def update_settings(db, patch: dict) -> dict:
    patch.pop("_id", None)
    # Don't overwrite the stored key when the client sends empty/null (the UI
    # masks it by default — empty means "leave it as is").
    if not (patch.get("openai_api_key") or "").strip():
        patch.pop("openai_api_key", None)
    else:
        patch["openai_api_key"] = patch["openai_api_key"].strip()
    if "llm_provider" in patch and patch["llm_provider"] not in ("emergent", "openai"):
        patch.pop("llm_provider")
    await db.ai_settings.update_one(
        {"_id": "global"},
        {"$set": patch, "$currentDate": {"updated_at": True}},
        upsert=True,
    )
    return await get_settings(db)


# ---------- Knowledge base -----------------------------------------------

async def list_knowledge(db, lang: Optional[str] = None) -> list[dict]:
    q = {}
    if lang:
        q["lang"] = lang
    docs = await db.ai_knowledge.find(q, {"_id": 0}).sort("created_at", -1).to_list(length=500)
    return docs


async def _gather_knowledge(db, lang: str) -> str:
    """Compact, model-friendly serialization of knowledge entries."""
    docs = await db.ai_knowledge.find(
        {"$or": [{"lang": lang}, {"lang": "both"}]}, {"_id": 0}
    ).to_list(length=200)
    if not docs:
        return ""
    out = []
    for d in docs:
        title = d.get("title") or ""
        content = (d.get("content") or "").strip()
        if not content:
            continue
        out.append(f"— {title}\n{content}")
    return "\n\n".join(out)


# ---------- Handoff detection --------------------------------------------

def detect_handoff_keyword(text: str) -> bool:
    if not text:
        return False
    return bool(_HANDOFF_RE.search(text))


async def is_in_handoff(db, conversation_id: int) -> bool:
    rec = await db.ai_conversations.find_one(
        {"conversation_id": conversation_id}, {"_id": 0, "handoff": 1}
    )
    return bool(rec and rec.get("handoff"))


async def set_handoff(db, conversation_id: int, on: bool = True) -> None:
    await db.ai_conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {
            "conversation_id": conversation_id,
            "handoff": on,
            "handoff_at": datetime.now(timezone.utc).isoformat() if on else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


# ---------- Language detection -------------------------------------------

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def detect_lang(text: str) -> str:
    if not text:
        return "ar"
    arabic_chars = len(_ARABIC_RE.findall(text))
    if arabic_chars >= 3 or (arabic_chars > 0 and arabic_chars / max(len(text), 1) > 0.15):
        return "ar"
    return "en"


# ---------- Reply generation ---------------------------------------------

def _build_system_prompt(settings: dict, knowledge_block: str, lang: str) -> str:
    persona = settings.get(f"persona_{lang}") or (DEFAULT_PERSONA_AR if lang == "ar" else DEFAULT_PERSONA_EN)
    fallback = settings.get(f"fallback_message_{lang}") or (
        "اعذرني، سأطلب من الفريق التواصل معك قريباً." if lang == "ar" else
        "I'll have the team follow up shortly."
    )
    header_ar = "معلومات SocialHub:"
    header_en = "SocialHub Knowledge:"
    header = header_ar if lang == "ar" else header_en
    if not knowledge_block:
        knowledge_block = "(لا توجد معلومات محدّدة بعد. اعتذر للعميل واطلب من الفريق التواصل معه قريباً.)" if lang == "ar" else "(No specific knowledge available yet. Apologize briefly and ask the team to follow up.)"

    fallback_note = (
        f"\nإذا لم تجد الجواب في المعلومات أعلاه، استخدم هذه العبارة كما هي: \"{fallback}\""
        if lang == "ar"
        else f"\nIf the answer is not in the knowledge above, use this exact line: \"{fallback}\""
    )
    return f"{persona}\n\n--- {header} ---\n{knowledge_block}\n--- /{header} ---{fallback_note}"


async def generate_reply(
    db,
    *,
    text: str,
    conversation_id: int,
    history: Optional[list[dict]] = None,
) -> tuple[Optional[str], str]:
    """
    Returns (reply, lang). reply=None means "do not send" (e.g. AI disabled,
    handoff already, LLM error). lang is what we detected.
    """
    settings = await get_settings(db)
    if not settings.get("enabled", True):
        logger.info("[AI] disabled in ai_settings — skipping reply")
        return None, "ar"

    provider = (settings.get("llm_provider") or "emergent").lower()
    lang = detect_lang(text)
    knowledge_block = await _gather_knowledge(db, lang)
    system_prompt = _build_system_prompt(settings, knowledge_block, lang)
    model = settings.get("model") or "gpt-4o"
    session_id = f"wa-{conversation_id}"

    logger.info(
        "[AI] generate_reply | provider=%s model=%s lang=%s convo=%s kb_chars=%d text_chars=%d",
        provider, model, lang, conversation_id, len(knowledge_block or ""), len(text or ""),
    )

    try:
        if provider == "openai":
            reply = await _generate_with_openai(
                settings=settings,
                system_prompt=system_prompt,
                user_text=text,
                history=history,
                model=model,
            )
        else:
            reply = await _generate_with_emergent(
                system_prompt=system_prompt,
                user_text=text,
                history=history,
                model=model,
                session_id=session_id,
            )
    except Exception as e:
        logger.exception("[AI] generation failed (%s): %s", provider, e)
        return None, lang

    if reply is None:
        return None, lang

    reply = (reply or "").strip()
    logger.info("[AI] LLM responded | chars=%d preview=%r", len(reply), reply[:120])
    if not reply:
        reply = settings.get(f"fallback_message_{lang}") or ""
    return reply, lang


async def _generate_with_emergent(
    *, system_prompt: str, user_text: str, history: Optional[list[dict]],
    model: str, session_id: str,
) -> Optional[str]:
    if not _LLM_AVAILABLE:
        logger.warning("[AI] emergentintegrations not importable — cannot use emergent provider")
        return None
    api_key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    if not api_key:
        logger.warning("[AI] EMERGENT_LLM_KEY not set — emergent provider skipped")
        return None
    chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_prompt).with_model("openai", model)
    if history:
        for h in history[-12:]:
            if h.get("role") == "user" and (h.get("content") or "").strip():
                try:
                    await chat.send_message(UserMessage(text=h["content"]))
                except Exception:
                    pass
    response = await chat.send_message(UserMessage(text=user_text))
    return response or ""


async def _generate_with_openai(
    *, settings: dict, system_prompt: str, user_text: str,
    history: Optional[list[dict]], model: str,
) -> Optional[str]:
    if not _OPENAI_SDK_AVAILABLE:
        logger.warning("[AI] openai SDK not importable — cannot use openai provider")
        return None
    key = (settings.get("openai_api_key") or "").strip() or (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        logger.warning("[AI] openai provider selected but no openai_api_key stored")
        return None
    client = AsyncOpenAI(api_key=key)
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-12:]:
            role = h.get("role")
            content = (h.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
    )
    if not resp.choices:
        return ""
    return (resp.choices[0].message.content or "").strip()


_FALLBACK_FINGERPRINT_LEN = 40  # chars used to detect fallback reuse


def _is_fallback_reply(settings: dict, reply: str, lang: str) -> bool:
    """Returns True if the bot's reply is (mostly) the configured fallback line.
    Robust to LLM paraphrasing: we check both ends of the fallback because the
    model commonly shortens the opening but keeps the distinctive ending
    ("team will follow up" / "الفريق التواصل معك")."""
    if not reply:
        return False
    fb = (settings.get(f"fallback_message_{lang}") or "").strip()
    if not fb:
        return False
    reply_lower = reply.lower()
    fb_lower = fb.lower()
    # Distinctive tail (last ~25 chars, stripped of trailing punctuation)
    tail = fb_lower.rstrip(".!؟…").strip()
    tail = tail[-25:]
    # Distinctive head (first ~20 chars, after the comma/apology)
    head = fb_lower[:20]
    if tail and tail in reply_lower:
        return True
    if head and head in reply_lower:
        return True
    # Strong-signal phrases that the LLM tends to keep when it can't answer
    signal_phrases = [
        "الفريق التواصل",
        "أعضاء الفريق",
        "اعضاء الفريق",
        "team member",
        "follow up",
        "i'm not sure",
        "لست متأكد",
    ]
    return any(p in reply_lower for p in signal_phrases)


def _normalize_for_repeat(text: str) -> str:
    """Lower + strip + collapse whitespace + drop punctuation for fuzzy repeat compare."""
    t = (text or "").lower().strip()
    t = re.sub(r"[\s\W_]+", " ", t, flags=re.UNICODE)
    return t.strip()


async def _evaluate_auto_handoff(
    db, *, settings: dict, conversation_id: int, incoming_text: str,
    bot_reply: Optional[str], lang: str,
) -> tuple[bool, Optional[str]]:
    """Decides whether to auto-handoff this conversation AFTER the bot has
    generated a reply. Returns (should_handoff, reason_for_log).

    Updates the running counters on `ai_conversations` regardless of decision.
    """
    if not settings.get("auto_handoff_enabled", True):
        return False, None

    fb_threshold = int(settings.get("auto_handoff_fallback_threshold", 2) or 2)
    rep_threshold = int(settings.get("auto_handoff_repeat_threshold", 3) or 3)
    rep_window = int(settings.get("auto_handoff_repeat_window_seconds", 120) or 120)
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - rep_window

    convo = await db.ai_conversations.find_one(
        {"conversation_id": conversation_id}, {"_id": 0}
    ) or {}

    # ---- 1) Consecutive fallback replies ----
    consecutive = int(convo.get("consecutive_fallbacks") or 0)
    is_fb = _is_fallback_reply(settings, bot_reply or "", lang)
    consecutive = consecutive + 1 if is_fb else 0

    # ---- 2) Repeated user messages within window ----
    norm = _normalize_for_repeat(incoming_text)
    recent = [m for m in (convo.get("recent_user_msgs") or []) if m.get("ts", 0) >= cutoff]
    recent.append({"norm": norm, "ts": now.timestamp()})
    # cap list size
    recent = recent[-10:]
    repeats = sum(1 for m in recent if m.get("norm") == norm and norm)

    # ---- Persist counters ----
    await db.ai_conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {
            "conversation_id": conversation_id,
            "consecutive_fallbacks": consecutive,
            "recent_user_msgs": recent,
            "updated_at": now.isoformat(),
        }},
        upsert=True,
    )

    # ---- Decide ----
    if consecutive >= fb_threshold:
        return True, f"fallback_threshold_reached ({consecutive}/{fb_threshold})"
    if repeats >= rep_threshold:
        return True, f"repeat_threshold_reached ({repeats}/{rep_threshold})"
    return False, None


async def handle_incoming(
    db,
    *,
    conversation_id: int,
    incoming_text: str,
) -> dict:
    """
    Decides what to do with an incoming message:
      - If handoff already → do nothing.
      - If handoff intent detected → mark handoff and return handoff_message to send.
      - Otherwise → generate AI reply.
      - After replying, evaluate auto-handoff triggers (repeat / fallback streak)
        and, if tripped, mark conversation handoff and append a system signal.
    Returns: {action, reply, lang, handoff, [handoff_reason], [team_note]}
    """
    settings = await get_settings(db)
    lang = detect_lang(incoming_text)

    if not settings.get("enabled", True):
        return {"action": "disabled", "reply": None, "lang": lang, "handoff": False}

    if await is_in_handoff(db, conversation_id):
        return {"action": "already_handoff", "reply": None, "lang": lang, "handoff": True}

    if detect_handoff_keyword(incoming_text):
        await set_handoff(db, conversation_id, True)
        msg = settings.get(f"handoff_message_{lang}") or ""
        team_note = (
            "🚨 تحويل تلقائي: العميل طلب التحدث مع موظف."
            if lang == "ar"
            else "🚨 Auto-handoff: customer asked to speak to a human."
        )
        return {
            "action": "handoff_triggered",
            "reply": msg,
            "lang": lang,
            "handoff": True,
            "handoff_reason": "keyword",
            "team_note": team_note,
        }

    reply, detected_lang = await generate_reply(
        db, text=incoming_text, conversation_id=conversation_id
    )
    if not reply:
        # Still evaluate handoff so we don't get stuck on a silent bot
        should_handoff, reason = await _evaluate_auto_handoff(
            db, settings=settings, conversation_id=conversation_id,
            incoming_text=incoming_text, bot_reply=None, lang=detected_lang,
        )
        if should_handoff:
            await set_handoff(db, conversation_id, True)
            msg = settings.get(f"handoff_message_{detected_lang}") or ""
            team_note = _build_team_note(reason, detected_lang)
            return {
                "action": "auto_handoff",
                "reply": msg,
                "lang": detected_lang,
                "handoff": True,
                "handoff_reason": reason,
                "team_note": team_note,
            }
        return {"action": "no_reply", "reply": None, "lang": detected_lang, "handoff": False}

    # Track activity
    await db.ai_conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {
            "conversation_id": conversation_id,
            "handoff": False,
            "last_reply_at": datetime.now(timezone.utc).isoformat(),
        }, "$inc": {"message_count": 1}},
        upsert=True,
    )

    # Evaluate auto-handoff AFTER the reply
    should_handoff, reason = await _evaluate_auto_handoff(
        db, settings=settings, conversation_id=conversation_id,
        incoming_text=incoming_text, bot_reply=reply, lang=detected_lang,
    )
    if should_handoff:
        await set_handoff(db, conversation_id, True)
        handoff_msg = settings.get(f"handoff_message_{detected_lang}") or ""
        team_note = _build_team_note(reason, detected_lang)
        # We still send the AI reply; the team note alerts the agent.
        return {
            "action": "auto_handoff_after_reply",
            "reply": reply,
            "extra_reply": handoff_msg,
            "lang": detected_lang,
            "handoff": True,
            "handoff_reason": reason,
            "team_note": team_note,
        }

    return {"action": "auto_reply", "reply": reply, "lang": detected_lang, "handoff": False}


def _build_team_note(reason: Optional[str], lang: str) -> str:
    if not reason:
        return ""
    if reason.startswith("fallback_threshold"):
        return (
            f"🚨 تحويل تلقائي: البوت لم يستطع الإجابة عدة مرات متتالية ({reason}). يرجى تولّي المحادثة."
            if lang == "ar"
            else f"🚨 Auto-handoff: bot couldn't answer ({reason}). Please take over."
        )
    if reason.startswith("repeat_threshold"):
        return (
            f"🚨 تحويل تلقائي: العميل يكرّر نفس السؤال ({reason}). يرجى تولّي المحادثة."
            if lang == "ar"
            else f"🚨 Auto-handoff: customer is repeating the same question ({reason}). Please take over."
        )
    return (
        f"🚨 تحويل تلقائي: {reason}"
        if lang == "ar"
        else f"🚨 Auto-handoff: {reason}"
    )
