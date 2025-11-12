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
# 🔹 Function to send second message (Admin)
# ============================
def send_second_message(chat_id):
    text2 = "📢 ကြေငြာကိစ္စများအတွက်ဆက်သွယ်ရန်"
    markup2 = InlineKeyboardMarkup()
    markup2.add(
        InlineKeyboardButton("Admin Account", url="https://t.me/twentyfour7ithinkingaboutyou")
    )
    bot.send_message(chat_id, text2, reply_markup=markup2)

# ============================
# 🔹 Handle /start Command
# ============================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    # 🔹 ပထမ Message (Main Buttons)
    text1 = (
        "🌞 သာယာသောနေ့လေးဖြစ်ပါစေညီကိုတို့ရေ 🥰\n"
        "💖 ချန်နယ်ဝင်ပေးတဲ့တစ်ယောက်ချင်းစီကိုလည်း ကျေးဇူးအထူးတင်ပါတယ်"
    )

    markup1 = InlineKeyboardMarkup(row_width=2)
    markup1.add(
        InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        InlineKeyboardButton("🎬 Second Channel", url="https://t.me/+CziNFfkLJSRjNjBl")
    )
    markup1.add(
        InlineKeyboardButton("📖 Story Channel", url="https://t.me/+ADv5LABjD2M0ODE1"),
        InlineKeyboardButton("🇯🇵 Japan Channel", url="https://t.me/+eoWKOuTw4OEyMzI1")
    )
    # 🔹 Only Fan + Hantai Channel row
    markup1.add(
        InlineKeyboardButton("🔥 Only Fan Channel", url="https://t.me/+tgso0l2Hti8wYTNl"),
        InlineKeyboardButton("🍑 Hantai Channel", url="https://t.me/+LLM3G7OYBpQzOGZl")
    )
    markup1.add(
        InlineKeyboardButton("💬 Chat Group 1", url="https://t.me/+RqYCRdFavhM0NTc1"),
        InlineKeyboardButton("💬 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1")
    )
    # 🔹 Updated Dark 4u Folder link
    markup1.add(
        InlineKeyboardButton("📂 Dark 4u Folder", url="https://t.me/addlist/fRfr-seGpKs3MWFl")
    )

    bot.send_message(chat_id, text1, reply_markup=markup1)

    # 🔹 Thread နဲ့ ဒုတိယ message (Admin Account)
    threading.Thread(target=send_second_message, args=(chat_id,)).start()

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
