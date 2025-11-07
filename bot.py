# ===== music_bot_v20_fast.py =====
import os, sys, subprocess, tempfile, random, threading
from datetime import datetime

import telebot
from telebot import types
from dotenv import load_dotenv
from flask import Flask
import yt_dlp

# ===== AUTO INSTALL =====
REQUIRED = ["pyTelegramBotAPI", "yt-dlp", "python-dotenv", "flask"]
for pkg in REQUIRED:
    try:
        __import__(pkg.split("-")[0])
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg])

# ===== LOAD CONFIG =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
PORT = int(os.environ.get("PORT", random.randint(2000, 9999)))
MAX_FILESIZE_MB = 30
START_TIME = datetime.utcnow()

# ===== COMMAND: /start =====
@bot.message_handler(commands=['start'])
def start_message(message):
    text = (
        "🎵 *Music Search Bot* မှကြိုဆိုပါတယ်!\n\n"
        "အသုံးပြုပုံ:\n"
        "▫ သီချင်းနာမည်ကို ရိုက်ထည့်ပါ — ဥပမာ: `Perfect Ed Sheeran`\n"
        "▫ Bot က YouTube မှ mp3 ဖိုင်အဖြစ်ပေးပါမယ် (အမြန်ဆုံး)\n\n"
        "🔹 ဖိုင်အရွယ်အစားအများဆုံး: 30MB\n"
        "🔹 အချို့သီချင်းများကို YouTube မှတင်မရနိုင်ပါ\n\n"
        "✅ သီချင်းနာမည်ကို စမ်းရိုက်ပါ —"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ===== SONG SEARCH + DOWNLOAD =====
@bot.message_handler(func=lambda msg: True)
def handle_song_request(message):
    query = message.text.strip()
    if not query:
        return
    bot.reply_to(message, f"🔍 '{query}' ကိုရှာနေပါတယ်... ခဏစောင့်ပါ။")
    
    threading.Thread(target=download_and_send_song, args=(message, query)).start()

def download_and_send_song(message, query):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmpdir, "song.%(ext)s"),
                "quiet": True,
                "noplaylist": True,
                "extractaudio": True,
                "audioformat": "mp3",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",  # smaller file, faster
                }],
            }

            # ytsearch1: automatically search & download first result
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"ytsearch1:{query}"])

            # Get mp3 file
            mp3_file = None
            for f in os.listdir(tmpdir):
                if f.endswith(".mp3"):
                    mp3_file = os.path.join(tmpdir, f)
                    break

            if not mp3_file:
                bot.reply_to(message, "❌ MP3 ဖိုင်မတွေ့ပါ။")
                return

            # Check size
            if os.path.getsize(mp3_file) > MAX_FILESIZE_MB * 1024 * 1024:
                bot.reply_to(message, "❌ ဖိုင်အရွယ်အစား 30MB ကျော်နေပါတယ်။")
                return

            # Send audio
            with open(mp3_file, "rb") as audio:
                bot.send_audio(message.chat.id, audio, caption=f"🎵 {query}")

    except Exception as e:
        bot.reply_to(message, f"❌ အမှားတစ်ခုဖြစ်ခဲ့ပါ: {e}")

# ===== FLASK KEEP ALIVE (RAILWAY / REPLIT SAFE) =====
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=PORT, threaded=True)

# ===== START BOT =====
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    print(f"✅ Bot is running on port {PORT}")
    bot.infinity_polling(skip_pending=True, timeout=60)
