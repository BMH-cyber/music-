import telebot, threading, os, json, requests, time
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from yt_dlp import YoutubeDL
from PIL import Image
from io import BytesIO

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATA_FILE = Path("music_mm_subscribers.json")
DOWNLOAD_DIR = Path("downloads_music_mm")
DOWNLOAD_DIR.mkdir(exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# ===== FLASK KEEP-ALIVE =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# ===== SUBSCRIBERS DATA =====
if DATA_FILE.exists():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        subscribers = json.load(f)
else:
    subscribers = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, indent=2, ensure_ascii=False)

# ===== DOWNLOAD OPTIONS =====
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "nocheckcertificate": True,
    "noprogress": True,
    "extractaudio": True,
    "audioformat": "mp3",
    "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "ignoreerrors": True,
    "no_warnings": True,
}

# ===== COMMAND HANDLERS =====
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    bot.reply_to(msg, "🎶 မင်္ဂလာပါ! သီချင်းနာမည်ရိုက်ပြီး /play နဲ့ရှာနိုင်ပါတယ်။\nဥပမာ: `/play faded`", parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def about_cmd(msg):
    bot.reply_to(msg, "🎧 Music Bot\nCreated for Telegram with ❤️")

@bot.message_handler(commands=['subscribe'])
def sub_cmd(msg):
    user_id = str(msg.chat.id)
    subscribers[user_id] = True
    save_data()
    bot.reply_to(msg, "✅ သီချင်းအသစ်တွေ ရရှိနေပါပြီ!")

@bot.message_handler(commands=['unsubscribe'])
def unsub_cmd(msg):
    user_id = str(msg.chat.id)
    if user_id in subscribers:
        del subscribers[user_id]
        save_data()
        bot.reply_to(msg, "❌ စာရင်းမှ ဖယ်ရှားပြီးပါပြီ။")
    else:
        bot.reply_to(msg, "မရှိသေးပါ။")

@bot.message_handler(commands=['play'])
def play_cmd(msg):
    query = msg.text.replace("/play", "").strip()
    if not query:
        bot.reply_to(msg, "သီချင်းနာမည်ရေးပါဦး 🎵")
        return

    bot.reply_to(msg, f"🔎 '{query}' ကိုရှာနေပါတယ်...")
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not info or "entries" not in info or not info["entries"]:
                bot.reply_to(msg, "😔 မတွေ့ပါ။ ပြန်စမ်းကြည့်ပါ။")
                return
            entry = info["entries"][0]
            url = entry["url"]
            title = entry["title"]

            bot.reply_to(msg, f"⬇️ '{title}' ကို download လုပ်နေပါတယ်...")

            # Download
            ydl.download([f"https://www.youtube.com/watch?v={entry['id']}"])

            # Find downloaded file
            file_path = next(DOWNLOAD_DIR.glob("*.mp3"), None)
            if not file_path:
                bot.reply_to(msg, "❌ Download မအောင်မြင်ပါ။")
                return

            with open(file_path, "rb") as audio:
                bot.send_audio(msg.chat.id, audio, title=title)
            os.remove(file_path)

    except Exception as e:
        bot.reply_to(msg, f"❌ Error: {e}")

@bot.message_handler(commands=['stop'])
def stop_cmd(msg):
    bot.reply_to(msg, "⏹ Bot ရပ်သွားပါပြီ။ (24/7 မထိခိုက်ပါ)")

# ===== START BOT =====
def run_bot():
    print("✅ Bot started successfully (Railway 24/7 ready)")
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    run_bot()
