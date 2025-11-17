import os
import time
import uuid
import logging
import httpx
import telebot
from telebot import types
from keep_alive import keep_alive

# ---------------- ENVIRONMENT ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_CHANNEL = os.getenv("PUBLIC_CHANNEL")
PRIVATE_LINK = os.getenv("PRIVATE_LINK", "")
ADMINS = os.getenv("ADMINS", "").split(",")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
user_mode = {}

all_users = set()
banned_users = set()
last_queries = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("checker_bot")


# ---------------- ADMIN CHECK ----------------
def is_admin(uid):
    return str(uid) in ADMINS


# ---------------- JOIN CHECK ----------------
def is_joined_public(uid):
    try:
        member = bot.get_chat_member(PUBLIC_CHANNEL, uid)
        return member.status in ("member", "creator", "administrator")
    except:
        return False


# ---------------- JOIN BUTTONS ----------------
def join_buttons():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Join Public", url=f"https://t.me/{PUBLIC_CHANNEL.replace('@','')}"))

    if PRIVATE_LINK.strip():
        kb.add(types.InlineKeyboardButton("🔒 Join Private", url=PRIVATE_LINK))

    kb.add(types.InlineKeyboardButton("✔ I Joined", callback_data="chk_join"))
    return kb



# ---------------- ERROR DETECTOR ----------------
def has_error(text):
    if not text:
        return False
    t = text.lower()
    for w in ("error", "invalid", "forbidden", "unauthorized", "not found", "failed"):
        if w in t:
            return True
    return False


# ---------------- PROXY CHECKER ----------------
async def check_proxy(proxy):
    try:
        async with httpx.AsyncClient(proxies=f"http://{proxy}", timeout=6) as client:
            r = await client.get("https://api.ipify.org")
            return f"🟢 LIVE → {proxy}\nIP: {r.text}"
    except:
        return f"🔴 DEAD → {proxy}"


# ---------------- API CHECKER ----------------
async def check_api(value):
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            if value.startswith(("http://", "https://")):
                r = await client.get(value)
                if r.status_code != 200:
                    return f"🔴 INVALID URL → Status {r.status_code}"
                if has_error(r.text):
                    return "🔴 INVALID URL → Error detected in response"
                return "🟢 VALID URL"

            r = await client.get(
                "https://httpbin.org/bearer",
                headers={"Authorization": f"Bearer {value}"}
            )
            if r.status_code == 200:
                return "🟢 VALID API KEY"
            if r.status_code == 401:
                return "🔴 INVALID API KEY"

            return f"⚠ UNKNOWN STATUS {r.status_code}"

    except Exception as e:
        return f"❌ ERROR → {e}"


# ---------------- RESULT BUTTONS ----------------
def result_buttons(value):
    uid = uuid.uuid4().hex[:12]
    last_queries[uid] = value

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 Re-Check", callback_data=f"re|{uid}"))
    kb.add(types.InlineKeyboardButton("❌ Delete", callback_data=f"del|{uid}"))

    if value.startswith("http"):
        kb.add(types.InlineKeyboardButton("🌐 Open URL", url=value))

    return kb


# ---------------- START ----------------
@bot.message_handler(commands=['start'])
def start_cmd(m):

    # SAVE USER
    all_users.add(str(m.from_user.id))

    if str(m.from_user.id) in banned_users:
        return

    if not is_joined_public(m.from_user.id):
        bot.reply_to(
            m,
            "🚀 **Welcome to ALL IN ONE Checker — The Future of API & Proxy Scanning**\n\n"
            "To unlock access, please join our public channel first.\n\n"
            "**Upcoming Features:**\n"
            "• 🤖 AI-powered smart validations\n"
            "• 🔍 Proxy pattern detection\n"
            "• 📊 API performance analytics\n"
            "• 🧠 Auto-fix suggestions\n"
            "• 🔐 Secure cloud scan history\n"
            "• ⚡ Multi-layer deep scan engine\n\n"
            "Join the channel and come back!",
            parse_mode="Markdown",
            reply_markup=join_buttons()
        )
        return

    bot.reply_to(
        m,
        "👋 **Welcome!**\n\n"
        "Use:\n"
        "• `/api` — API/URL Checker\n"
        "• `/proxy` — Proxy Checker\n",
        parse_mode="Markdown"
    )



# ---------------- API MENU ----------------
@bot.message_handler(commands=['api'])
def api_menu(m):
    if not is_joined_public(m.from_user.id):
        bot.reply_to(m, "Join public channel first!", reply_markup=join_buttons())
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Single API/URL", callback_data="api_single"))
    kb.add(types.InlineKeyboardButton("Bulk TXT", callback_data="api_bulk"))
    bot.reply_to(m, "Choose API mode:", reply_markup=kb)



# ---------------- PROXY MENU ----------------
@bot.message_handler(commands=['proxy'])
def proxy_menu(m):
    if not is_joined_public(m.from_user.id):
        bot.reply_to(m, "Join public channel first!", reply_markup=join_buttons())
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Single Proxy", callback_data="proxy_single"))
    kb.add(types.InlineKeyboardButton("Bulk TXT", callback_data="proxy_bulk"))
    bot.reply_to(m, "Choose Proxy mode:", reply_markup=kb)



# ---------------- ADMIN PANEL ----------------
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Not authorized.")
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"))
    kb.add(types.InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban"))
    kb.add(types.InlineKeyboardButton("📊 Bot Stats", callback_data="adm_stats"))
    kb.add(types.InlineKeyboardButton("♻ Restart", callback_data="adm_restart"))

    bot.reply_to(m, "👑 **Admin Control Panel**", parse_mode="Markdown", reply_markup=kb)



# ---------------- CALLBACK HANDLER ----------------
@bot.callback_query_handler(func=lambda c: True)
def callback_handler(c):
    chat = c.message.chat.id

    # JOIN CHECK
    if c.data == "chk_join":
        if is_joined_public(c.from_user.id):
            bot.send_message(chat, "✅ Access granted! Use /api or /proxy")
        else:
            bot.send_message(chat, "❌ You still haven't joined!")
        return

    # ADMIN CALLBACKS
    if c.data.startswith("adm_"):

        if not is_admin(c.from_user.id):
            bot.answer_callback_query(c.id, "❌ Not allowed")
            return

        act = c.data

        if act == "adm_broadcast":
            user_mode[chat] = "broadcast"
            bot.send_message(chat, "📢 Send message for broadcast:")
            return

        if act == "adm_ban":
            user_mode[chat] = "ban"
            bot.send_message(chat, "🚫 Send user ID to ban:")
            return

        if act == "adm_stats":
            msg = (
                "📊 **Bot Stats**\n"
                f"• Total Users: {len(all_users)}\n"
                f"• Banned Users: {len(banned_users)}\n"
                f"• Admins: {len(ADMINS)}\n"
                f"• Status: Running\n"
            )
            bot.send_message(chat, msg, parse_mode="Markdown")
            return

        if act == "adm_restart":
            bot.send_message(chat, "♻ Restarting bot...")
            os._exit(1)

        return

    # RECHECK OR DELETE
    if "|" in c.data:
        cmd, uid = c.data.split("|")
        value = last_queries.get(uid, None)
        if not value:
            bot.answer_callback_query(c.id, "❌ Expired.")
            return

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if cmd == "re":
            if ":" in value:
                result = loop.run_until_complete(check_proxy(value))
            else:
                result = loop.run_until_complete(check_api(value))

            bot.send_message(chat, result, reply_markup=result_buttons(value))
            return

        if cmd == "del":
            bot.delete_message(chat, c.message.message_id)
            last_queries.pop(uid, None)
            return

    # MODE SELECT
    if c.data in ("api_single", "proxy_single", "api_bulk", "proxy_bulk"):
        user_mode[chat] = c.data
        bot.send_message(chat, "Send your input now:")
        return



# ---------------- TEXT HANDLER ----------------
@bot.message_handler(content_types=['text'])
def text_handler(m):

    if str(m.from_user.id) in banned_users:
        return

    chat = m.chat.id
    all_users.add(str(m.from_user.id))

    # BROADCAST
    if user_mode.get(chat) == "broadcast" and is_admin(m.from_user.id):
        msg = m.text
        for u in all_users:
            try:
                bot.send_message(u, msg)
            except:
                pass
        bot.send_message(chat, "📢 Broadcast Sent!")
        del user_mode[chat]
        return

    # BAN
    if user_mode.get(chat) == "ban" and is_admin(m.from_user.id):
        banned_users.add(m.text.strip())
        bot.send_message(chat, f"🚫 User {m.text} banned.")
        del user_mode[chat]
        return

    # NORMAL MODE
    if chat not in user_mode:
        return

    mode = user_mode[chat]
    text = m.text.strip()

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if mode == "proxy_single":
        res = loop.run_until_complete(check_proxy(text))
    else:
        res = loop.run_until_complete(check_api(text))

    bot.reply_to(m, res, reply_markup=result_buttons(text))
    del user_mode[chat]



# ---------------- FILE HANDLER ----------------
@bot.message_handler(content_types=['document'])
def doc_handler(m):

    if str(m.from_user.id) in banned_users:
        return

    chat = m.chat.id
    all_users.add(str(m.from_user.id))

    if chat not in user_mode:
        return

    file = bot.get_file(m.document.file_id)
    data = bot.download_file(file.file_path).decode().splitlines()

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    output = []
    for line in data:
        s = line.strip()
        if not s:
            continue

        if "proxy" in user_mode[chat]:
            output.append(loop.run_until_complete(check_proxy(s)))
        else:
            output.append(loop.run_until_complete(check_api(s)))

    bot.send_message(chat, "\n\n".join(output))
    del user_mode[chat]



# ---------------- STARTUP CLEANUP ----------------
def startup_cleanup():
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    try:
        bot.remove_webhook()
    except:
        pass
    logger.info("Webhook removed. Starting polling...")


# ---------------- RUN ----------------
if __name__ == "__main__":
    keep_alive()
    startup_cleanup()

    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception:
            logger.exception("Bot crashed, retrying in 5 sec...")
            time.sleep(5)
