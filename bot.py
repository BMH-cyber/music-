import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
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
        "🌞 သာယာသောနေ့လေးဖြစ်ပါစေညီကိုတို့ရေ 🥰\n"
        "💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီတိုင်းကိုလည်း ကျေးဇူးအထူးတင်ပါတယ်"
    )

    # Buttons (Bottom Click)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        InlineKeyboardButton("🎬 Second Channel", url="https://t.me/+CziNFfkLJSRjNjBl")  # ✅ Name changed
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
