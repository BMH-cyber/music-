import os
import threading
import time
import requests
import logging
import json
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

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

if not BOT_TOKEN or not APP_URL:
    logging.error("❌ BOT_TOKEN or APP_URL is missing in Environment Variables")
    raise Exception("BOT_TOKEN or APP_URL is missing")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="MarkdownV2")
app = Flask(__name__)

WEBHOOK_URL = f"{APP_URL}/{BOT_TOKEN}"

# -----------------------------
# Admin ID
# -----------------------------
ADMIN_IDS = [5720351176]  # Admin Telegram ID

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
# MarkdownV2 Escape Function
# -----------------------------
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text

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
def send_welcome(chat_id, mention_link=None):
    if mention_link:
        welcome_text = f"🌞 {mention_link}, သာယာသောနေ့လေးဖြစ်ပါစေ 🥰\n" \
                       "💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ပါတယ်"
    else:
        welcome_text = "🌞 သာယာသောနေ့လေးဖြစ်ပါစေ 🥰\n" \
                       "💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ပါတယ်"

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
        bot.send_message(chat_id, welcome_text, reply_markup=markup_channels)
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

# -----------------------------
# New Chat Member Welcome & Auto Track Group
# -----------------------------
@bot.message_handler(content_types=["new_chat_members"])
def new_member_welcome(message):
    save_group(message.chat.id)
    for member in message.new_chat_members:
        mention_text = None
        if getattr(member, "username", None):
            mention_text = f"@{member.username}"
        else:
            names = []
            if getattr(member, "first_name", None):
                names.append(member.first_name)
            if getattr(member, "last_name", None):
                names.append(member.last_name)
            if names:
                mention_text = " ".join(names)

        if mention_text:
            mention_text = escape_markdown(mention_text)
            mention_link = f"[{mention_text}](tg://user?id={member.id})"
            send_welcome(message.chat.id, mention_link=mention_link)
        else:
            send_welcome(message.chat.id)  # no name to mention

# -----------------------------
# /broadcast Command (Webhook Compatible)
# -----------------------------
@bot.message_handler(commands=["broadcast"])
def broadcast_start(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ သင့်မှာ permission မရှိပါ")
        return
    bot.send_message(
        message.chat.id,
        "📝 ကြေငြာမယ့်စာကိုရိုက်ထည့်ပါ (Text / Photo / Video)",
        reply_markup=ForceReply(selective=True)
    )

@bot.message_handler(func=lambda m: m.reply_to_message and "ကြေငြာမယ့်စာကိုရိုက်ထည့်ပါ" in m.reply_to_message.text)
def broadcast_reply(message):
    if message.from_user.id not in ADMIN_IDS:
        return

    targets = load_groups()

    try:
        if message.content_type == "text":
            text = message.text
            for chat_id in targets:
                try: bot.send_message(chat_id, text, parse_mode="MarkdownV2")
                except: continue
        elif message.content_type == "photo":
            caption = message.caption if message.caption else ""
            for chat_id in targets:
                try: bot.send_photo(chat_id, message.photo[-1].file_id, caption=caption)
                except: continue
        elif message.content_type == "video":
            caption = message.caption if message.caption else ""
            for chat_id in targets:
                try: bot.send_video(chat_id, message.video.file_id, caption=caption)
                except: continue
        bot.send_message(message.chat.id, "✅ ကြေငြာပြီးပါပြီ")
    except Exception as e:
        logging.error("Broadcast failed: %s", e)
        bot.send_message(message.chat.id, f"❌ Broadcast failed: {e}")

# -----------------------------
# Keep-Alive Thread
# -----------------------------
def keep_alive():
    while True:
        try:
            resp = requests.get(APP_URL, timeout=10)
            logging.info("Keep-alive ping response: %s", resp.status_code)
        except Exception as e:
            logging.warning("Keep-alive ping failed: %s", e)
        time.sleep(240)

# -----------------------------
# Setup Webhook
# -----------------------------
def setup_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info("✅ Webhook set: %s", WEBHOOK_URL)
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
