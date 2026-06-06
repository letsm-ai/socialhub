"""
Chatwoot Platform API client.
Reference: https://developers.chatwoot.com/contributing-guide/chatwoot-platform-apis
"""
import os
import secrets
import string
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class ChatwootError(Exception):
    pass


def _base() -> str:
    return os.environ["CHATWOOT_URL"].rstrip("/")


def _headers() -> dict:
    # Prefer the new `CHATWOOT_PLATFORM_TOKEN` (current Platform App) — fall back
    # to legacy `CHATWOOT_PLATFORM_API_KEY` for backwards compatibility.
    token = (
        os.environ.get("CHATWOOT_PLATFORM_TOKEN")
        or os.environ.get("CHATWOOT_PLATFORM_API_KEY")
        or ""
    ).strip()
    if not token:
        raise ChatwootError("CHATWOOT_PLATFORM_TOKEN (or CHATWOOT_PLATFORM_API_KEY) not configured")
    return {
        "Content-Type": "application/json",
        "api_access_token": token,
    }


def _gen_password(n: int = 20) -> str:
    """Generate a strong password that satisfies Chatwoot's policy:
    at least 1 lowercase, 1 uppercase, 1 digit, 1 symbol."""
    import random
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Guarantee one of each required class
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    rest = [secrets.choice(alphabet) for _ in range(max(0, n - len(required)))]
    pw = required + rest
    random.SystemRandom().shuffle(pw)
    return "".join(pw)


async def create_account(name: str, locale: str = "en") -> dict:
    """POST /platform/api/v1/accounts -> { id, name, ... }"""
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(f"{_base()}/platform/api/v1/accounts",
                          headers=_headers(),
                          json={"name": name, "locale": locale})
        if r.status_code >= 400:
            raise ChatwootError(f"create_account {r.status_code}: {r.text}")
        return r.json()


async def create_user(name: str, email: str, password: Optional[str] = None) -> dict:
    """POST /platform/api/v1/users -> { id, name, email, access_token, ... }"""
    payload = {
        "name": name,
        "email": email.lower().strip(),
        "password": password or _gen_password(),
    }
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(f"{_base()}/platform/api/v1/users",
                          headers=_headers(), json=payload)
        if r.status_code >= 400:
            raise ChatwootError(f"create_user {r.status_code}: {r.text}")
        return r.json()


async def link_user_to_account(account_id: int, user_id: int, role: str = "administrator") -> dict:
    """POST /platform/api/v1/accounts/{account_id}/account_users"""
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(
            f"{_base()}/platform/api/v1/accounts/{account_id}/account_users",
            headers=_headers(),
            json={"user_id": user_id, "role": role},
        )
        if r.status_code >= 400:
            raise ChatwootError(f"link_user {r.status_code}: {r.text}")
        return r.json()


async def get_user(user_id: int) -> dict:
    """GET /platform/api/v1/users/{user_id} -> { id, name, email, access_token, ... }
    Useful to recover an access_token for a user we provisioned previously but
    whose token we never stored (legacy records)."""
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.get(f"{_base()}/platform/api/v1/users/{user_id}",
                         headers=_headers())
        if r.status_code >= 400:
            raise ChatwootError(f"get_user {r.status_code}: {r.text}")
        return r.json()


async def get_sso_url(user_id: int) -> str:
    """GET /platform/api/v1/users/{user_id}/login -> { url }"""
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.get(f"{_base()}/platform/api/v1/users/{user_id}/login",
                         headers=_headers())
        if r.status_code >= 400:
            raise ChatwootError(f"sso {r.status_code}: {r.text}")
        return r.json().get("url", "")


async def delete_account(account_id: int) -> None:
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.delete(f"{_base()}/platform/api/v1/accounts/{account_id}",
                            headers=_headers())
        if r.status_code >= 400 and r.status_code != 404:
            raise ChatwootError(f"delete_account {r.status_code}: {r.text}")


async def provision_for_user(user_doc: dict) -> dict:
    """
    Idempotent: provisions a Chatwoot account + user for the given SocialHub user.
    Returns {"account_id": int, "user_id": int, "access_token": str}.

    Role: clients are linked as `agent` (not administrator) so they can NEVER
    create or modify inboxes inside Chatwoot. WhatsApp linking, integrations,
    and account settings are managed exclusively from SocialHub.
    """
    company = user_doc.get("company_name") or user_doc.get("name") or "SocialHub Client"
    acc = await create_account(name=company)
    account_id = acc["id"]
    cw_user = await create_user(name=user_doc["name"], email=user_doc["email"])
    cw_user_id = cw_user["id"]
    cw_access_token = cw_user.get("access_token") or ""
    try:
        await link_user_to_account(account_id, cw_user_id, role="agent")
    except ChatwootError as e:
        # Roll back partial state on link failure
        logger.warning("Linking failed, rolling back account %s: %s", account_id, e)
        try:
            await delete_account(account_id)
        except Exception:
            pass
        raise
    return {"account_id": account_id, "user_id": cw_user_id, "access_token": cw_access_token}


async def set_user_role(account_id: int, user_id: int, role: str = "agent") -> dict:
    """Change an existing user's role inside an account.

    Chatwoot's Platform API has no PATCH endpoint for `account_users` — instead
    we DELETE the existing link and POST a new one with the desired role.
    Both calls are idempotent on Chatwoot's side.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1) Remove existing link (ignore 404 — user might not be linked yet)
        del_resp = await client.request(
            "DELETE",
            f"{_base()}/platform/api/v1/accounts/{account_id}/account_users",
            headers=_headers(),
            json={"user_id": user_id},
        )
        if del_resp.status_code >= 400 and del_resp.status_code != 404:
            # 422 typically means "not found" too — proceed anyway
            logger.warning(
                "set_user_role: unlink returned %s: %s", del_resp.status_code, del_resp.text[:200],
            )

        # 2) Recreate the link with the new role
        add_resp = await client.post(
            f"{_base()}/platform/api/v1/accounts/{account_id}/account_users",
            headers=_headers(),
            json={"user_id": user_id, "role": role},
        )
        if add_resp.status_code >= 400:
            raise ChatwootError(
                f"set_user_role re-link {add_resp.status_code}: {add_resp.text[:300]}",
            )
        return add_resp.json() if add_resp.text else {"ok": True, "role": role}


# ===========================================================
# Application API (uses per-user access_token)
# Used to seed demo data into a client's Chatwoot workspace.
# ===========================================================
def _app_headers(user_access_token: str) -> dict:
    return {"Content-Type": "application/json", "api_access_token": user_access_token}


async def create_api_inbox(account_id: int, user_token: str, name: str, webhook_url: str = "") -> dict:
    """POST /api/v1/accounts/{aid}/inboxes — creates an API channel inbox."""
    payload = {
        "name": name,
        "channel": {"type": "api", "webhook_url": webhook_url or ""},
    }
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(
            f"{_base()}/api/v1/accounts/{account_id}/inboxes",
            headers=_app_headers(user_token),
            json=payload,
        )
        if r.status_code >= 400:
            raise ChatwootError(f"create_api_inbox {r.status_code}: {r.text}")
        return r.json()


async def create_contact(account_id: int, user_token: str, inbox_id: int, name: str, phone: str) -> dict:
    """POST /api/v1/accounts/{aid}/contacts — creates a contact (also assigns to inbox)."""
    payload = {
        "name": name,
        "phone_number": phone,
        "inbox_id": inbox_id,
    }
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(
            f"{_base()}/api/v1/accounts/{account_id}/contacts",
            headers=_app_headers(user_token),
            json=payload,
        )
        if r.status_code >= 400:
            raise ChatwootError(f"create_contact {r.status_code}: {r.text}")
        return r.json()


async def create_conversation(account_id: int, user_token: str, inbox_id: int, contact_id: int,
                              source_id: str, message: str) -> dict:
    """POST /api/v1/accounts/{aid}/conversations — creates a conversation with the first incoming message."""
    payload = {
        "source_id": source_id,
        "inbox_id": inbox_id,
        "contact_id": contact_id,
        "status": "open",
        "message": {"content": message, "message_type": "incoming"},
    }
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(
            f"{_base()}/api/v1/accounts/{account_id}/conversations",
            headers=_app_headers(user_token),
            json=payload,
        )
        if r.status_code >= 400:
            raise ChatwootError(f"create_conversation {r.status_code}: {r.text}")
        return r.json()


async def post_message(account_id: int, user_token: str, conversation_id: int,
                       content: str, incoming: bool = True, private: bool = False) -> dict:
    """POST /api/v1/accounts/{aid}/conversations/{cid}/messages — append a message to existing conversation.

    When private=True, the message is recorded as an internal note (visible only
    to agents) and Chatwoot will fire its webhook with private=true, which our
    outgoing handler ignores. Use this for AI/bot replies so they don't loop
    back through the Chatwoot → WhatsApp pipeline.
    """
    payload = {
        "content": content,
        "message_type": "incoming" if incoming else "outgoing",
        "private": bool(private),
    }
    async with httpx.AsyncClient(timeout=20.0) as cx:
        r = await cx.post(
            f"{_base()}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages",
            headers=_app_headers(user_token),
            json=payload,
        )
        if r.status_code >= 400:
            raise ChatwootError(f"post_message {r.status_code}: {r.text}")
        return r.json()


async def seed_demo_conversations(account_id: int, user_token: str, lang: str = "ar") -> dict:
    """
    Creates a demo inbox + 3 sample contacts + 3 conversations with realistic messages.
    Returns a summary dict. Idempotent-ish: if the inbox name already exists, errors are
    swallowed and a partial result is returned.
    """
    inbox_name = "WhatsApp Demo (+968 9999 8888)"
    try:
        inbox = await create_api_inbox(account_id, user_token, name=inbox_name)
        inbox_id = inbox["id"]
    except ChatwootError as e:
        logger.warning("seed_demo_conversations: inbox creation failed: %s", e)
        return {"ok": False, "error": str(e)}

    scenarios_ar = [
        {
            "name": "فاطمة الكندي",
            "phone": "+96891234567",
            "first": "السلام عليكم، عندكم الفستان الأخضر المقاس M؟",
            "agent_reply": "وعليكم السلام، نعم متوفر! تفضلي رابط المنتج: https://example.com/p/123",
            "customer_reply": "ممتاز، كم سعر الشحن لمسقط؟",
        },
        {
            "name": "سالم الحارثي",
            "phone": "+96892345678",
            "first": "كم سعر الشحن للسلطنة؟ وكم يستغرق التوصيل؟",
            "agent_reply": "أهلاً سالم، الشحن لمسقط ٢ ريال وللولايات ٣ ريال. التوصيل ٢-٤ أيام عمل.",
            "customer_reply": "تمام، شكراً.",
        },
        {
            "name": "مريم البلوشية",
            "phone": "+96893456789",
            "first": "أنا اشتريت طلب رقم #4528 ولين الحين ما وصل، صار يومين",
            "agent_reply": "أعتذر مريم، خليني أتابع مع الشحن وأرجعلك خلال ١٠ دقائق.",
            "customer_reply": None,
        },
    ]
    scenarios_en = [
        {
            "name": "Fatima Al Kindi",
            "phone": "+96891234567",
            "first": "Hi, do you have the green dress in size M?",
            "agent_reply": "Hello! Yes, available. Here's the link: https://example.com/p/123",
            "customer_reply": "Great, what's shipping to Muscat?",
        },
        {
            "name": "Salim Al Harthi",
            "phone": "+96892345678",
            "first": "How much is shipping to Oman and how long does it take?",
            "agent_reply": "Hi Salim, OMR 2 to Muscat, OMR 3 to wilayats. Delivery 2-4 business days.",
            "customer_reply": "Perfect, thanks!",
        },
        {
            "name": "Maryam Al Balushi",
            "phone": "+96893456789",
            "first": "I placed order #4528 two days ago but it hasn't arrived yet.",
            "agent_reply": "Sorry Maryam, let me check with the courier and get back to you in 10 minutes.",
            "customer_reply": None,
        },
    ]
    scenarios = scenarios_ar if lang == "ar" else scenarios_en
    summary = {"ok": True, "inbox_id": inbox_id, "conversations": []}
    for idx, sc in enumerate(scenarios):
        try:
            contact = await create_contact(account_id, user_token, inbox_id, sc["name"], sc["phone"])
            # The contact payload returns a contact_inboxes array; we need its source_id
            contact_data = contact.get("payload", {}).get("contact", {})
            contact_id = contact_data.get("id")
            source_id = None
            for ci in contact_data.get("contact_inboxes", []):
                if ci.get("inbox", {}).get("id") == inbox_id:
                    source_id = ci.get("source_id")
                    break
            if not contact_id:
                continue
            conv = await create_conversation(
                account_id, user_token, inbox_id, contact_id,
                source_id or f"demo-{idx}", sc["first"],
            )
            conv_id = conv.get("id")
            if conv_id and sc.get("agent_reply"):
                await post_message(account_id, user_token, conv_id, sc["agent_reply"], incoming=False)
            if conv_id and sc.get("customer_reply"):
                await post_message(account_id, user_token, conv_id, sc["customer_reply"], incoming=True)
            summary["conversations"].append({"contact": sc["name"], "id": conv_id})
        except Exception as e:
            logger.warning("seed_demo scenario %s failed: %s", idx, e)
            summary["conversations"].append({"contact": sc["name"], "error": str(e)})

    return summary


# Random demo messages for "simulate new message" feature
_DEMO_INCOMING_MESSAGES_AR = [
    {"name": "خالد العبري", "phone": "+96894567890", "msg": "السلام عليكم، عندكم خصومات على المنتجات الجديدة؟"},
    {"name": "نورا الزدجالية", "phone": "+96895678901", "msg": "كم سعر العباية رقم 7؟ وهل يوجد لون كحلي؟"},
    {"name": "ياسر السيابي", "phone": "+96896789012", "msg": "كنت طلبت طلب أمس، متى يتم الشحن؟"},
    {"name": "هدى الراشدية", "phone": "+96897890123", "msg": "أبغى أرجّع منتج، كيف العملية؟"},
    {"name": "ماجد الحبسي", "phone": "+96898901234", "msg": "هل توصلون لصلالة؟ وما تكلفة الشحن؟"},
    {"name": "ريم الكلباني", "phone": "+96899012345", "msg": "السلام عليكم، عندكم متجر فيزيكال؟"},
    {"name": "أحمد البوسعيدي", "phone": "+96894123987", "msg": "أبغى أكمل طلب رقم #7821، كيف أدفع؟"},
    {"name": "سارة الكنود", "phone": "+96895234876", "msg": "Hi, do you ship internationally?"},
]


async def simulate_incoming_message(account_id: int, user_token: str, inbox_id: int) -> dict:
    """
    Picks a random demo persona and either:
      (a) creates a brand-new contact + conversation with their first message, OR
      (b) appends a new incoming message to an existing demo conversation.
    Returns {ok, conversation_id, contact_name, message}.
    """
    import random
    persona = random.choice(_DEMO_INCOMING_MESSAGES_AR)

    try:
        # Always create a NEW contact + conversation so the agent sees a fresh notification
        suffix = secrets.token_hex(3)
        contact = await create_contact(
            account_id, user_token, inbox_id,
            persona["name"], persona["phone"][:-3] + suffix[:3],
        )
        contact_data = contact.get("payload", {}).get("contact", {})
        contact_id = contact_data.get("id")
        source_id = None
        for ci in contact_data.get("contact_inboxes", []):
            if ci.get("inbox", {}).get("id") == inbox_id:
                source_id = ci.get("source_id")
                break
        if not contact_id:
            raise ChatwootError("contact creation returned no id")
        conv = await create_conversation(
            account_id, user_token, inbox_id, contact_id,
            source_id or f"sim-{suffix}", persona["msg"],
        )
        return {
            "ok": True,
            "conversation_id": conv.get("id"),
            "contact_name": persona["name"],
            "message": persona["msg"],
        }
    except Exception as e:
        logger.warning("simulate_incoming_message failed: %s", e)
        return {"ok": False, "error": str(e)}
