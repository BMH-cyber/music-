# ===== Install dependencies =====
pip install pyTelegramBotAPI==4.12.0 Flask==2.3.6 requests==2.31.0 python-dotenv==1.0.1

# ===== Create bot.py =====
cat <<'EOL' > bot.py
import os
import telebot
from flask import Flask, request
import requests

# ===== Load environment variables =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("❌ BOT_TOKEN or WEBHOOK_URL missing in environment variables!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===== Webhook setup =====
def reset_webhook():
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    except Exception:
        pass

# ===== Common button markup =====
def get_common_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        telebot.types.InlineKeyboardButton("🎵 MV Channel", url="https://t.me/+CziNFfkLJSRjNjBl")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💬 Main Chat", url="https://t.me/+RqYCRdFavhM0NTc1"),
        telebot.types.InlineKeyboardButton("💭 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1")
    )
    return markup

# ===== Handlers =====
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = get_common_markup()
    markup.add(telebot.types.InlineKeyboardButton("🌐 Join All Groups", url="https://t.me/addlist/T_JawSxSbmA3ZTRl"))
    bot.send_message(
        message.chat.id,
        "ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵\n\nတစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်အောက်ကခလုတ်တွေပါ ❤️\n\nတစ်ခါတည်းဂရုအကုန်ဝင်ချင်တဲ့ညီကိုတွေက‌တော့ “🌐 Join All Groups” ကိုနှိပ်ပါ 👇\n\nသာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘",
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['help'])
def handle_help(message):
    markup = get_common_markup()
    bot.send_message(
        message.chat.id,
        "/start - စတင်ရန်\n/help - အသုံးပြုပုံကြည့်ရန်\n/about - ကြော်ငြာအကြောင်းဆက်သွယ်ရန်",
        reply_markup=markup
    )

@bot.message_handler(commands=['about'])
def handle_about(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📩 Contact Now", url="https://t.me/twentyfour7ithinkingaboutyou"))
    bot.send_message(
        message.chat.id,
        "📢 ကြော်ငြာအကြောင်း ဆက်သွယ်ရန်\n\n👇 @twentyfour7ithinkingaboutyou",
        reply_markup=markup
    )

# ===== Webhook route =====
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        if json_str:
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
    except Exception:
        pass
    return "!", 200

# ===== Health check =====
@app.route("/")
def index():
    return "✅ Bot is running successfully!"

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    reset_webhook()
    app.run(host="0.0.0.0", port=PORT)
EOL

# ===== Run bot with gunicorn =====
gunicorn bot:app -b 0.0.0.0:$PORT
