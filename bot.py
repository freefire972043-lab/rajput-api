import telebot
import requests
import time
import threading
import sqlite3
import os
from flask import Flask
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# New imports for scheduling and environment variables
import schedule
import pytz
from datetime import datetime

# ================== CONFIG (from Environment Variables) ==================
BOT_TOKEN = os.environ.get('7965256274:AAGiPxfZiyDzfOOci9YPGD6tFCbWy93tcgQ')
OWNER_ID = int(os.environ.get('6820574331'))

ALLOWED_GROUPS = [-1002595397242]  # Jo groups me bot chale
API_LINK = "https://free-like-api-aditya-ffm.vercel.app"
REGIONS = [
    "IND", "BR", "US", "NA", "SAC", "SG", "RU", "ID",
    "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EUROPE", "EU"
]
# ============================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
last_request_time = 0

# ================== DATABASE ===================
# Added 'check_same_thread=False' for multi-threaded access
def init_db():
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS autolike_users (
        user_id INTEGER,
        chat_id INTEGER,
        uid TEXT,
        region TEXT,
        last_liked INTEGER,
        expiration_timestamp INTEGER,
        PRIMARY KEY(user_id, uid)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS bot_config (
        id INTEGER PRIMARY KEY,
        api_link TEXT
    )""")
    c.execute("INSERT OR IGNORE INTO bot_config (id, api_link) VALUES (1, ?)", (API_LINK,))
    conn.commit()
    conn.close()

def get_current_api():
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT api_link FROM bot_config WHERE id=1")
    link = c.fetchone()[0]
    conn.close()
    return link

def set_new_api(new_api):
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE bot_config SET api_link=? WHERE id=1", (new_api,))
    conn.commit()
    conn.close()

def add_user_to_autolike(user_id, chat_id, uid, region, expiration_timestamp):
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("REPLACE INTO autolike_users VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, chat_id, uid, region, 0, expiration_timestamp))
    conn.commit()
    conn.close()

def remove_user_from_autolike(user_id, uid=None):
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    if uid:
        c.execute("DELETE FROM autolike_users WHERE user_id=? AND uid=?", (user_id, uid))
    else:
        c.execute("DELETE FROM autolike_users WHERE user_id=?", (user_id,))
    removed = c.rowcount > 0
    conn.commit()
    conn.close()
    return removed

def get_autolike_user(user_id):
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT uid, region, last_liked, expiration_timestamp FROM autolike_users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_all_autolike_users():
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM autolike_users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_autolike_uids_count():
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM autolike_users")
    count = c.fetchone()[0]
    conn.close()
    return count

def update_last_liked(user_id, uid, timestamp):
    conn = sqlite3.connect("autolike.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE autolike_users SET last_liked=? WHERE user_id=? AND uid=?", (timestamp, user_id, uid))
    conn.commit()
    conn.close()

init_db()
# ============================================

# =============== START / HELP ===============
@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    if message.chat.type == 'private':
        user_name = message.from_user.first_name
        welcome_text = f"""
🎉 WELCOME {user_name} 🎉
━━━✦✦━━━  
🔥 Ready to Fire, Ready to Win 🔥  
😎 Enjoy the Game with our BOT 🚀  
━━━━━━━━━━━━━━━
<b>Command -</b>
<code>/like {{region}} {{uid}}</code>
"""
        bot_username = bot.get_me().username
        markup = InlineKeyboardMarkup()
        add_to_group_button = InlineKeyboardButton(text="✨ ADD ME TO YOUR GROUP ✨", url=f"https://t.me/{bot_username}?startgroup=true")
        support_button = InlineKeyboardButton(text="SUPPORT", url="https://t.me/snnetwork7")
        owner_button = InlineKeyboardButton(text="❤️ OWNER ❤️", url="https://t.me/snxrajput")
        markup.add(add_to_group_button)
        markup.add(support_button, owner_button)
        bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
# ============================================

# =============== API REQUEST =================
def make_request(url):
    global last_request_time
    current_time = time.time()
    elapsed = current_time - last_request_time
    if elapsed < 1:
        time.sleep(1 - elapsed)
    last_request_time = time.time()
    try:
        response = requests.get(url, timeout=10)
        return response
    except Exception as e:
        print(f"Request error: {e}")
        return None

def get_api_remaining():
    try:
        api_link = get_current_api()
        url = f"{api_link}/remain"
        response = make_request(url)
        if response and response.status_code == 200:
            result = response.json()
            return result.get("remaining", 0), result.get("daily_limit", 0)
        return 0, 0
    except Exception as e:
        print(f"Error getting API remaining: {e}")
        return 0, 0
# ============================================

# =============== BOT COMMANDS =================
@bot.message_handler(commands=['autolike'])
def handle_autolike(message):
    if message.from_user.id != OWNER_ID: return
    if message.chat.id not in ALLOWED_GROUPS: return

    args = message.text.split()
    if len(args) != 4:
        bot.reply_to(message, "<b>Usage: /autolike {region} {uid} {days}</b>")
        return

    region, uid, days_str = args[1].upper(), args[2], args[3]
    try:
        days = int(days_str)
        if days <= 0 or days > 90:
            bot.reply_to(message, "<b>Invalid days. Must be 1-90.</b>")
            return
    except ValueError:
        bot.reply_to(message, "<b>Invalid days. Must be a number.</b>")
        return
    if region not in REGIONS:
        bot.reply_to(message, f"<b>Invalid region: {region}</b>")
        return

    expiration_timestamp = int(time.time()) + days*24*60*60
    add_user_to_autolike(message.from_user.id, message.chat.id, uid, region, expiration_timestamp)
    expiry_date_str = time.strftime('%Y-%m-%d', time.localtime(expiration_timestamp))
    bot.reply_to(message, f"✅ <b>Autolike Enabled for {days} days!</b>\nUID <code>{uid}</code> expires on <b>{expiry_date_str}</b>.")

@bot.message_handler(commands=['stopautolike'])
def handle_stop_autolike(message):
    if message.from_user.id != OWNER_ID: return
    if message.chat.id not in ALLOWED_GROUPS: return

    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "<b>Usage: /stopautolike {uid}</b>")
        return
    uid = args[1]
    if remove_user_from_autolike(message.from_user.id, uid):
        bot.reply_to(message, f"❌ <b>Autolike Disabled for UID {uid}</b>")
    else:
        bot.reply_to(message, f"🤔 <b>No autolike found for UID {uid}</b>")

@bot.message_handler(commands=['autolikestatus'])
def handle_autolike_status(message):
    if message.from_user.id != OWNER_ID: return
    if message.chat.id not in ALLOWED_GROUPS: return

    user_data = get_autolike_user(message.from_user.id)
    if user_data:
        uid, region, last_liked, expiration_timestamp = user_data
        last_liked_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_liked)) if last_liked > 0 else "Never"
        expiry_date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expiration_timestamp))
        status_msg = (
            f"📌 <b>Autolike Status:</b>\n"
            f"<b>UID:</b> <code>{uid}</code>\n"
            f"<b>Region:</b> <code>{region}</code>\n"
            f"<b>Last Auto-Liked:</b> {last_liked_str}\n"
            f"<b>Expires on:</b> {expiry_date_str}"
        )
        bot.reply_to(message, status_msg)
    else:
        bot.reply_to(message, "🤔 <b>No autolike active.</b>")

@bot.message_handler(commands=['autolikelist'])
def handle_autolike_list(message):
    if message.from_user.id != OWNER_ID: return
    if message.chat.id not in ALLOWED_GROUPS: return

    users = get_all_autolike_users()
    if not users:
        bot.reply_to(message, "🤔 <b>No active autolike subscriptions.</b>")
        return

    reply_text = "📋 <b>Active Autolike UIDs:</b>\n\n"
    for user in users:
        user_id, chat_id, uid, region, last_liked, expiration_timestamp = user
        expiry_date_str = time.strftime('%Y-%m-%d', time.localtime(expiration_timestamp))
        reply_text += (
            f"🎯 UID: <code>{uid}</code> ({region})\n"
            f"⏳ Expires: {expiry_date_str}\n\n"
        )
    bot.reply_to(message, reply_text)


@bot.message_handler(commands=['countuids'])
def handle_count_uids(message):
    if message.from_user.id != OWNER_ID: return
    count = get_all_autolike_uids_count()
    bot.reply_to(message, f"📊 <b>Total Autolike UIDs:</b> {count}")

@bot.message_handler(commands=['setapi'])
def handle_set_api(message):
    if message.from_user.id != OWNER_ID: return
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "<b>Usage: /setapi {new_api_link}</b>")
        return
    new_api = args[1]
    set_new_api(new_api)
    bot.reply_to(message, f"✅ <b>API Updated Successfully!</b>\nNew API: <code>{new_api}</code>")

@bot.message_handler(commands=["like"])
def handle_like(message):
    if message.chat.id not in ALLOWED_GROUPS: return
    args = message.text.split()
    if len(args) != 3:
        bot.reply_to(message, "<b>Usage: /like {region} {uid}</b>")
        return
    region, uid = args[1].upper(), args[2]
    if region not in REGIONS:
        bot.reply_to(message, f"<b>Invalid region: {region}</b>")
        return

    remaining, _ = get_api_remaining()
    if remaining <= 0:
        bot.reply_to(message, "⚠️ <b>Limit Reached! Try later.</b>")
        return

    processing_msg = bot.reply_to(message, "⏳ <b>Processing your request...</b>")

    try:
        api_link = get_current_api()
        url = f"{api_link}/like?uid={uid}&server_name={region}&key=@adityaapis"
        response = make_request(url)

        if response and response.status_code == 200:
            result = response.json()
            status = result.get("status")
            if status == 1:
                nickname = str(result.get('PlayerNickname', 'N/A')).replace('<','&lt;').replace('>','&gt;')
                likes_given = result.get("LikesGivenByAPI", 0)
                text = (
                    "✅ <b>Likes Sent Successfully!</b>\n"
                    f"🎮 <b>Player Nickname:</b> {nickname}\n"
                    f"🌍 <b>Region:</b> {result.get('PlayerRegion','N/A')}\n"
                    f"⭐ <b>Level:</b> {result.get('PlayerLevel','N/A')}\n"
                    f"❤️ <b>Before Likes:</b> {result.get('LikesbeforeCommand','N/A')}\n"
                    f"💖 <b>After Likes:</b> {result.get('LikesafterCommand','N/A')}\n"
                    f"🤖 <b>Likes Given By Bot:</b> {likes_given}"
                )
            elif status == 2:
                text = "⚠️ <b>Failed: Likes already sent.</b>"
            else:
                text = "❌ <b>Failed: Player not found.</b>"
        else:
            text = "❌ <b>Failed to connect to API.</b>"

        bot.edit_message_text(text, message.chat.id, processing_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ <b>Error:</b> {str(e)}", message.chat.id, processing_msg.message_id)

@bot.message_handler(commands=["remain"])
def handle_remain(message):
    remaining, daily_limit = get_api_remaining()
    bot.reply_to(message, f"📊 <b>Global API Remaining Requests:</b> {remaining}/{daily_limit} ✅")
# ============================================

# ================= AUTOLIKE SCHEDULER (FINAL VERSION) =================
def run_autolike_task():
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        print(f"[{now_ist.strftime('%Y-%m-%d %H:%M:%S')}] Running daily autolike task...")

        users = get_all_autolike_users()
        if not users:
            print("No autolike users found to process.")
            return

        remaining, _ = get_api_remaining()
        if remaining <= 0:
            print("API limit reached. Skipping autolike task for today.")
            return

        for user in users:
            user_id, chat_id, uid, region, last_liked, expiration_timestamp = user
            
            if int(time.time()) > expiration_timestamp:
                if remove_user_from_autolike(user_id, uid):
                    bot.send_message(chat_id, f"⌛️ <b>Your autolike subscription for UID {uid} has expired.</b>")
                continue

            api_link = get_current_api()
            url = f"{api_link}/like?uid={uid}&server_name={region}&key=@adityaapis"
            response = make_request(url)
            
            if response and response.status_code == 200:
                result = response.json()
                status = result.get("status")

                if status == 1:
                    update_last_liked(user_id, uid, int(time.time()))
                    nickname = str(result.get('PlayerNickname', 'N/A')).replace('<','&lt;').replace('>','&gt;')
                    likes_given = result.get("LikesGivenByAPI", 0)
                    text = (
                        "🤖 <b>[AUTO-LIKE]</b>\n"
                        "➖➖➖➖➖➖➖➖➖➖➖\n"
                        "✅ <b>Likes Sent Successfully!</b>\n"
                        f"🎮 <b>Player Nickname:</b> {nickname}\n"
                        f"🌍 <b>Region:</b> {result.get('PlayerRegion','N/A')}\n"
                        f"⭐ <b>Level:</b> {result.get('PlayerLevel','N/A')}\n"
                        f"❤️ <b>Before Likes:</b> {result.get('LikesbeforeCommand','N/A')}\n"
                        f"💖 <b>After Likes:</b> {result.get('LikesafterCommand','N/A')}\n"
                        f"🤖 <b>Likes Given By Bot:</b> {likes_given}"
                    )
                    bot.send_message(chat_id, text)
                
                else:
                    error_reason = "Likes already sent or Player not found."
                    bot.send_message(chat_id, f"🤖 <b>[AUTO-LIKE]</b>\n➖➖➖➖➖➖➖➖➖➖➖\n🎯 <b>UID:</b> <code>{uid}</code>\n⚠️ <b>Failed:</b> {error_reason}")
            else:
                bot.send_message(chat_id, f"🤖 <b>[AUTO-LIKE]</b>\n➖➖➖➖➖➖➖➖➖➖➖\n🎯 <b>UID:</b> <code>{uid}</code>\n❌ <b>Failed to connect to API.</b>")
            
            time.sleep(2)

    except Exception as e:
        print(f"An error occurred in run_autolike_task: {e}")

def autolike_scheduler():
    print("Autolike scheduler started. Waiting to run the task at 04:00 AM India Time.")
    schedule.every().day.at("04:00", "Asia/Kolkata").do(run_autolike_task)
    while True:
        schedule.run_pending()
        time.sleep(1)

# ========================================================

# ================= FLASK SERVER (for Render) =================
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Bot is running successfully!"

def run_flask():
    # Render provides the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= START BOT & SERVER =================
if __name__ == "__main__":
    print("Starting Flask server in a new thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("Starting autolike scheduler in a new thread...")
    scheduler_thread = threading.Thread(target=autolike_scheduler, daemon=True)
    scheduler_thread.start()
    
    print("Bot polling started...")
    bot.infinity_polling()
