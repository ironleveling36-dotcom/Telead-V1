"""
In-bot interactive login.

Lets the user log in to their Telegram account ENTIRELY from the bot chat:
  1. start_login()    -> sends the login code to their Telegram app
  2. submit_code()    -> signs in; may report that 2FA is required
  3. submit_password()-> completes 2FA sign-in

On success the StringSession + credentials are saved to the DB and the
main sending client is reset so it picks up the new session immediately.

A temporary Telethon client is kept alive per-user between steps (the whole
app is one process, so an in-memory dict is fine).
"""

import logging

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

import credentials
import telegram_client

logger = logging.getLogger(__name__)

# user_id -> {"client", "phone", "hash", "api_id", "api_hash"}
_pending: dict[int, dict] = {}


async def start_login(user_id: int, api_id: int, api_hash: str, phone: str) -> tuple[bool, str]:
    """Send a login code to the user's phone. Returns (ok, message)."""
    # Clean up any half-finished attempt.
    await cancel(user_id)
    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        sent = await client.send_code_request(phone)
        _pending[user_id] = {
            "client": client,
            "phone": phone,
            "hash": sent.phone_code_hash,
            "api_id": api_id,
            "api_hash": api_hash,
        }
        return True, "📲 A login code was sent to your Telegram app. Send it here (e.g. 12345)."
    except errors.PhoneNumberInvalidError:
        return False, "❌ Invalid phone number. Use international format like +1234567890."
    except errors.ApiIdInvalidError:
        return False, "❌ Invalid API ID / API Hash. Double-check them from my.telegram.org."
    except Exception as e:
        return False, f"❌ Could not start login: {e}"


async def submit_code(user_id: int, code: str) -> tuple[str, str]:
    """
    Try to sign in with the code.
    Returns (status, message) where status is 'ok' | '2fa' | 'error'.
    """
    ctx = _pending.get(user_id)
    if not ctx:
        return "error", "No login in progress. Start again with the Account menu."
    client: TelegramClient = ctx["client"]
    try:
        await client.sign_in(phone=ctx["phone"], code=code.strip(), phone_code_hash=ctx["hash"])
        return _finish(user_id, ctx)
    except errors.SessionPasswordNeededError:
        return "2fa", "🔐 Two-step verification is on. Send your password."
    except errors.PhoneCodeInvalidError:
        return "error", "❌ Wrong code. Try sending it again."
    except errors.PhoneCodeExpiredError:
        await cancel(user_id)
        return "error", "❌ Code expired. Start the login again."
    except Exception as e:
        return "error", f"❌ Sign-in failed: {e}"


async def submit_password(user_id: int, password: str) -> tuple[str, str]:
    """Complete a 2FA sign-in. Returns (status, message)."""
    ctx = _pending.get(user_id)
    if not ctx:
        return "error", "No login in progress. Start again."
    client: TelegramClient = ctx["client"]
    try:
        await client.sign_in(password=password)
        return _finish(user_id, ctx)
    except errors.PasswordHashInvalidError:
        return "error", "❌ Wrong password. Try again."
    except Exception as e:
        return "error", f"❌ 2FA failed: {e}"


def _finish(user_id: int, ctx: dict) -> tuple[str, str]:
    """Save session + credentials, drop the temp client."""
    client: TelegramClient = ctx["client"]
    session_str = client.session.save()
    credentials.set_api_id(ctx["api_id"])
    credentials.set_api_hash(ctx["api_hash"])
    credentials.set_phone(ctx["phone"])
    credentials.set_session(session_str)
    # Disconnect the temp client (don't await — caller may not be async-safe here)
    try:
        import asyncio
        asyncio.create_task(client.disconnect())
    except Exception:
        pass
    _pending.pop(user_id, None)
    # Force the main sender to rebuild with the new session.
    telegram_client.reset_client_sync()
    logger.info("User %s logged in successfully.", user_id)
    return "ok", "✅ Logged in! Your account is now connected and ads will start posting."


async def cancel(user_id: int):
    """Abort and clean up an in-progress login."""
    ctx = _pending.pop(user_id, None)
    if ctx:
        try:
            await ctx["client"].disconnect()
        except Exception:
            pass


def in_progress(user_id: int) -> bool:
    return user_id in _pending