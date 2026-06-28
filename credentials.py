"""
Credentials store.

Holds the Telegram API ID / API Hash / phone / session string so the user
can set or change them ANYTIME from inside the bot (via /login or the
🔐 Account panel) — no redeploy, no editing env vars.

Priority: values saved in the DB win; otherwise we fall back to env vars
(handy for first boot / seeding). Saving from the bot persists to SQLite,
so on Railway just attach a volume and the login survives restarts.
"""

import os
from config import get_setting, set_setting

# DB setting keys
K_API_ID = "cred_api_id"
K_API_HASH = "cred_api_hash"
K_PHONE = "cred_phone"
K_SESSION = "cred_session"
K_OWNER = "owner_user_id"


def _db_or_env(key: str, env: str, default: str = "") -> str:
    val = get_setting(key, "")
    if val:
        return val
    return os.environ.get(env, default)


# ── getters ─────────────────────────────────────────────────────────

def get_api_id() -> int:
    raw = _db_or_env(K_API_ID, "TELEGRAM_API_ID", "0")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def get_api_hash() -> str:
    return _db_or_env(K_API_HASH, "TELEGRAM_API_HASH", "")


def get_phone() -> str:
    return _db_or_env(K_PHONE, "TELEGRAM_PHONE", "")


def get_session() -> str:
    return _db_or_env(K_SESSION, "TELEGRAM_SESSION", "")


# ── setters ─────────────────────────────────────────────────────────

def set_api_id(value: int | str):
    set_setting(K_API_ID, str(value))


def set_api_hash(value: str):
    set_setting(K_API_HASH, value.strip())


def set_phone(value: str):
    set_setting(K_PHONE, value.strip())


def set_session(value: str):
    set_setting(K_SESSION, value)


def clear_session():
    set_setting(K_SESSION, "")


# ── status helpers ──────────────────────────────────────────────────

def is_configured() -> bool:
    """True once API ID + Hash are present."""
    return bool(get_api_id()) and bool(get_api_hash())


def is_logged_in() -> bool:
    """True once a session string exists."""
    return bool(get_session())


def status_line() -> str:
    api = "✅" if is_configured() else "❌"
    login = "✅" if is_logged_in() else "❌"
    phone = get_phone() or "—"
    return f"API keys: {api}   Logged in: {login}   Phone: {phone}"


# ── owner (single-user ownership claim) ─────────────────────────────

def get_owner() -> int:
    raw = get_setting(K_OWNER, "") or os.environ.get("ADMIN_USER_ID", "0")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def set_owner(user_id: int):
    set_setting(K_OWNER, str(user_id))


def claim_owner_if_unset(user_id: int) -> bool:
    """If no owner yet, the first user to /start becomes the owner."""
    if get_owner() == 0:
        set_owner(user_id)
        return True
    return False