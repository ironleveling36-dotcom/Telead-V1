"""
Telegram client wrapper using Telethon.

Sends messages as the USER'S OWN account. Credentials (API ID/Hash and the
session) are read from the credentials store, which the user can change
ANYTIME from the bot — so this module always rebuilds the client when the
saved credentials change.
"""

import asyncio
import logging

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

import credentials

logger = logging.getLogger(__name__)

_client: TelegramClient | None = None
_client_session: str = ""   # session string the current _client was built with
_lock = asyncio.Lock()


def reset_client_sync():
    """Mark the client for rebuild (called after a re-login / cred change)."""
    global _client, _client_session
    old = _client
    _client, _client_session = None, ""
    if old is not None:
        try:
            asyncio.create_task(old.disconnect())
        except Exception:
            pass


async def get_client() -> TelegramClient:
    """Return the shared, connected & authorized TelegramClient."""
    global _client, _client_session
    async with _lock:
        if not credentials.is_configured():
            raise RuntimeError("API ID/Hash not set. Open the bot and use 🔐 Account → Login.")
        session = credentials.get_session()
        if not session:
            raise RuntimeError("Not logged in. Open the bot and use 🔐 Account → Login.")

        # Rebuild if session changed (user re-logged in) or first use.
        if _client is None or _client_session != session:
            if _client is not None:
                try:
                    await _client.disconnect()
                except Exception:
                    pass
            _client = TelegramClient(
                StringSession(session), credentials.get_api_id(), credentials.get_api_hash()
            )
            _client_session = session

        if not _client.is_connected():
            await _client.connect()
        if not await _client.is_user_authorized():
            raise RuntimeError("Session invalid/expired. Re-login via 🔐 Account in the bot.")
        return _client


def _parse_mode_arg(parse_mode: str):
    pm = (parse_mode or "none").lower()
    if pm in ("md", "markdown"):
        return "md"
    if pm == "html":
        return "html"
    return None


async def send_message_to_channel(
    channel_id: str,
    text: str,
    *,
    parse_mode: str = "none",
    silent: bool = False,
    link_preview: bool = True,
) -> tuple[bool, str]:
    """Send one message to a channel. Returns (success, detail)."""
    try:
        client = await get_client()
    except Exception as e:
        return False, f"client error: {e}"

    entity: object = channel_id
    if isinstance(channel_id, str) and channel_id.lstrip("-").isdigit():
        entity = int(channel_id)

    kwargs = dict(
        message=text,
        parse_mode=_parse_mode_arg(parse_mode),
        silent=silent,
        link_preview=link_preview,
    )

    try:
        await client.send_message(entity=entity, **kwargs)
        logger.info("✅ Sent to %s", channel_id)
        return True, "sent"

    except errors.FloodWaitError as e:
        wait = e.seconds + 2
        logger.warning("⏳ FloodWait %ss on %s — sleeping then retrying", e.seconds, channel_id)
        await asyncio.sleep(wait)
        try:
            await client.send_message(entity=entity, **kwargs)
            return True, "sent after flood wait"
        except Exception as retry_err:
            return False, f"retry failed: {retry_err}"

    except errors.ChannelPrivateError:
        return False, "channel private / you were removed"
    except errors.ChatWriteForbiddenError:
        return False, "write forbidden in this channel"
    except errors.UsernameNotOccupiedError:
        return False, "username does not exist"
    except (ValueError, errors.PeerIdInvalidError):
        return False, "invalid channel id — join/open the channel first so it's cached"
    except Exception as e:
        logger.error("❌ Send failed %s: %s (%s)", channel_id, e, type(e).__name__)
        return False, f"{type(e).__name__}: {e}"


async def disconnect_client():
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        logger.info("Telegram client disconnected.")