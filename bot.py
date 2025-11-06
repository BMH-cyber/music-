import os
import telebot
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
from flask import Flask
import threading

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PORT = int(os.getenv("PORT", 3000))

bot = telebot.TeleBot(TOKEN)

# ===== yt-dlp OPTIONS =====
YDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'skip_download': True,
    'quiet': True,
    'extract_flat': True,
}

def search_song(query):
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if 'entries' in result and len(result['entries']) > 0:
                video = result['entries'][0]
                return video.get('webpage_url'), video.get('title')
            else:
                return None, None
    except Exception as e:
        print(f"Error in yt-dlp: {e}")
        return None, None

# ===== Telegram Handlers =====
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.reply_to(message, "မင်္ဂလာပါ! သီချင်းရှာချင်ရင် /play <song name> လို့ရေးပါ။")

@bot.message_handler(commands=['play'])
def play_handler(message):
    query = message.text.replace("/play", "").strip()
    if not query:
        bot.reply_to(message, "ရှာချင်သည့် သီချင်းနာမည်ထည့်ပါ။")
        return

    url, title = search_song(query)
    if url:
        bot.reply_to(message, f"သီချင်းတွေ့ပါသည် 🎵\n{title}\n{url}")
    else:
        bot.reply_to(message, "သီချင်းမတွေ့နိုင်ပါ 😢")

# ===== FLASK KEEP-ALIVE =====
app = Flask("")

@app.route("/")
def home():
    return "Bot is running ✅"

def run():
    app.run(host="0.0.0.0", port=PORT)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

# ===== RUN BOT =====
if __name__ == "__main__":
    keep_alive()
    print("Bot started...")
    bot.infinity_polling()
