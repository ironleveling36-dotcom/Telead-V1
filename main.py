"""
Main entry point.

Starts:
  • The Telethon user-account scheduler (posts ads to channels).
  • The Aiogram control bot (panel + in-chat login), if CONTROL_BOT_TOKEN is set.

The bot can run BEFORE the user has logged in — the user sets API ID/Hash
and logs in from the bot chat (🔐 Account). The scheduler simply waits and
skips cycles until a valid session exists. Designed for Railway (Docker).
"""

import asyncio
import logging
import os

from config import init_db, CONTROL_BOT_TOKEN
import credentials
from telegram_client import disconnect_client
from scheduler import scheduler_loop

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")


async def _run_control_bot():
    from control_bot import build_dispatcher
    bot, dp = build_dispatcher()
    logger.info("🤖 Control bot starting (polling)…")
    await dp.start_polling(bot, handle_signals=False)


async def main():
    init_db()

    if credentials.is_logged_in():
        logger.info("✅ Saved session found — scheduler will start posting.")
    else:
        logger.warning("⚠️ Not logged in yet. Open the bot and use 🔐 Account → Login.")

    tasks = [asyncio.create_task(scheduler_loop(), name="scheduler")]

    if CONTROL_BOT_TOKEN:
        tasks.append(asyncio.create_task(_run_control_bot(), name="control_bot"))
    else:
        logger.warning(
            "CONTROL_BOT_TOKEN not set — no control panel. "
            "Set it so you can log in and manage ads from chat."
        )

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await disconnect_client()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down.")