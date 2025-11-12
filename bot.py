import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import threading
import os

# ============================
# 🔹 Telegram Bot Token
# ============================
BOT_TOKEN = "8406720651:AAEN4Na5i5s9NLGgkFJLEx4rx8XCPSSqbPQ"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ============================
# 🔹 Flask App for Railway
# ============================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram Bot is Running on Railway!"

# ============================
# 🔹 Handle /start Command
# ============================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    text = (
        "<b>🎬 ညီကိုတို့အတွက်အပန်းဖြေရာ 👇</b>\n\n"
        "<b>🎬 Main Channel:</b>\n"
        "<a href='https://t.me/+FS5GVrQz-9xjMWNl'>👉 Join Here</a>\n\n"
        "<b>🎬 Second Chance:</b>\n"
        "<a href='https://t.me/+CziNFfkLJSRjNjBl'>👉 Join Here</a>\n\n"
        "<b>💬 Chat Group 1:</b>\n"
        "<a href='https://t.me/+RqYCRdFavhM0NTc1'>👉 Join Here</a>\n\n"
        "<b>💬 Chat Group 2:</b>\n"
        "<a href='https://t.me/+qOU88Pm12pMzZGM1'>👉 Join Here</a>\n\n"
        "<b>📂 Folders (Dark 4u Collection):</b>\n"
        "<a href='https://t.me/addlist/T_JawSxSbmA3ZTRl'>👉 Click to Open All</a>\n\n"
        "✨ တစ်ခါတည်းအားလုံးကိုတစ်ပြိုင်နက်ဝင်ချင်တဲ့ညီကိုတွေက "
        "<b>အောက်က 📂 Folder Link ကိုနှိပ်ပါ။</b>\n\n"
        "🌞 <i>သာယာသောနေ့လေးဖြစ်ပါစေညီကိုတို့ရေ 🥰</i>\n"
        "💖 <i>ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီတိုင်းကိုလည်း ကျေးဇူးအထူးတင်ပါတယ်။</i>"
    )

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        InlineKeyboardButton("🎬 Second Chance", url="https://t.me/+CziNFfkLJSRjNjBl")
    )
    markup.add(
        InlineKeyboardButton("💬 Chat Group 1", url="https://t.me/+RqYCRdFavhM0NTc1"),
        InlineKeyboardButton("💬 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1")
    )
    markup.add(
        InlineKeyboardButton("📂 Dark 4u Folder", url="https://t.me/addlist/T_JawSxSbmA3ZTRl")
    )

    bot.send_message(chat_id, text, reply_markup=markup)

# ============================
# 🔹 Background Bot Polling
# ============================
threading.Thread(target=lambda: bot.polling(non_stop=True, skip_pending=True)).start()

# ============================
# 🔹 Flask App Run (for Railway)
# ============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
