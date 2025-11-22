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
# Logging Setup
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------------
# Environment Variables
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

WEBHOOK_URL = f"{APP_URL}/{BOT_TOKEN}"

# -----------------------------
# Admin IDs (multi-admin support)
# -----------------------------
ADMIN_IDS = [5720351176, 6920736354, 7906327556]  # Add more IDs here

# -----------------------------
# Auto Join Groups Storage
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
        logging.info(f"New group saved: {chat_id}")

# -----------------------------
# Broadcast Settings
# -----------------------------
LAST_BROADCAST_MSG = None
AUTO_PIN = False

# -----------------------------
# Wizard State Storage
# -----------------------------
WIZARD_DATA = {}  # {admin_id: {"text": "", "media": [], "buttons": []}}

# -----------------------------
# Home Route
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Bot is running!"

# -----------------------------
# Webhook Route
# -----------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        if json_data:
            update = telebot.types.Update.de_json(json_data)
            bot.process_new_updates([update])
        else:
            logging.warning("Webhook received empty JSON")
    except Exception as e:
        logging.error("❌ Webhook processing error: %s", e)
    return "OK", 200

# -----------------------------
# Send Welcome Function
# -----------------------------
def send_welcome(chat_id, mention=None):
    text = f"🌞 {mention}, သာယာသောနေ့လေးဖြစ်ပါစေ 🥰\n💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ပါတယ်" if mention else "🌞 သာယာသောနေ့လေးဖြစ်ပါစေ 🥰\n💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ပါတယ်"

    markup_channels = InlineKeyboardMarkup(row_width=2)
    markup_channels.add(
        InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        InlineKeyboardButton("🎬 Second Channel", url="https://t.me/+CziNFfkLJSRjNjBl"),
        InlineKeyboardButton("📖 Story Channel", url="https://t.me/+ADv5LABjD2M0ODE1"),
        InlineKeyboardButton("🇯🇵 Japan Channel", url="https://t.me/+eoWKOuTw4OEyMzI1"),
        InlineKeyboardButton("🔥 Only Fan Channel", url="https://t.me/+tgso0l2Hti8wYTNl"),
        InlineKeyboardButton("🍑 Hantai Channel", url="https://t.me/+LLM3G7OYBpQzOGZl"),
        InlineKeyboardButton("💬 Chat Group 1", url="https://t.me/+RqYCRdFavhM0NTc1"),
        InlineKeyboardButton("💬 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1"),
        InlineKeyboardButton("📂 Dark 4u Folder", url="https://t.me/addlist/fRfr-seGpKs3MWFl")
    )

    try:
        bot.send_message(chat_id, text, reply_markup=markup_channels)
    except Exception as e:
        logging.error("❌ Error sending welcome channels: %s", e)

    markup_admin = InlineKeyboardMarkup()
    markup_admin.add(
        InlineKeyboardButton("Admin Account", url="https://t.me/twentyfour7ithinkingaboutyou")
    )

    try:
        bot.send_message(chat_id, "📢 ကြေငြာများအတွက် ဆက်သွယ်ရန်👇", reply_markup=markup_admin)
    except Exception as e:
        logging.error("❌ Error sending admin contact: %s", e)

# -----------------------------
# /start Command
# -----------------------------
@bot.message_handler(commands=["start"])
def start(message):
    send_welcome(message.chat.id)
    save_group(message.chat.id)

    if message.from_user.id in ADMIN_IDS:
        show_admin_panel(message.chat.id)

# -----------------------------
# Admin Panel Menu
# -----------------------------
def show_admin_panel(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📝 Broadcast Text", callback_data="admin:broadcast_text"),
        InlineKeyboardButton("📸 Broadcast Photo", callback_data="admin:broadcast_photo"),
        InlineKeyboardButton("🎥 Broadcast Video", callback_data="admin:broadcast_video"),
        InlineKeyboardButton("🖋 Multi Broadcast Wizard", callback_data="admin:multi_broadcast"),
        InlineKeyboardButton(f"📌 Auto-Pin: {'ON' if AUTO_PIN else 'OFF'}", callback_data="admin:toggle_pin")
    )
    bot.send_message(chat_id, "⚙️ Admin Panel - Main Menu", reply_markup=markup)

# -----------------------------
# Callback Handler
# -----------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ You are not admin", show_alert=True)
        return

    data = call.data

    if data == "admin:toggle_pin":
        global AUTO_PIN
        AUTO_PIN = not AUTO_PIN
        bot.answer_callback_query(call.id, f"Auto-Pin {'Enabled' if AUTO_PIN else 'Disabled'}")
        show_admin_panel(call.message.chat.id)

    elif data.startswith("admin:broadcast_"):
        msg_type = data.split("_")[1]
        bot.answer_callback_query(call.id, f"Send {msg_type} in next message")
        bot.register_next_step_handler(call.message, lambda msg, t=msg_type: handle_broadcast_input(msg, t))

    elif data == "admin:multi_broadcast":
        bot.answer_callback_query(call.id)
        start_wizard(call.message)

# -----------------------------
# Broadcast Handler (single type)
# -----------------------------
def handle_broadcast_input(message, msg_type):
    if msg_type == "text":
        _broadcast_text(message.text, message.from_user.id)
    elif msg_type == "photo":
        if message.content_type == "photo":
            _broadcast_photo(message.photo[-1].file_id, message.caption or "", message.from_user.id)
        else:
            bot.reply_to(message, "❌ Please send a photo")
    elif msg_type == "video":
        if message.content_type == "video":
            _broadcast_video(message.video.file_id, message.caption or "", message.from_user.id)
        else:
            bot.reply_to(message, "❌ Please send a video")

# -----------------------------
# Broadcast Functions
# -----------------------------
def _broadcast_text(text, admin_id):
    global LAST_BROADCAST_MSG
    groups = load_groups()
    success, failed = 0, 0
    for chat_id in groups:
        try:
            msg = bot.send_message(chat_id, text)
            if AUTO_PIN:
                try:
                    bot.pin_chat_message(chat_id, msg.message_id)
                except: pass
            success += 1
        except:
            failed += 1
    if LAST_BROADCAST_MSG:
        try: bot.delete_message(admin_id, LAST_BROADCAST_MSG)
        except: pass
    sent = bot.send_message(admin_id, f"✅ Broadcast Completed: {success} success, {failed} failed")
    LAST_BROADCAST_MSG = sent.message_id

def _broadcast_photo(file_id, caption, admin_id):
    global LAST_BROADCAST_MSG
    groups = load_groups()
    success, failed = 0, 0
    for chat_id in groups:
        try:
            msg = bot.send_photo(chat_id, file_id, caption=caption)
            if AUTO_PIN:
                try: bot.pin_chat_message(chat_id, msg.message_id)
                except: pass
            success += 1
        except:
            failed += 1
    if LAST_BROADCAST_MSG:
        try: bot.delete_message(admin_id, LAST_BROADCAST_MSG)
        except: pass
    sent = bot.send_message(admin_id, f"✅ Broadcast Completed: {success} success, {failed} failed")
    LAST_BROADCAST_MSG = sent.message_id

def _broadcast_video(file_id, caption, admin_id):
    global LAST_BROADCAST_MSG
    groups = load_groups()
    success, failed = 0, 0
    for chat_id in groups:
        try:
            msg = bot.send_video(chat_id, file_id, caption=caption)
            if AUTO_PIN:
                try: bot.pin_chat_message(chat_id, msg.message_id)
                except: pass
            success += 1
        except:
            failed += 1
    if LAST_BROADCAST_MSG:
        try: bot.delete_message(admin_id, LAST_BROADCAST_MSG)
        except: pass
    sent = bot.send_message(admin_id, f"✅ Broadcast Completed: {success} success, {failed} failed")
    LAST_BROADCAST_MSG = sent.message_id

# -----------------------------
# New Chat Member Welcome
# -----------------------------
@bot.message_handler(content_types=["new_chat_members"])
def new_member_welcome(message):
    save_group(message.chat.id)
    for member in message.new_chat_members:
        mention = getattr(member, "username", None)
        if mention: mention = f"@{mention}"
        else: mention = getattr(member, "first_name", None) or getattr(member, "last_name", "")
        send_welcome(message.chat.id, mention)

# -----------------------------
# Multi Broadcast Wizard Steps
# -----------------------------
def start_wizard(message):
    admin_id = message.from_user.id
    WIZARD_DATA[admin_id] = {"text": "", "media": [], "buttons": []}
    bot.send_message(admin_id, "📝 Step 1: Send your text message (or type 'skip')")
    bot.register_next_step_handler(message, wizard_step_text)

def wizard_step_text(message):
    admin_id = message.from_user.id
    if message.text.lower() != "skip":
        WIZARD_DATA[admin_id]["text"] = message.text
    bot.send_message(admin_id, "📸 Step 2: Send photos/videos one by one. Type 'done' when finished.")
    bot.register_next_step_handler(message, wizard_step_media)

def wizard_step_media(message):
    admin_id = message.from_user.id
    data = WIZARD_DATA[admin_id]

    if message.text and message.text.lower() == "done":
        bot.send_message(admin_id, "🔗 Step 3: Add buttons. Format: Button Text | URL. Type 'done' when finished.")
        bot.register_next_step_handler(message, wizard_step_buttons)
        return

    if message.content_type == "photo":
        data["media"].append({"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""})
    elif message.content_type == "video":
        data["media"].append({"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""})
    else:
        bot.reply_to(message, "❌ Please send photo or video, or type 'done'")

    bot.register_next_step_handler(message, wizard_step_media)

def wizard_step_buttons(message):
    admin_id = message.from_user.id
    data = WIZARD_DATA[admin_id]

    if message.text.lower() == "done":
        preview_and_send(admin_id)
        return

    if "|" in message.text:
        text, url = map(str.strip, message.text.split("|", 1))
        data["buttons"].append({"text": text, "url": url})
    else:
        bot.reply_to(message, "❌ Invalid format. Use: Button Text | URL")

    bot.register_next_step_handler(message, wizard_step_buttons)

def preview_and_send(admin_id):
    data = WIZARD_DATA[admin_id]
    markup = None
    if data["buttons"]:
        markup = InlineKeyboardMarkup()
        for btn in data["buttons"]:
            markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))

    preview_text = data.get("text") or "📎 Media Only Message"
    bot.send_message(admin_id, f"✅ Preview:\n{preview_text}", reply_markup=markup)

    groups = load_groups()
    success, failed = 0, 0

    for chat_id in groups:
        try:
            # Send text
            if data.get("text"):
                msg = bot.send_message(chat_id, data["text"], reply_markup=markup)
                if AUTO_PIN:
                    try: bot.pin_chat_message(chat_id, msg.message_id)
                    except: pass

            # Send media
            for m in data["media"]:
                if m["type"] == "photo":
                    msg = bot.send_photo(chat_id, m["file_id"], caption=m.get("caption", ""))
                    if AUTO_PIN:
                        try: bot.pin_chat_message(chat_id, msg.message_id)
                        except: pass
                elif m["type"] == "video":
                    msg = bot.send_video(chat_id, m["file_id"], caption=m.get("caption", ""))
                    if AUTO_PIN:
                        try: bot.pin_chat_message(chat_id, msg.message_id)
                        except: pass

            success += 1
        except Exception as e:
            logging.error(f"Failed to send to {chat_id}: {e}")
            failed += 1

    bot.send_message(admin_id, f"✅ Broadcast Done: {success} success, {failed} failed")
    WIZARD_DATA.pop(admin_id, None)

# -----------------------------
# Keep-Alive Thread
# -----------------------------
def keep_alive():
    while True:
        try:
            requests.get(APP_URL, timeout=10)
        except: pass
        time.sleep(240)

# -----------------------------
# Setup Webhook
# -----------------------------
def setup_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info("✅ Webhook set")
    except Exception as e:
        logging.error("❌ Webhook setup error: %s", e)
        raise

# -----------------------------
# Start Bot
# -----------------------------
if __name__ == "__main__":
    logging.info("Starting bot...")
    setup_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    logging.info("Bot is ready. Run Flask via Gunicorn, NOT app.run()")
