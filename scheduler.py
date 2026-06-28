"""
Scheduler — the heart of the ad bot.

Every cycle (re-reading the interval from the DB each time) it:
  1. Checks pause + quiet-hours guards.
  2. Loads enabled channels and enabled ads.
  3. Selects ads based on send_mode (all / rotate / random).
  4. Sends each selected ad to each enabled channel, honoring advanced
     settings (per-send delay, jitter, parse_mode, silent, link preview,
     max sends per cycle).
  5. Records send counts and timestamps.

The loop is wrapped in try/except so a failure on one cycle (or one
channel) never stops the scheduler.
"""

import asyncio
import logging
import random
from datetime import datetime

import settings
import credentials
from database import list_channels, list_ads, update_ad_sent
from telegram_client import send_message_to_channel

logger = logging.getLogger(__name__)


def _select_ads(ads: list[dict]) -> list[dict]:
    """Pick which ads to send this cycle based on send_mode."""
    mode = settings.get("send_mode")
    if not ads:
        return []
    if mode == "random":
        return [random.choice(ads)]
    if mode == "rotate":
        cursor = settings.get_rotate_cursor() % len(ads)
        chosen = ads[cursor]
        settings.set_rotate_cursor((cursor + 1) % len(ads))
        return [chosen]
    return ads  # "all"


async def run_one_cycle() -> dict:
    """Send the selected ads to every enabled channel once. Returns stats."""
    stats = {"channels": 0, "ads": 0, "sent": 0, "failed": 0, "skipped": None}

    if settings.get("paused"):
        stats["skipped"] = "paused"
        logger.info("⏸️ Scheduler paused — skipping cycle.")
        return stats

    if not credentials.is_logged_in():
        stats["skipped"] = "not_logged_in"
        logger.info("🔑 Not logged in yet — use 🔐 Account in the bot. Skipping cycle.")
        return stats

    hour = datetime.now().astimezone().hour
    if settings.in_quiet_hours(hour):
        stats["skipped"] = "quiet_hours"
        logger.info("🌙 Quiet hours (hour=%d) — skipping cycle.", hour)
        return stats

    channels = list_channels(enabled_only=True)
    ads = _select_ads(list_ads(enabled_only=True))
    stats["channels"], stats["ads"] = len(channels), len(ads)

    if not channels:
        logger.warning("No enabled channels — skipping cycle.")
        return stats
    if not ads:
        logger.warning("No enabled ads — skipping cycle.")
        return stats

    # Advanced send options
    parse_mode = settings.get("parse_mode")
    silent = settings.get("silent")
    link_preview = settings.get("link_preview")
    per_delay = settings.get("per_send_delay")
    jitter = settings.get("jitter_seconds")
    max_per_cycle = settings.get("max_per_cycle")

    total = 0
    for ad in ads:
        for ch in channels:
            if max_per_cycle and total >= max_per_cycle:
                logger.info("Reached max_per_cycle=%d — stopping cycle early.", max_per_cycle)
                return stats

            if jitter > 0:
                await asyncio.sleep(random.uniform(0, jitter))

            ok, detail = await send_message_to_channel(
                ch["channel_id"], ad["content"],
                parse_mode=parse_mode, silent=silent, link_preview=link_preview,
            )
            total += 1
            if ok:
                stats["sent"] += 1
                update_ad_sent(ad["id"])
            else:
                stats["failed"] += 1
                logger.error("Ad #%s -> %s failed: %s", ad["id"], ch["channel_id"], detail)

            await asyncio.sleep(per_delay)

    logger.info(
        "Cycle complete: %d sent, %d failed across %d channels.",
        stats["sent"], stats["failed"], stats["channels"],
    )
    return stats


async def scheduler_loop():
    """Run forever, sleeping `interval_minutes` between cycles."""
    logger.info("📡 Scheduler started.")
    while True:
        try:
            await run_one_cycle()
        except Exception as e:
            logger.exception("Cycle crashed (continuing): %s", e)

        interval = settings.get("interval_minutes")
        logger.info("😴 Sleeping %d minute(s) until next cycle.", interval)
        try:
            await asyncio.sleep(max(1, interval) * 60)
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled — shutting down.")
            break