import telebot
import os
from dotenv import load_dotenv
import threading

# ===== Load Config =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# ===== Clear any existing webhook to avoid 409 conflict =====
bot.remove_webhook()

# ===== Start message (multiline) =====
START_MESSAGE = """ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵

တစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်ကတော့အောက်ကခလုတ်တွေပါ ❤️

တစ်ခါတည်းဂရုအကုန်ဝင်ချင်တဲ့ညီကိုတွေက‌တော့ “🌐 Join All Groups” ကိုနှိပ်ပါ 👇

သာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘"""

# ===== Function to send message with buttons =====
def send_start_message(message):
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

    bot.send_message(
        message.chat.id,
        START_MESSAGE,
        reply_markup=markup,
        disable_web_page_preview=True
    )

# ===== /start command handler =====
@bot.message_handler(commands=['start'])
def handle_start(message):
    threading.Thread(target=send_start_message, args=(message,)).start()

# ===== Run Bot (fast polling) =====
print("✅ Bot is running (Polling mode, conflict-safe)")
bot.polling(none_stop=True, interval=0, timeout=20)
