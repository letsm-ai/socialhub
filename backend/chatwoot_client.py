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
    return {
        "Content-Type": "application/json",
        "api_access_token": os.environ["CHATWOOT_PLATFORM_API_KEY"],
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
    Returns {"account_id": int, "user_id": int}.
    """
    company = user_doc.get("company_name") or user_doc.get("name") or "SocialHub Client"
    acc = await create_account(name=company)
    account_id = acc["id"]
    cw_user = await create_user(name=user_doc["name"], email=user_doc["email"])
    cw_user_id = cw_user["id"]
    try:
        await link_user_to_account(account_id, cw_user_id, role="administrator")
    except ChatwootError as e:
        # Roll back partial state on link failure
        logger.warning("Linking failed, rolling back account %s: %s", account_id, e)
        try:
            await delete_account(account_id)
        except Exception:
            pass
        raise
    return {"account_id": account_id, "user_id": cw_user_id}
