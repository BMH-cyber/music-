import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from flask import Flask, request
import os
import threading
import time
import requests

# ============================
# Bot Token
# ============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ============================
# Webhook URL (Correct Version)
# ============================
APP_URL = "https://music-production-fecd.up.railway.app"
WEBHOOK_URL = f"{APP_URL}/{BOT_TOKEN}"


# ============================
# Home Route
# ============================
@app.route("/", methods=["GET"])
def home():
    return "✅ Telegram Bot is running on Railway!"


# ============================
# Webhook Route
# ============================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        if json_data:
            update = telebot.types.Update.de_json(json_data)
            bot.process_new_updates([update])
    except Exception as e:
        print("Webhook Error:", e)

    return "OK", 200


# ============================
# /start Handler
# ============================
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id

    text1 = (
        "🌞 သာယာသောနေ့လေးဖြစ်ပါစေညီကိုတို့ရေ 🥰\n"
        "💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ပါတယ်"
    )

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
    markup2.add(InlineKeyboardButton("Admin Account", url="https://t.me/twentyfour7ithinkingaboutyou"))
    bot.send_message(chat_id, "📢 ကြေငြာကိစ္စများအတွက် ဆက်သွယ်ရန်👇", reply_markup=markup2)

    try:
        photo_url = "https://i.imgur.com/Z6V7wZk.png"
        media_photo = InputMediaPhoto(photo_url, caption="Welcome to our channels!")
        bot.send_media_group(chat_id, [media_photo])
    except Exception as e:
        print("Photo send error:", e)


# ============================
# Keep-alive for Railway Free Plan
# ============================
def keep_alive():
    while True:
        try:
            requests.get(APP_URL)
        except Exception:
            pass

        time.sleep(240)


# ============================
# Run App + Webhook Setup
# ============================
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        print("✅ Webhook set:", WEBHOOK_URL)
    except Exception as e:
        print("Webhook Set Error:", e)

    threading.Thread(target=keep_alive, daemon=True).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
