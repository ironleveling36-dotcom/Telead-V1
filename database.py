"""
Database access layer — all CRUD operations for channels, ads, and settings.

Every function opens and closes its own short-lived connection so the
module is safe to call from async code without locking concerns.
"""

from config import get_db


# ── Channels ────────────────────────────────────────────────────────

def add_channel(channel_id: str, title: str = "") -> dict:
    """Insert a channel if not already present. Returns the row as dict."""
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO channels (channel_id, title) VALUES (?, ?)",
        (channel_id, title),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM channels WHERE channel_id=?", (channel_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def remove_channel(channel_id: str) -> bool:
    """Delete a channel. Returns True if a row was removed."""
    conn = get_db()
    cur = conn.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def list_channels(enabled_only: bool = False) -> list[dict]:
    """Return all (or only enabled) channels as a list of dicts."""
    conn = get_db()
    if enabled_only:
        rows = conn.execute(
            "SELECT * FROM channels WHERE enabled=1 ORDER BY id"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM channels ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_channel(channel_id: str, enabled: bool) -> bool:
    """Enable or disable a channel. Returns True if updated."""
    conn = get_db()
    cur = conn.execute(
        "UPDATE channels SET enabled=? WHERE channel_id=?",
        (1 if enabled else 0, channel_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Ads ─────────────────────────────────────────────────────────────

def add_ad(content: str) -> dict:
    """Insert a new advertisement. Returns the row as dict."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO ads (content) VALUES (?)", (content,)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM ads WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def remove_ad(ad_id: int) -> bool:
    """Delete an ad by ID. Returns True if removed."""
    conn = get_db()
    cur = conn.execute("DELETE FROM ads WHERE id=?", (ad_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def list_ads(enabled_only: bool = False) -> list[dict]:
    """Return all (or only enabled) ads as a list of dicts."""
    conn = get_db()
    if enabled_only:
        rows = conn.execute(
            "SELECT * FROM ads WHERE enabled=1 ORDER BY id"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ads ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_ad(ad_id: int, enabled: bool) -> bool:
    """Enable or disable an ad. Returns True if updated."""
    conn = get_db()
    cur = conn.execute(
        "UPDATE ads SET enabled=? WHERE id=?", (1 if enabled else 0, ad_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_ad(ad_id: int, content: str) -> bool:
    """Replace an ad's text. Returns True if updated."""
    conn = get_db()
    cur = conn.execute("UPDATE ads SET content=? WHERE id=?", (content, ad_id))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def get_ad(ad_id: int) -> dict | None:
    """Return a single ad as dict, or None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM ads WHERE id=?", (ad_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_ad_sent(ad_id: int):
    """Increment send count and update last_sent timestamp."""
    conn = get_db()
    conn.execute(
        "UPDATE ads SET send_count = send_count + 1, "
        "last_sent = datetime('now','localtime') WHERE id=?",
        (ad_id,),
    )
    conn.commit()
    conn.close()