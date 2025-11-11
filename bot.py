# bot.py
import os
from flask import Flask, request
import telebot

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("❌ BOT_TOKEN or WEBHOOK_URL missing!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===== Webhook Setup =====
def setup_webhook():
    import requests
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    print("✅ Webhook set successfully")

# ===== /start Command =====
START_MESSAGE = """ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵

တစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်ကတော့အောက်ကခလုတ်တွေပါ ❤️

သာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘"""

@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        telebot.types.InlineKeyboardButton("🎵 MV Channel", url="https://t.me/+CziNFfkLJSRjNjBl")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💬 Main Chat", url="https://t.me/+RqYCRdFavhM0NTc1"),
        telebot.types.InlineKeyboardButton("💭 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🌐 Join All Groups", url="https://t.me/addlist/T_JawSxSbmA3ZTRl")
    )
    bot.send_message(message.chat.id, START_MESSAGE, reply_markup=markup, disable_web_page_preview=True)

# ===== /about Command =====
ABOUT_MESSAGE = "ကြော်ငြာကိစ္စများအတွက်ဆက်သွယ်ရန် 👇 @twentyfour7ithinkingaboutyou"

@bot.message_handler(commands=['about'])
def about_handler(message):
    bot.send_message(message.chat.id, ABOUT_MESSAGE)

# ===== Webhook Route =====
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    if json_str:
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    return "!", 200

# ===== Health Check =====
@app.route("/")
def index():
    return "✅ Bot is running!"

# ===== Run App =====
if __name__=="__main__":
    PORT = int(os.environ.get("PORT", 8080))
    setup_webhook()
    app.run(host="0.0.0.0", port=PORT)
