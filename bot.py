import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import os
import time
import threading

# ============================
# 🔹 Telegram Bot Token
# ============================
BOT_TOKEN = "8406720651:AAEN4Na5i5s9NLGgkFJLEx4rx8XCPSSqbPQ"
WEBHOOK_PATH = "/" + BOT_TOKEN
WEBHOOK_URL = "https://music-production-fecd.up.railway.app" + WEBHOOK_PATH

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ============================
# 🔹 Home Route
# ============================
@app.route("/")
def home():
    return "✅ Telegram Bot is running on Railway!"

# ============================
# 🔹 Webhook Route
# ============================
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# ============================
# 🔹 /start Command
# ============================
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    text1 = (
        "🌞 သာယာသောနေ့လေးဖြစ်ပါစေညီကိုတို့ရေ 🥰\n"
        "💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကိုလည်း ကျေးဇူးအထူးတင်ပါတယ်"
    )

    markup1 = InlineKeyboardMarkup(row_width=2)
    markup1.add(
        InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        InlineKeyboardButton("🎬 Second Channel", url="https://t.me/+CziNFfkLJSRjNjBl"),
    )
    markup1.add(
        InlineKeyboardButton("📖 Story Channel", url="https://t.me/+ADv5LABjD2M0ODE1"),
        InlineKeyboardButton("🇯🇵 Japan Channel", url="https://t.me/+eoWKOuTw4OEyMzI1"),
    )
    markup1.add(
        InlineKeyboardButton("🔥 Only Fan Channel", url="https://t.me/+tgso0l2Hti8wYTNl"),
        InlineKeyboardButton("🍑 Hantai Channel", url="https://t.me/+LLM3G7OYBpQzOGZl"),
    )
    markup1.add(
        InlineKeyboardButton("💬 Chat Group 1", url="https://t.me/+RqYCRdFavhM0NTc1"),
        InlineKeyboardButton("💬 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1"),
    )
    markup1.add(
        InlineKeyboardButton("📂 Dark 4u Folder", url="https://t.me/addlist/fRfr-seGpKs3MWFl")
    )

    bot.send_message(chat_id, text1, reply_markup=markup1)

    # Second message (Admin)
    markup2 = InlineKeyboardMarkup()
    markup2.add(
        InlineKeyboardButton("Admin Account", url="https://t.me/twentyfour7ithinkingaboutyou")
    )
    bot.send_message(chat_id, "📢 ကြေငြာကိစ္စများအတွက်ဆက်သွယ်ရန်", reply_markup=markup2)

# ============================
# 🔹 Keep Alive Thread (Optional)
# ============================
def keep_alive():
    while True:
        try:
            print("🔄 Keep-alive ping…")
        except:
            pass
        time.sleep(20)

# ============================
# 🔹 Run App + Webhook
# ============================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print("✅ Webhook Set:", WEBHOOK_URL)

    # Start keep-alive thread
    threading.Thread(target=keep_alive).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
