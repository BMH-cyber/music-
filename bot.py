# ===== music_bot_v19.py =====
import os, sys, subprocess, asyncio, tempfile, random
import telebot
from telebot import types
from dotenv import load_dotenv
from datetime import datetime
import yt_dlp
import aiohttp
from flask import Flask

# ===== AUTO INSTALL =====
REQUIRED = ["pyTelegramBotAPI", "yt-dlp", "aiohttp", "python-dotenv", "flask"]
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
PORT = random.randint(2000, 9999)
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

    asyncio.run(download_and_send_song(message, query))

async def download_and_send_song(message, query):
    try:
        # YouTube ရှာဖွေခြင်း
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as resp:
                html = await resp.text()
        video_ids = [part.split('"')[0] for part in html.split('watch?v=')[1:]]
        if not video_ids:
            bot.reply_to(message, "❌ သီချင်းမတွေ့ပါ။ ထပ်စမ်းပါ။")
            return
        video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"

        # Download temp dir
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
                    "preferredquality": "192",
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # Get mp3 path
            for f in os.listdir(tmpdir):
                if f.endswith(".mp3"):
                    filepath = os.path.join(tmpdir, f)
                    break
            else:
                bot.reply_to(message, "❌ MP3 ဖိုင်မတွေ့ပါ။")
                return

            # File size check
            if os.path.getsize(filepath) > MAX_FILESIZE_MB * 1024 * 1024:
                bot.reply_to(message, "❌ ဖိုင်အရွယ်အစား 30MB ကျော်နေပါတယ်။")
                return

            # Send audio
            with open(filepath, "rb") as audio:
                bot.send_audio(message.chat.id, audio, caption=f"🎵 {query}")

    except Exception as e:
        bot.reply_to(message, f"❌ အမှားတစ်ခုဖြစ်ခဲ့ပါ: {e}")

# ===== FLASK KEEP ALIVE (RAILWAY / TERMUX PORT SAFE) =====
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=PORT, threaded=True)

# ===== START BOT =====
if __name__ == "__main__":
    import threading
    threading.Thread(target=run_flask).start()
    print(f"✅ Bot is running on port {PORT}")
    bot.infinity_polling(skip_pending=True, timeout=60)
