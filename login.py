"""
One-time login helper.

Run this LOCALLY (it needs interactive input for the SMS/app code):

    python login.py

It logs into Telegram with your phone number and prints a StringSession.
Copy that string and set it on Railway as the TELEGRAM_SESSION env var so
the bot can run headless (no interactive login) in production.
"""

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH, PHONE


async def main():
    if not API_ID or not API_HASH:
        raise SystemExit("Set TELEGRAM_API_ID and TELEGRAM_API_HASH first (e.g. in .env).")

    print("Logging in to Telegram… you'll be asked for the code sent to your app.")
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start(phone=PHONE or input("Phone (e.g. +123...): ").strip())
        me = await client.get_me()
        session_str = client.session.save()
        print("\n" + "=" * 70)
        print(f"✅ Logged in as: {me.first_name} (@{me.username}) id={me.id}")
        print("=" * 70)
        print("\nYour StringSession (KEEP IT SECRET — it's full account access):\n")
        print(session_str)
        print("\nSet it on Railway as:  TELEGRAM_SESSION=<the string above>\n")


if __name__ == "__main__":
    asyncio.run(main())