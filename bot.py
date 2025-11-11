import os
import telebot
from flask import Flask, request

# ===== Load Config =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

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

# ===== Webhook Route =====
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# ===== Set Webhook Route =====
@app.route("/")
def index():
    return "✅ Bot is running successfully on Railway!"

# ===== Run Flask =====
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://your-app.up.railway.app/<BOT_TOKEN>
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=PORT)
