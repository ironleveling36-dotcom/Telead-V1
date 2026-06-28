# 📢 Telegram Ad Bot (User Account)

Automatically posts advertisements to Telegram channels **as your own user account**
(not a bot), on a repeating schedule. Built with **Telethon** for the user-account
sending and an optional **Aiogram** control bot to manage everything from chat.

> Why Telethon and not pure Aiogram? Aiogram only works with **bot tokens**.
> To send messages **as you** (a normal member of a channel) you must use a
> **user session** (API ID + API Hash), which is what Telethon provides.

---

## 🆕 Everything is set up INSIDE the bot (no local login needed)

You no longer need to run `login.py` on your computer. After deploying, just
open your bot and use the **🔐 Account** menu:

1. **Set API ID** and **Set API Hash** (get them from <https://my.telegram.org>).
2. Tap **🔓 Login** → enter your **phone** → the bot asks you for the **code**
   Telegram sends to your app → (if you have 2FA) enter your **password**.
3. Done — the session is saved to the database and posting starts automatically.

You can **change the API ID / API Hash or re-login anytime** from the same menu.
`login.py` and `seed.py` are still included as optional local helpers, but are
not required.

---

## ✨ Features

- ✅ Sends ads **as your user account** (works when you're just a member, not admin)
- ✅ **Set/change API ID & API Hash and log in entirely from the bot chat** (with 2FA)
- ✅ Add **one or many channels** at once · remove any · enable/disable each
- ✅ Add ads · **edit ad text** · delete · enable/disable each
- ✅ Advanced settings: interval, send mode, parse mode, jitter, delay, quiet hours, etc.
- ✅ All data in **SQLite** (survives restarts via a volume)
- ✅ **Resilient scheduler** — one bad channel/error never stops it
- ✅ **Docker** image, **Railway**-ready, runs 24/7
- ✅ First user to /start becomes the owner (or lock with `ADMIN_USER_ID`)

---

## 📁 Project structure

```
tele_ad_bot/
├── main.py              # entry point — runs scheduler (+ optional control bot)
├── config.py            # env vars, SQLite schema & settings helpers
├── database.py          # CRUD for channels / ads / settings
├── telegram_client.py   # Telethon user-account client + safe sending
├── scheduler.py         # the 5-minute posting loop
├── control_bot.py       # optional Aiogram bot to manage ads from chat
├── login.py             # one-time: generate a headless StringSession
├── seed.py              # CLI helper to add channels/ads quickly
├── requirements.txt
├── Procfile             # Railway/Heroku worker
├── railway.json         # Railway build + restart config
├── runtime.txt          # Python version
├── .env.example         # copy to .env and fill in
└── .gitignore           # excludes *.session, .env, *.db
```

---

## 🚀 Quick start (local)

### 1. Get Telegram API credentials
Go to <https://my.telegram.org> → **API development tools** → create an app.
Copy your **API ID** and **API Hash**.

### 2. Configure
```bash
cp .env.example .env
# edit .env: set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
pip install -r requirements.txt
```

### 3. Log in once (creates your session)
```bash
python login.py
```
Enter the code Telegram sends to your app (and 2FA password if enabled).
It prints a **StringSession** — copy it. You'll paste it into Railway later.

### 4. Add channels & ads
> ⚠️ **Important:** your account must already be a **member** of each channel,
> and you must have opened it at least once so Telethon can resolve it.
> Use the channel's numeric id (e.g. `-1001234567890`) or `@username`.

```bash
python seed.py channel -1001234567890 "My Channel"
python seed.py ad "🔥 Check out my product! https://example.com"
python seed.py ad "Second advertisement message"
python seed.py interval 5
python seed.py list
```

### 5. Run
```bash
python main.py
```
It posts every enabled ad to every enabled channel every 5 minutes.

---

## 🐳 Run with Docker (recommended)

```bash
cp .env.example .env        # fill in API id/hash + TELEGRAM_SESSION
docker compose up -d --build
docker compose logs -f      # watch it run
```

The SQLite DB is stored in a named volume (`adbot_data` → `/data`) so your
ads/channels/settings survive restarts. Stop with `docker compose down`.

> Generate `TELEGRAM_SESSION` first by running `python login.py` locally
> (interactive login can't happen inside the container).

---

## ☁️ Deploy to Railway (headless, 24/7 — Docker build)

1. **Push this folder to a GitHub repo** (see below).
2. On <https://railway.app> → **New Project → Deploy from GitHub repo** → pick your repo.
3. Railway builds from the **`Dockerfile`** (configured in `railway.json`).
4. Add **Variables** (Settings → Variables):

   | Variable | Value |
   |---|---|
   | `CONTROL_BOT_TOKEN` | **(required)** token from @BotFather |
   | `ADMIN_USER_ID` | *(optional)* lock to your id from @userinfobot |
   | `DB_PATH` | `/data/ad_bot.db` |

   > You do **not** need to set API ID / Hash / session here — you'll do that
   > from the bot's **🔐 Account** menu after it's running.

5. **(Recommended)** Add a **Volume** mounted at `/data` and set `DB_PATH=/data/ad_bot.db`
   so your channels/ads survive redeploys.
6. Deploy. Watch the logs — you should see `✅ User account session is live.` then cycle logs.

Because there's no web server, run it as a **Worker** service (the `Procfile` already
declares `worker:`). Railway's restart policy (`railway.json`) auto-restarts on crashes.

---

## 🎛️ Advanced inline control panel

Set `CONTROL_BOT_TOKEN` (from @BotFather) + `ADMIN_USER_ID` (from @userinfobot),
then send **/panel** (or /start) to your bot. Everything is button-driven:

```
🤖 Ad Bot Control Panel
 ├─ 📊 Status            live summary + counters
 ├─ ⚙️ Settings          (all advanced options below)
 ├─ 📢 Ads               tap an ad to enable/disable · 🗑 delete · ➕ add
 ├─ 📡 Channels          tap to enable/disable · 🗑 delete · ➕ add
 ├─ ⏸️/▶️ Pause / Resume  stop or start posting instantly
 └─ 📤 Send now          run one cycle immediately
```

Adding ads/channels and editing numeric values is handled with inline
follow-up prompts (FSM) — just tap the button and reply with the value.

### ⚙️ Advanced settings (all editable from the panel)

| Setting | What it does |
|---|---|
| **Interval (min)** | Minutes between posting cycles (default 5) |
| **Send mode** | `all` = every enabled ad each cycle · `rotate` = one ad per cycle (round-robin) · `random` = one random ad |
| **Parse mode** | `none` / `markdown` / `html` formatting for ad text |
| **Per-send delay (s)** | Pause between each individual send |
| **Jitter (s)** | Random 0..N second delay before each send (anti-spam pattern) |
| **Max sends/cycle** | Hard cap on sends per cycle (0 = unlimited) |
| **Quiet hours** | Start/end hour (0-23) to pause posting overnight (-1 = off; wraps midnight) |
| **Silent send** | Deliver without notification sound |
| **Link preview** | Toggle web page previews on links |
| **Pause** | Master on/off switch for the scheduler |

All settings persist in SQLite and take effect on the **next cycle** — no restart needed.

---

## 🐙 Push to GitHub

```bash
cd tele_ad_bot
git init
git add .
git commit -m "Telegram user-account ad bot"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`.gitignore` keeps your `*.session`, `.env`, and `*.db` files **out of the repo** —
never commit those (a session string = full access to your Telegram account).

---

## 🛟 Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot find any entity corresponding to ...` | Your account isn't a member of that channel, or you've never opened it. Join/open it first. |
| `TELEGRAM_SESSION is set but not authorized` | Session expired/revoked. Re-run `python login.py` and update the variable. |
| `FloodWaitError` in logs | Normal rate limiting — the bot waits automatically. Increase the interval if frequent. |
| `write forbidden` | The channel doesn't allow you to post. You can only post where members are allowed to send messages. |
| Data lost on redeploy | Attach a Railway **Volume** and set `DB_PATH=/data/ad_bot.db`. |

---

## ⚠️ Responsible use

Sending automated, repeated messages may violate Telegram's Terms of Service and can
get your account limited or banned. Use reasonable intervals, only post where you're
permitted, and don't spam. You are responsible for how you use this tool.
