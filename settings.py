"""
Advanced settings layer.

Wraps the `settings` key/value table with typed getters/setters and a
schema of defaults. Every advanced option the scheduler and panel use
lives here, so adding a new setting is a one-line change to DEFAULTS.
"""

from config import get_setting, set_setting

# key -> (default_value, type, human_label, help_text)
DEFAULTS = {
    "interval_minutes":  ("5",      int,  "Interval (min)",      "Minutes between posting cycles"),
    "per_send_delay":    ("2",      int,  "Per-send delay (s)",  "Seconds to wait between each individual send"),
    "jitter_seconds":    ("0",      int,  "Jitter (s)",          "Random 0..N seconds added before each send (anti-spam)"),
    "send_mode":         ("all",    str,  "Send mode",           "all = every enabled ad each cycle; rotate = one ad per cycle (round-robin); random = one random ad"),
    "parse_mode":        ("none",   str,  "Parse mode",          "none | markdown | html — formatting for ad text"),
    "silent":            ("0",      bool, "Silent send",         "Send without notification sound"),
    "link_preview":      ("1",      bool, "Link preview",        "Show web page previews for links"),
    "paused":            ("0",      bool, "Scheduler paused",    "When on, no ads are sent"),
    "quiet_start":       ("-1",     int,  "Quiet start (hour)",  "Hour 0-23 to stop posting (-1 = disabled)"),
    "quiet_end":         ("-1",     int,  "Quiet end (hour)",    "Hour 0-23 to resume posting (-1 = disabled)"),
    "max_per_cycle":     ("0",      int,  "Max sends/cycle",     "Cap total sends per cycle (0 = unlimited)"),
}

# round-robin cursor (which ad index to send next in 'rotate' mode)
_ROTATE_KEY = "rotate_cursor"


def _cast(value: str, typ):
    if typ is bool:
        return value in ("1", "true", "True", "on", "yes")
    if typ is int:
        try:
            return int(value)
        except ValueError:
            return 0
    return value


def get(key: str):
    """Return a typed setting value, falling back to its default."""
    default, typ, *_ = DEFAULTS[key]
    return _cast(get_setting(key, default), typ)


def put(key: str, value) -> None:
    """Store a setting (bool stored as 1/0)."""
    if isinstance(value, bool):
        value = "1" if value else "0"
    set_setting(key, str(value))


def toggle(key: str) -> bool:
    """Flip a boolean setting and return the new value."""
    new = not get(key)
    put(key, new)
    return new


def all_settings() -> dict:
    """Return every setting as {key: typed_value}."""
    return {k: get(k) for k in DEFAULTS}


def ensure_defaults() -> None:
    """Insert any missing settings with their default values."""
    for key, (default, *_rest) in DEFAULTS.items():
        if get_setting(key, None) is None:  # type: ignore[arg-type]
            set_setting(key, default)
    if get_setting(_ROTATE_KEY, None) is None:  # type: ignore[arg-type]
        set_setting(_ROTATE_KEY, "0")


# ── rotate cursor helpers ───────────────────────────────────────────

def get_rotate_cursor() -> int:
    return int(get_setting(_ROTATE_KEY, "0"))


def set_rotate_cursor(value: int) -> None:
    set_setting(_ROTATE_KEY, str(value))


def in_quiet_hours(hour: int) -> bool:
    """True if `hour` (0-23) falls within the configured quiet window."""
    start, end = get("quiet_start"), get("quiet_end")
    if start < 0 or end < 0:
        return False
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    # window wraps midnight, e.g. 22 -> 6
    return hour >= start or hour < end