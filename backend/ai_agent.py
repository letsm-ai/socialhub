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
        }
    return s


async def update_settings(db, patch: dict) -> dict:
    patch.pop("_id", None)
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
    if not _LLM_AVAILABLE:
        logger.warning("[AI] generate_reply skipped — emergentintegrations not importable")
        return None, "ar"

    api_key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    if not api_key:
        logger.warning("[AI] EMERGENT_LLM_KEY not set — AI reply skipped")
        return None, "ar"

    settings = await get_settings(db)
    if not settings.get("enabled", True):
        logger.info("[AI] disabled in ai_settings — skipping reply")
        return None, "ar"

    lang = detect_lang(text)
    knowledge_block = await _gather_knowledge(db, lang)
    system_prompt = _build_system_prompt(settings, knowledge_block, lang)
    model = settings.get("model") or "gpt-4o"
    logger.info(
        "[AI] generate_reply | model=%s lang=%s convo=%s kb_chars=%d text_chars=%d",
        model, lang, conversation_id, len(knowledge_block or ""), len(text or ""),
    )

    session_id = f"wa-{conversation_id}"
    try:
        chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_prompt).with_model("openai", model)
        # Replay last few messages for context (last 6 exchanges = 12 msgs)
        if history:
            for h in history[-12:]:
                role = h.get("role")
                content = h.get("content") or ""
                if role == "user" and content.strip():
                    try:
                        await chat.send_message(UserMessage(text=content))
                    except Exception:
                        # If history send fails, continue — we'll still answer the live message
                        pass
        response = await chat.send_message(UserMessage(text=text))
        reply = (response or "").strip()
        logger.info("[AI] LLM responded | chars=%d preview=%r", len(reply), reply[:120])
        if not reply:
            reply = settings.get(f"fallback_message_{lang}") or ""
        return reply, lang
    except Exception as e:
        logger.exception("[AI] generation failed: %s", e)
        return None, lang


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
    Returns: {action, reply, lang, handoff}
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
        return {"action": "handoff_triggered", "reply": msg, "lang": lang, "handoff": True}

    reply, detected_lang = await generate_reply(
        db, text=incoming_text, conversation_id=conversation_id
    )
    if not reply:
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
    return {"action": "auto_reply", "reply": reply, "lang": detected_lang, "handoff": False}
