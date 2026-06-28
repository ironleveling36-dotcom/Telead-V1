"""
Optional seed script — quickly populate channels & ads from the CLI.

Usage examples:
    python seed.py channel -1001234567890 "My Channel"
    python seed.py ad "🔥 Check out my awesome product! https://example.com"
    python seed.py interval 5
    python seed.py list
"""

import sys

from config import init_db, set_interval_minutes, get_interval_minutes
import database as db


def main():
    init_db()
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "channel" and len(sys.argv) >= 3:
        title = sys.argv[3] if len(sys.argv) > 3 else ""
        db.add_channel(sys.argv[2], title)
        print(f"✅ Channel added: {sys.argv[2]}")

    elif cmd == "ad" and len(sys.argv) >= 3:
        ad = db.add_ad(sys.argv[2])
        print(f"✅ Ad #{ad['id']} added.")

    elif cmd == "interval" and len(sys.argv) >= 3:
        set_interval_minutes(int(sys.argv[2]))
        print(f"✅ Interval set to {get_interval_minutes()} min.")

    elif cmd == "list":
        print("Channels:")
        for c in db.list_channels():
            print(f"  {'🟢' if c['enabled'] else '🔴'} {c['channel_id']}  {c['title']}")
        print("Ads:")
        for a in db.list_ads():
            print(f"  {'🟢' if a['enabled'] else '🔴'} #{a['id']} (x{a['send_count']}): {a['content'][:60]}")
        print(f"Interval: {get_interval_minutes()} min")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()