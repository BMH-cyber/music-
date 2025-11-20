import os
import threading
import time
import requests
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Load Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 8080))

if not BOT_TOKEN or not APP_URL:
    raise Exception("❌ BOT_TOKEN or APP_URL is missing in Environment Variables")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

WEBHOOK_URL = f"{APP_URL}/{BOT_TOKEN}"

# -----------------------------
# Home route (Uptime check)
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Bot is running!"

# -----------------------------
# Webhook route
# -----------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    except Exception as e:
        print("❌ Webhook Error:", e)
    return "OK", 200

# -----------------------------
# /start command
# -----------------------------
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    text1 = "🌞 သာယာသောနေ့လေးဖြစ်ပါစေ 🥰\n💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ပါတယ်"

    markup1 = InlineKeyboardMarkup(row_width=2)
    markup1.add(
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
    bot.send_message(chat_id, text1, reply_markup=markup1)

    markup2 = InlineKeyboardMarkup()
    markup2.add(
        InlineKeyboardButton("Admin Account", url="https://t.me/twentyfour7ithinkingaboutyou")
    )
    bot.send_message(chat_id, "📢 ကြေငြာများအတွက် ဆက်သွယ်ရန်👇", reply_markup=markup2)

    try:
        photo_url = "https://i.imgur.com/Z6V7wZk.png"
        bot.send_photo(chat_id, photo_url, caption="Welcome to our channels!")
    except Exception as e:
        print("❌ Photo Error:", e)

# -----------------------------
# Keep-alive thread (optional)
# -----------------------------
def keep_alive():
    while True:
        try:
            requests.get(APP_URL)
        except:
            pass
        time.sleep(240)  # every 4 min

# -----------------------------
# Set webhook before starting server
# -----------------------------
def setup_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        print("✅ Webhook set:", WEBHOOK_URL)
    except Exception as e:
        print("❌ Webhook setup error:", e)

setup_webhook()
threading.Thread(target=keep_alive, daemon=True).start()

# -----------------------------
# Run Flask app via Gunicorn (no app.run)
# -----------------------------
