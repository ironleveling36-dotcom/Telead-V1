"""
Advanced inline control panel (Aiogram 3) — fully self-service.

Everything is done from the bot chat with buttons:

  Main menu
   ├─ 🔐 Account     set/change API ID & Hash, LOGIN (enter code + 2FA),
   │                 logout — all in chat, no redeploy
   ├─ 📊 Status
   ├─ ⚙️ Settings    interval, mode, parse, jitter, delay, quiet hours…
   ├─ 📢 Ads         add · ✏️ edit text · 🗑 delete · tap to enable/disable
   ├─ 📡 Channels    add (one or many) · 🗑 remove · tap to enable/disable
   ├─ ▶️/⏸️ Pause/Resume
   └─ 📤 Send now

Ownership: the first person to /start claims the bot (or set ADMIN_USER_ID).
"""

import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import database as db
import settings
import scheduler
import credentials
import auth
from config import CONTROL_BOT_TOKEN

logger = logging.getLogger(__name__)


class Flow(StatesGroup):
    add_ad = State()
    edit_ad = State()
    add_channel = State()
    set_value = State()
    # account / login
    login_api_id = State()
    login_api_hash = State()
    login_phone = State()
    login_code = State()
    login_password = State()
    set_api_id = State()
    set_api_hash = State()


# ── keyboard helpers ────────────────────────────────────────────────

def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row]
        for row in rows
    ])


def back_btn(target: str = "home") -> list[tuple[str, str]]:
    return [("⬅️ Back", target)]


def main_menu() -> InlineKeyboardMarkup:
    paused = settings.get("paused")
    return kb([
        [("🔐 Account", "account"), ("📊 Status", "status")],
        [("📢 Ads", "ads"), ("📡 Channels", "channels")],
        [("⚙️ Settings", "settings"),
         (("▶️ Resume" if paused else "⏸️ Pause"), "toggle_pause")],
        [("📤 Send now", "sendnow")],
    ])


def account_menu() -> InlineKeyboardMarkup:
    rows = [
        [("🆔 Set API ID", "set_api_id"), ("🔑 Set API Hash", "set_api_hash")],
    ]
    if credentials.is_logged_in():
        rows.append([("🔄 Re-login", "login"), ("🚪 Logout", "logout")])
    else:
        rows.append([("🔓 Login", "login")])
    rows.append(back_btn())
    return kb(rows)


def ads_menu() -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for a in db.list_ads():
        mark = "🟢" if a["enabled"] else "🔴"
        preview = (a["content"][:20] + "…") if len(a["content"]) > 20 else a["content"]
        rows.append([
            (f"{mark} #{a['id']} {preview}", f"ad_toggle:{a['id']}"),
            ("✏️", f"ad_edit:{a['id']}"),
            ("🗑", f"ad_del:{a['id']}"),
        ])
    rows.append([("➕ Add ad", "ad_add")])
    rows.append(back_btn())
    return kb(rows)


def channels_menu() -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for c in db.list_channels():
        mark = "🟢" if c["enabled"] else "🔴"
        label = c["title"] or c["channel_id"]
        label = (label[:24] + "…") if len(label) > 24 else label
        rows.append([
            (f"{mark} {label}", f"ch_toggle:{c['channel_id']}"),
            ("🗑", f"ch_del:{c['channel_id']}"),
        ])
    rows.append([("➕ Add channel(s)", "ch_add")])
    rows.append(back_btn())
    return kb(rows)


def settings_menu() -> InlineKeyboardMarkup:
    s = settings.all_settings()
    return kb([
        [(f"⏱ Interval: {s['interval_minutes']}m", "set:interval_minutes"),
         (f"🔁 Mode: {s['send_mode']}", "cycle_mode")],
        [(f"📝 Parse: {s['parse_mode']}", "cycle_parse"),
         (f"⏳ Delay: {s['per_send_delay']}s", "set:per_send_delay")],
        [(f"🎲 Jitter: {s['jitter_seconds']}s", "set:jitter_seconds"),
         (f"🔢 Max/cycle: {s['max_per_cycle']}", "set:max_per_cycle")],
        [(f"🌙 Quiet start: {s['quiet_start']}", "set:quiet_start"),
         (f"🌅 Quiet end: {s['quiet_end']}", "set:quiet_end")],
        [(f"🔕 Silent: {'on' if s['silent'] else 'off'}", "toggle:silent"),
         (f"🔗 Preview: {'on' if s['link_preview'] else 'off'}", "toggle:link_preview")],
        back_btn(),
    ])


def status_text() -> str:
    chans = db.list_channels()
    ads = db.list_ads()
    s = settings.all_settings()
    return (
        "📊 <b>Status</b>\n"
        f"{credentials.status_line()}\n"
        f"State: {'⏸️ paused' if s['paused'] else '▶️ running'}\n"
        f"Channels: {len(chans)} ({sum(c['enabled'] for c in chans)} on)\n"
        f"Ads: {len(ads)} ({sum(a['enabled'] for a in ads)} on) · "
        f"sent {sum(a['send_count'] for a in ads)}x\n"
        f"Interval: {s['interval_minutes']}m · Mode: {s['send_mode']} · Parse: {s['parse_mode']}\n"
        f"Jitter: {s['jitter_seconds']}s · Delay: {s['per_send_delay']}s · Max/cycle: {s['max_per_cycle']}\n"
        f"Quiet: {s['quiet_start']}→{s['quiet_end']} · "
        f"Silent: {'on' if s['silent'] else 'off'} · Preview: {'on' if s['link_preview'] else 'off'}"
    )


def account_text() -> str:
    return (
        "🔐 <b>Account</b>\n\n"
        f"{credentials.status_line()}\n\n"
        "• Set your <b>API ID</b> & <b>API Hash</b> (from my.telegram.org)\n"
        "• Then tap <b>Login</b> — I'll send a code to your Telegram app; "
        "reply with it here (and your 2FA password if you have one).\n"
        "• You can change these anytime."
    )


# ── dispatcher ──────────────────────────────────────────────────────

def build_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=CONTROL_BOT_TOKEN)
    dp = Dispatcher()

    def is_owner(uid: int) -> bool:
        return uid == credentials.get_owner()

    async def guard_cb(cq: types.CallbackQuery) -> bool:
        if not is_owner(cq.from_user.id):
            await cq.answer("⛔ Not authorized.", show_alert=True)
            return False
        return True

    @dp.message(Command("start", "panel", "help"))
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.clear()
        newly = credentials.claim_owner_if_unset(message.from_user.id)
        if not is_owner(message.from_user.id):
            await message.answer("⛔ This bot already has an owner.")
            return
        hello = "👑 You're now the owner of this bot.\n\n" if newly else ""
        await message.answer(hello + "🤖 <b>Ad Bot Control Panel</b>",
                             parse_mode="HTML", reply_markup=main_menu())

    # ---- navigation ----
    @dp.callback_query(F.data == "home")
    async def cb_home(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        await state.clear()
        await cq.message.edit_text("🤖 <b>Ad Bot Control Panel</b>", parse_mode="HTML",
                                   reply_markup=main_menu())
        await cq.answer()

    @dp.callback_query(F.data == "status")
    async def cb_status(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        await cq.message.edit_text(status_text(), parse_mode="HTML",
                                   reply_markup=kb([back_btn()]))
        await cq.answer()

    @dp.callback_query(F.data == "account")
    async def cb_account(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        await cq.message.edit_text(account_text(), parse_mode="HTML",
                                   reply_markup=account_menu())
        await cq.answer()

    @dp.callback_query(F.data == "ads")
    async def cb_ads(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        await cq.message.edit_text("📢 <b>Ads</b> — tap to enable/disable · ✏️ edit · 🗑 delete:",
                                   parse_mode="HTML", reply_markup=ads_menu())
        await cq.answer()

    @dp.callback_query(F.data == "channels")
    async def cb_channels(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        await cq.message.edit_text("📡 <b>Channels</b> — tap to enable/disable · 🗑 remove:",
                                   parse_mode="HTML", reply_markup=channels_menu())
        await cq.answer()

    @dp.callback_query(F.data == "settings")
    async def cb_settings(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        await cq.message.edit_text("⚙️ <b>Advanced Settings</b>", parse_mode="HTML",
                                   reply_markup=settings_menu())
        await cq.answer()

    # ---- pause / sendnow ----
    @dp.callback_query(F.data == "toggle_pause")
    async def cb_pause(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        new = settings.toggle("paused")
        await cq.answer("Paused" if new else "Resumed")
        await cq.message.edit_text("🤖 <b>Ad Bot Control Panel</b>", parse_mode="HTML",
                                   reply_markup=main_menu())

    @dp.callback_query(F.data == "sendnow")
    async def cb_sendnow(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        await cq.answer("Sending…")
        stats = await scheduler.run_one_cycle()
        if stats.get("skipped"):
            txt = f"Skipped ({stats['skipped']})."
        else:
            txt = f"Done: {stats['sent']} sent, {stats['failed']} failed."
        await cq.message.answer(txt, reply_markup=main_menu())

    # ---- account: set API id / hash ----
    @dp.callback_query(F.data == "set_api_id")
    async def cb_set_api_id(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        await state.set_state(Flow.set_api_id)
        await cq.message.answer("🆔 Send your <b>API ID</b> (numbers only).", parse_mode="HTML")
        await cq.answer()

    @dp.message(Flow.set_api_id)
    async def on_set_api_id(message: types.Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("API ID must be numbers only. Try again.")
            return
        credentials.set_api_id(int(message.text.strip()))
        await state.clear()
        await message.answer("✅ API ID saved.", reply_markup=account_menu())

    @dp.callback_query(F.data == "set_api_hash")
    async def cb_set_api_hash(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        await state.set_state(Flow.set_api_hash)
        await cq.message.answer("🔑 Send your <b>API Hash</b>.", parse_mode="HTML")
        await cq.answer()

    @dp.message(Flow.set_api_hash)
    async def on_set_api_hash(message: types.Message, state: FSMContext):
        credentials.set_api_hash(message.text.strip())
        await state.clear()
        await message.answer("✅ API Hash saved.", reply_markup=account_menu())

    # ---- account: logout ----
    @dp.callback_query(F.data == "logout")
    async def cb_logout(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        credentials.clear_session()
        import telegram_client
        telegram_client.reset_client_sync()
        await cq.message.edit_text(account_text(), parse_mode="HTML",
                                   reply_markup=account_menu())
        await cq.answer("Logged out")

    # ---- account: LOGIN flow ----
    @dp.callback_query(F.data == "login")
    async def cb_login(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        if not credentials.get_api_id():
            await state.set_state(Flow.login_api_id)
            await cq.message.answer("🆔 First, send your <b>API ID</b> (numbers only).", parse_mode="HTML")
        elif not credentials.get_api_hash():
            await state.set_state(Flow.login_api_hash)
            await cq.message.answer("🔑 Send your <b>API Hash</b>.", parse_mode="HTML")
        else:
            await state.set_state(Flow.login_phone)
            cur = credentials.get_phone()
            hint = f"\n(current: {cur})" if cur else ""
            await cq.message.answer(f"📞 Send your phone number in international format, "
                                    f"e.g. +1234567890{hint}", parse_mode="HTML")
        await cq.answer()

    @dp.message(Flow.login_api_id)
    async def on_login_api_id(message: types.Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("API ID must be numbers only. Try again.")
            return
        credentials.set_api_id(int(message.text.strip()))
        await state.set_state(Flow.login_api_hash)
        await message.answer("🔑 Now send your <b>API Hash</b>.", parse_mode="HTML")

    @dp.message(Flow.login_api_hash)
    async def on_login_api_hash(message: types.Message, state: FSMContext):
        credentials.set_api_hash(message.text.strip())
        await state.set_state(Flow.login_phone)
        await message.answer("📞 Now send your phone number, e.g. +1234567890")

    @dp.message(Flow.login_phone)
    async def on_login_phone(message: types.Message, state: FSMContext):
        phone = message.text.strip()
        ok, msg = await auth.start_login(
            message.from_user.id, credentials.get_api_id(),
            credentials.get_api_hash(), phone,
        )
        if ok:
            await state.set_state(Flow.login_code)
        await message.answer(msg)

    @dp.message(Flow.login_code)
    async def on_login_code(message: types.Message, state: FSMContext):
        status, msg = await auth.submit_code(message.from_user.id, message.text)
        if status == "ok":
            await state.clear()
            await message.answer(msg, reply_markup=main_menu())
        elif status == "2fa":
            await state.set_state(Flow.login_password)
            await message.answer(msg)
        else:
            await message.answer(msg)

    @dp.message(Flow.login_password)
    async def on_login_password(message: types.Message, state: FSMContext):
        status, msg = await auth.submit_password(message.from_user.id, message.text)
        if status == "ok":
            await state.clear()
            await message.answer(msg, reply_markup=main_menu())
        else:
            await message.answer(msg)

    # ---- ad toggle / edit / delete ----
    @dp.callback_query(F.data.startswith("ad_toggle:"))
    async def cb_ad_toggle(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        ad_id = int(cq.data.split(":")[1])
        ad = db.get_ad(ad_id)
        if ad:
            db.toggle_ad(ad_id, not ad["enabled"])
        await cq.message.edit_reply_markup(reply_markup=ads_menu())
        await cq.answer("Toggled")

    @dp.callback_query(F.data.startswith("ad_edit:"))
    async def cb_ad_edit(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        ad_id = int(cq.data.split(":")[1])
        ad = db.get_ad(ad_id)
        if not ad:
            await cq.answer("Not found")
            return
        await state.set_state(Flow.edit_ad)
        await state.update_data(ad_id=ad_id)
        await cq.message.answer(
            f"✏️ Send the new text for ad #{ad_id}.\nCurrent:\n\n{ad['content']}")
        await cq.answer()

    @dp.message(Flow.edit_ad)
    async def on_edit_ad(message: types.Message, state: FSMContext):
        data = await state.get_data()
        db.update_ad(data["ad_id"], message.text)
        await state.clear()
        await message.answer(f"✅ Ad #{data['ad_id']} updated.", reply_markup=ads_menu())

    @dp.callback_query(F.data.startswith("ad_del:"))
    async def cb_ad_del(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        db.remove_ad(int(cq.data.split(":")[1]))
        await cq.message.edit_reply_markup(reply_markup=ads_menu())
        await cq.answer("Deleted")

    @dp.callback_query(F.data == "ad_add")
    async def cb_ad_add(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        await state.set_state(Flow.add_ad)
        await cq.message.answer("✏️ Send the advertisement text now.")
        await cq.answer()

    @dp.message(Flow.add_ad)
    async def on_add_ad(message: types.Message, state: FSMContext):
        ad = db.add_ad(message.text)
        await state.clear()
        await message.answer(f"✅ Ad #{ad['id']} added.", reply_markup=ads_menu())

    # ---- channel toggle / delete / add (one or many) ----
    @dp.callback_query(F.data.startswith("ch_toggle:"))
    async def cb_ch_toggle(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        cid = cq.data.split(":", 1)[1]
        ch = next((c for c in db.list_channels() if c["channel_id"] == cid), None)
        if ch:
            db.toggle_channel(cid, not ch["enabled"])
        await cq.message.edit_reply_markup(reply_markup=channels_menu())
        await cq.answer("Toggled")

    @dp.callback_query(F.data.startswith("ch_del:"))
    async def cb_ch_del(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        db.remove_channel(cq.data.split(":", 1)[1])
        await cq.message.edit_reply_markup(reply_markup=channels_menu())
        await cq.answer("Removed")

    @dp.callback_query(F.data == "ch_add")
    async def cb_ch_add(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        await state.set_state(Flow.add_channel)
        await cq.message.answer(
            "✏️ Send one channel per line. Each: <code>id [optional title]</code>\n"
            "Examples:\n<code>-1001234567890 My Channel</code>\n<code>@somechannel</code>",
            parse_mode="HTML")
        await cq.answer()

    @dp.message(Flow.add_channel)
    async def on_add_channel(message: types.Message, state: FSMContext):
        added = 0
        for line in message.text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            db.add_channel(parts[0], parts[1] if len(parts) > 1 else "")
            added += 1
        await state.clear()
        await message.answer(f"✅ Added {added} channel(s).", reply_markup=channels_menu())

    # ---- settings: cycles / toggles / numeric ----
    @dp.callback_query(F.data == "cycle_mode")
    async def cb_cycle_mode(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        order = ["all", "rotate", "random"]
        cur = settings.get("send_mode")
        settings.put("send_mode", order[(order.index(cur) + 1) % len(order)] if cur in order else "all")
        await cq.message.edit_reply_markup(reply_markup=settings_menu())
        await cq.answer(f"Mode: {settings.get('send_mode')}")

    @dp.callback_query(F.data == "cycle_parse")
    async def cb_cycle_parse(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        order = ["none", "markdown", "html"]
        cur = settings.get("parse_mode")
        settings.put("parse_mode", order[(order.index(cur) + 1) % len(order)] if cur in order else "none")
        await cq.message.edit_reply_markup(reply_markup=settings_menu())
        await cq.answer(f"Parse: {settings.get('parse_mode')}")

    @dp.callback_query(F.data.startswith("toggle:"))
    async def cb_toggle_setting(cq: types.CallbackQuery):
        if not await guard_cb(cq):
            return
        settings.toggle(cq.data.split(":", 1)[1])
        await cq.message.edit_reply_markup(reply_markup=settings_menu())
        await cq.answer("Updated")

    @dp.callback_query(F.data.startswith("set:"))
    async def cb_set_value(cq: types.CallbackQuery, state: FSMContext):
        if not await guard_cb(cq):
            return
        key = cq.data.split(":", 1)[1]
        await state.set_state(Flow.set_value)
        await state.update_data(key=key)
        await cq.message.answer(
            f"✏️ Send a new value for <b>{settings.DEFAULTS[key][2]}</b>.\n"
            f"<i>{settings.DEFAULTS[key][3]}</i>", parse_mode="HTML")
        await cq.answer()

    @dp.message(Flow.set_value)
    async def on_set_value(message: types.Message, state: FSMContext):
        data = await state.get_data()
        val = message.text.strip()
        if not val.lstrip("-").isdigit():
            await message.answer("Please send a whole number.")
            return
        key = data["key"]
        settings.put(key, int(val))
        await state.clear()
        await message.answer(f"✅ {settings.DEFAULTS[key][2]} set to {val}.",
                             reply_markup=settings_menu())

    return bot, dp