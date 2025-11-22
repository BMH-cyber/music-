import os
import threading
import time
import requests
import logging
import json
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo

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
# Admin IDs
# -----------------------------
ADMIN_IDS = [5720351176, 6920736354, 7906327556]

# -----------------------------
# Groups Storage
# -----------------------------
GROUPS_FILE = "joined_groups.json"
AUTO_PIN = False
BROADCAST_DATA = {}  # Admin id -> broadcast data

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
# Flask Routes
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Bot is running!"

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
        logging.error(f"Webhook processing error: {e}")
    return "OK", 200

# -----------------------------
# Send Welcome
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
        logging.error(f"❌ Error sending welcome channels: {e}")

    markup_admin = InlineKeyboardMarkup()
    markup_admin.add(
        InlineKeyboardButton("Admin Account", url="https://t.me/twentyfour7ithinkingaboutyou")
    )

    try:
        bot.send_message(chat_id, "📢 ကြေငြာများအတွက် ဆက်သွယ်ရန်👇", reply_markup=markup_admin)
    except Exception as e:
        logging.error(f"❌ Error sending admin contact: {e}")

# -----------------------------
# Admin Panel
# -----------------------------
def show_admin_panel(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f"📌 Auto-Pin: {'ON' if AUTO_PIN else 'OFF'}", callback_data="admin:toggle_pin"),
        InlineKeyboardButton("🖋 Broadcast Wizard", callback_data="admin:broadcast_wizard")
    )
    bot.send_message(chat_id, "⚙️ Admin Panel - Main Menu", reply_markup=markup)

# -----------------------------
# /start
# -----------------------------
@bot.message_handler(commands=["start"])
def start(message):
    send_welcome(message.chat.id)
    save_group(message.chat.id)
    if message.from_user.id in ADMIN_IDS:
        try:
            show_admin_panel(message.chat.id)
        except Exception as e:
            logging.error(f"Admin panel error: {e}")
            bot.send_message(message.chat.id, "⚠️ Admin panel error, check logs")

# -----------------------------
# Callback Handler
# -----------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ You are not admin", show_alert=True)
        return

    if data == "admin:toggle_pin":
        global AUTO_PIN
        AUTO_PIN = not AUTO_PIN
        bot.answer_callback_query(call.id, f"Auto-Pin {'Enabled' if AUTO_PIN else 'Disabled'}")
        show_admin_panel(call.message.chat.id)

    elif data == "admin:broadcast_wizard":
        bot.answer_callback_query(call.id)
        # Initialize admin broadcast session
        BROADCAST_DATA[user_id] = {"text": None, "media": [], "buttons": []}
        msg = bot.send_message(user_id, "📝 Send your broadcast message.\n- Text\n- Media (photo/video/document)\n- Buttons: `Name | URL`\nWhen done, type 'send'")
        # Step handler: content_types full list
        bot.register_next_step_handler(msg, broadcast_wizard_step)

    elif data == "confirm_broadcast":
        broadcast_message(user_id)

# -----------------------------
# Broadcast Wizard (Step-Free)
# -----------------------------
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS, content_types=["text","photo","video","document"])
def broadcast_wizard_step(message):
    user_id = message.from_user.id
    if user_id not in BROADCAST_DATA:
        BROADCAST_DATA[user_id] = {"text": None, "media": [], "buttons": []}
    data = BROADCAST_DATA[user_id]

    if message.content_type == "text":
        if message.text.lower() == "send":
            # Preview + Confirm
            markup = None
            if data["buttons"]:
                markup = InlineKeyboardMarkup()
                for btn in data["buttons"]:
                    markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))

            preview_text = data.get("text") or "📎 Media/Link Only Message"
            bot.send_message(user_id, f"✅ Preview:\n{preview_text}", reply_markup=markup)

            confirm_markup = InlineKeyboardMarkup()
            confirm_markup.add(InlineKeyboardButton("🚀 Send Broadcast", callback_data="confirm_broadcast"))
            bot.send_message(user_id, "Press below to broadcast to all groups", reply_markup=confirm_markup)
            return

        # Button check
        if "|" in message.text:
            name, url = map(str.strip, message.text.split("|", 1))
            data["buttons"].append({"text": name, "url": url})
        else:
            data["text"] = message.text

    elif message.content_type == "photo":
        data["media"].append({"type":"photo","file_id":message.photo[-1].file_id,"caption":message.caption or ""})
    elif message.content_type == "video":
        data["media"].append({"type":"video","file_id":message.video.file_id,"caption":message.caption or ""})
    elif message.content_type == "document":
        data["media"].append({"type":"document","file_id":message.document.file_id,"caption":message.caption or ""})
    else:
        bot.reply_to(message, "❌ Unsupported type")

# -----------------------------
# Broadcast Function (Multi-Media)
# -----------------------------
def broadcast_message(admin_id):
    if admin_id not in BROADCAST_DATA:
        bot.send_message(admin_id,"❌ No broadcast data")
        return

    data = BROADCAST_DATA[admin_id]
    groups = load_groups()
    success, failed = 0,0

    markup = None
    if data["buttons"]:
        markup = InlineKeyboardMarkup()
        for btn in data["buttons"]:
            markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]))

    for chat_id in groups:
        try:
            # Send text first
            if data.get("text"):
                msg = bot.send_message(chat_id, data["text"], reply_markup=markup)
                if AUTO_PIN:
                    try: bot.pin_chat_message(chat_id,msg.message_id)
                    except: pass

            # Send media
            media_list = data.get("media", [])
            if media_list:
                group = []
                for m in media_list:
                    if m["type"]=="photo":
                        group.append(InputMediaPhoto(m["file_id"], caption=m.get("caption","")))
                    elif m["type"]=="video":
                        group.append(InputMediaVideo(m["file_id"], caption=m.get("caption","")))
                    else:
                        # document: send separately
                        msg = bot.send_document(chat_id, m["file_id"], caption=m.get("caption",""))
                        if AUTO_PIN:
                            try: bot.pin_chat_message(chat_id,msg.message_id)
                            except: pass

                if group:
                    bot.send_media_group(chat_id, group)

            success += 1
        except Exception as e:
            logging.error(f"Failed to send to {chat_id}: {e}")
            failed += 1

    bot.send_message(admin_id,f"✅ Broadcast Done: {success} success, {failed} failed")
    BROADCAST_DATA.pop(admin_id,None)

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
# Keep Alive
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
        logging.error(f"❌ Webhook setup error: {e}")
        raise

# -----------------------------
# Start Bot
# -----------------------------
if __name__ == "__main__":
    logging.info("Starting bot...")
    setup_webhook()
    threading.Thread(target=keep_alive, daemon=True).start()
    logging.info("Bot is ready. Run Flask via Gunicorn, NOT app.run()")
