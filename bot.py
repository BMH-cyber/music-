import os
import threading
import time
import requests
import logging
import json
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------------
# Env
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 8080))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

if not APP_URL:
    raise RuntimeError("APP_URL missing")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

WEBHOOK_URL = f"{APP_URL}/{BOT_TOKEN}"

# -----------------------------
# Admins
# -----------------------------
ADMIN_IDS = [5720351176, 6920736354, 7906327556]

# -----------------------------
# Groups Storage
# -----------------------------
GROUPS_FILE = "joined_groups.json"

def load_groups():
    try:
        with open(GROUPS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_group(chat_id):
    groups = load_groups()
    if chat_id not in groups:
        groups.append(chat_id)
        with open(GROUPS_FILE, "w") as f:
            json.dump(groups, f)

# -----------------------------
# Broadcast Settings
# -----------------------------
AUTO_PIN = False

# -----------------------------
# Wizard State (FIXED)
# -----------------------------
WIZARD = {}
# {admin_id: {"active": True, "items": []}}

def start_simple_wizard(message):
    admin_id = message.from_user.id
    WIZARD[admin_id] = {"active": True, "items": []}

    bot.send_message(
        admin_id,
        "🧙‍♂️ <b>Multi Broadcast Wizard Started</b>\n\n"
        "📌 Text / Photo / Video ကို အများကြီးပို့နိုင်ပါတယ်\n"
        "📌 ပြီးရင် <b>send</b> လို့ရေးပါ\n"
        "📌 ဖျက်ချင်ရင် <b>cancel</b>",
        parse_mode="HTML"
    )

# -----------------------------
# Wizard Collector (STABLE)
# -----------------------------
@bot.message_handler(
    content_types=["text", "photo", "video"],
    func=lambda m: m.from_user.id in WIZARD and WIZARD[m.from_user.id]["active"]
)
def wizard_collector(message):
    admin_id = message.from_user.id
    wizard = WIZARD[admin_id]

    # TEXT
    if message.content_type == "text":
        text = message.text.lower()

        if text == "send":
            finish_wizard(admin_id)
            return

        if text == "cancel":
            WIZARD.pop(admin_id, None)
            bot.send_message(admin_id, "❌ Wizard cancelled")
            return

        wizard["items"].append({
            "type": "text",
            "text": message.text
        })
        bot.send_message(admin_id, "✅ Text added")
        return

    # PHOTO
    if message.content_type == "photo":
        wizard["items"].append({
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": message.caption or ""
        })
        bot.send_message(admin_id, "🖼 Photo added")
        return

    # VIDEO
    if message.content_type == "video":
        wizard["items"].append({
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption or ""
        })
        bot.send_message(admin_id, "🎥 Video added")
        return

# -----------------------------
# Finish Wizard
# -----------------------------
def finish_wizard(admin_id):
    wizard = WIZARD.get(admin_id)

    if not wizard or not wizard["items"]:
        bot.send_message(admin_id, "❌ Nothing to broadcast")
        return

    groups = load_groups()
    success = failed = 0

    for chat_id in groups:
        try:
            for item in wizard["items"]:
                if item["type"] == "text":
                    msg = bot.send_message(chat_id, item["text"])

                elif item["type"] == "photo":
                    msg = bot.send_photo(chat_id, item["file_id"], caption=item["caption"])

                elif item["type"] == "video":
                    msg = bot.send_video(chat_id, item["file_id"], caption=item["caption"])

                if AUTO_PIN:
                    try:
                        bot.pin_chat_message(chat_id, msg.message_id)
                    except:
                        pass

            success += 1
        except Exception as e:
            logging.error(f"Broadcast failed {chat_id}: {e}")
            failed += 1

    bot.send_message(
        admin_id,
        f"✅ <b>Broadcast Completed</b>\n\n"
        f"📤 Success: {success}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML"
    )

    WIZARD.pop(admin_id, None)

# -----------------------------
# Home
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "Telegram Bot is running!"

# -----------------------------
# Webhook
# -----------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(silent=True)
    if update:
        bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200

# -----------------------------
# Welcome
# -----------------------------
def send_welcome(chat_id):
    text = (
        "🌞 သာယာသောနေ့လေးဖြစ်ပါစေ 🥰\n"
        "ချန်နယ်ဝင်ပေးတဲ့အတွက် ကျေးဇူးတင်ပါတယ် 💖"
    )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        InlineKeyboardButton("💬 Chat Group", url="https://t.me/+RqYCRdFavhM0NTc1")
    )

    bot.send_message(chat_id, text, reply_markup=markup)

# -----------------------------
# /start
# -----------------------------
@bot.message_handler(commands=["start"])
def start(message):
    save_group(message.chat.id)
    send_welcome(message.chat.id)

    if message.chat.type == "private" and message.from_user.id in ADMIN_IDS:
        show_admin_panel(message.chat.id)

# -----------------------------
# Admin Panel
# -----------------------------
def show_admin_panel(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📤 Multi Broadcast", callback_data="admin:multi"),
        InlineKeyboardButton(f"📌 Auto Pin: {'ON' if AUTO_PIN else 'OFF'}", callback_data="admin:pin")
    )
    bot.send_message(chat_id, "⚙️ <b>Admin Panel</b>", reply_markup=markup)

# -----------------------------
# Callbacks
# -----------------------------
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    global AUTO_PIN

    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "Not admin")
        return

    if call.data == "admin:multi":
        bot.answer_callback_query(call.id)
        start_simple_wizard(call.message)

    elif call.data == "admin:pin":
        AUTO_PIN = not AUTO_PIN
        bot.answer_callback_query(call.id, f"Auto Pin {'ON' if AUTO_PIN else 'OFF'}")
        show_admin_panel(call.message.chat.id)

# -----------------------------
# Keep Alive (Railway)
# -----------------------------
def keep_alive():
    while True:
        try:
            requests.get(APP_URL, timeout=10)
        except:
            pass
        time.sleep(240)

# -----------------------------
# Webhook Setup
# -----------------------------
def setup_webhook():
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)
    logging.info("Webhook set")

# -----------------------------
# Start
# -----------------------------
if __name__ == "__main__":
    logging.info("Starting Telegram Bot (Railway + Webhook)")
    setup_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
