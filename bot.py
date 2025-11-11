import os
import sys
import telebot
import threading
from dotenv import load_dotenv
from flask import Flask
import logging

# ===== Logging =====
logging.basicConfig(level=logging.INFO)

# ===== Load Config =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN not found in .env file!")
    sys.exit()

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ===== Flask App =====
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running successfully on Railway!"

# ===== Handlers =====
def create_markup_start_help():
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

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = create_markup_start_help()
    markup.add(
        telebot.types.InlineKeyboardButton("🌐 Join All Groups", url="https://t.me/addlist/T_JawSxSbmA3ZTRl")
    )
    bot.send_message(
        message.chat.id,
        """ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵

တစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်ကတော့အောက်ကခလုတ်တွေပါ ❤️

တစ်ခါတည်းဂရုအကုန်ဝင်ချင်တဲ့ညီကိုတွေက‌တော့ “🌐 Join All Groups” ကိုနှိပ်ပါ 👇

သာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘""",
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['help'])
def handle_help(message):
    markup = create_markup_start_help()
    bot.send_message(
        message.chat.id,
        """🆘 <b>အသုံးပြုပုံ</b>

/start - ညီကိုတို့အတွက် အပန်းဖြေရာ စတင်ရန်  
/help - အသုံးပြုပုံလမ်းညွှန် ကြည့်ရန်  
/about - ကြော်ငြာအကြောင်းဆက်သွယ်ရန်  

မေးချင်တာရှိရင် Main Chat မှာ မေးလို့ရပါတယ် 💬""",
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['about'])
def handle_about(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("📩 Contact Now", url="https://t.me/twentyfour7ithinkingaboutyou")
    )
    bot.send_message(
        message.chat.id,
        """📢 <b>ကြော်ငြာကိစ္စများအတွက် ဆက်သွယ်ရန်</b>

👇 @twentyfour7ithinkingaboutyou""",
        reply_markup=markup,
        disable_web_page_preview=True
    )

# ===== Bot Polling in Background =====
def run_bot():
    logging.info("✅ Bot polling started...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)

# ===== Main =====
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"🚀 Flask web server running on port {port} ...")
    app.run(host="0.0.0.0", port=port)
