"""
Configuration module for the Telegram Ad Bot.

All persistent settings (channels, ads, intervals) live in SQLite.
Telegram credentials are read from environment variables so the project
can be deployed to Railway / Docker without hard-coding secrets.

Two login modes are supported:
  1. Local interactive login (phone + code)  -> creates a .session file
  2. Headless StringSession (for Railway)     -> set TELEGRAM_SESSION env var

Generate the StringSession once locally with:  python login.py
"""

import os
import sqlite3
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()  # load a local .env if present (ignored in prod)
except Exception:
    pass

# ── Database ────────────────────────────────────────────────────────
# On Railway, mount a volume at /data and set DB_PATH=/data/ad_bot.db
DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "ad_bot.db"))

# ── Telegram credentials (from env / secrets) ──────────────────────
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0") or "0")
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
PHONE = os.environ.get("TELEGRAM_PHONE", "")          # e.g. +1234567890

# Headless session string (preferred for Railway). If empty we fall back
# to a local .session file created by interactive login.
STRING_SESSION = os.environ.get("TELEGRAM_SESSION", "")

# File-based session name (used only for local/interactive login)
SESSION_NAME = str(Path(__file__).parent / "telethon_session")

# Optional: a control bot token so you can manage ads from Telegram chat.
# Leave empty to disable the control interface.
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN", "")
# Your numeric Telegram user ID — only this user may control the bot.
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "0") or "0")

# ── Defaults ────────────────────────────────────────────────────────
DEFAULT_INTERVAL_MINUTES = 5


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection with row factory + sane pragmas."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id  TEXT    NOT NULL UNIQUE,
            title       TEXT    DEFAULT '',
            enabled     INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS ads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT    NOT NULL,
            enabled     INTEGER DEFAULT 1,
            send_count  INTEGER DEFAULT 0,
            last_sent   TEXT,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO settings (key, value)
            VALUES ('interval_minutes', '5');
    """)
    conn.commit()
    conn.close()
    # Populate any advanced settings that don't exist yet.
    try:
        import settings as _settings
        _settings.ensure_defaults()
    except Exception:
        pass


def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_interval_minutes() -> int:
    return int(get_setting("interval_minutes", str(DEFAULT_INTERVAL_MINUTES)))


def set_interval_minutes(minutes: int):
    set_setting("interval_minutes", str(max(1, minutes)))


def validate_credentials():
    """Raise a clear error early if required credentials are missing."""
    missing = []
    if not API_ID:
        missing.append("TELEGRAM_API_ID")
    if not API_HASH:
        missing.append("TELEGRAM_API_HASH")
    if not STRING_SESSION and not PHONE:
        missing.append("TELEGRAM_SESSION (or TELEGRAM_PHONE for local login)")
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )