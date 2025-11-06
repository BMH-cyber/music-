import os
import threading
import subprocess
import tempfile
import shutil
import time
import json
from pathlib import Path
from datetime import datetime
from queue import Queue
from io import BytesIO

import telebot
from PIL import Image
import requests
from flask import Flask
from dotenv import load_dotenv

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DOWNLOAD_DIR = Path("downloads_music4u")
MAX_FILESIZE = 50 * 1024 * 1024   # Telegram max 50MB
START_TIME = datetime.utcnow()

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR.mkdir(exist_ok=True)
active_downloads = {}
lock = threading.Lock()

# ===== FLASK KEEP ALIVE =====
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Music 4U Bot is Alive and Healthy!"

def run_server():
    app.run(host="0.0.0.0", port=8080, debug=False)

def keep_alive():
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()

# ===== BASIC COMMANDS =====
@bot.message_handler(commands=["start", "help"])
def start(msg):
    bot.reply_to(msg, (
        "🎶 *Welcome to Music 4U*\n\n"
        "သီချင်းရှာရန်: `/play <နာမည်>` သို့မဟုတ် YouTube link\n"
        "/stop - ဒေါင်းလုပ်ရပ်ရန်\n"
        "/status - Server uptime\n"
        "/about - Bot info\n"
        "\n⚡ Fast • Reliable • 24/7 Online"
    ), parse_mode="Markdown")

@bot.message_handler(commands=["status"])
def status(msg):
    uptime = datetime.utcnow() - START_TIME
    bot.reply_to(msg, f"🕒 Server Uptime: {uptime}\n✅ Running smoothly!")

@bot.message_handler(commands=["play"])
def play(msg):
    chat_id = msg.chat.id
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "အသုံးပြုနည်း: `/play <နာမည်>`", parse_mode="Markdown")
        return
    query = parts[1].strip()

    with lock:
        if chat_id not in active_downloads:
            stop_event = threading.Event()
            q = Queue()
            q.put(query)
            active_downloads[chat_id] = {"stop": stop_event, "queue": q}
            threading.Thread(target=process_queue, args=(chat_id,), daemon=True).start()
        else:
            active_downloads[chat_id]["queue"].put(query)
            bot.reply_to(msg, "⏳ Download queue ထဲသို့ထည့်လိုက်ပါသည်။")

@bot.message_handler(commands=["stop"])
def stop(msg):
    chat_id = msg.chat.id
    with lock:
        if chat_id in active_downloads:
            active_downloads[chat_id]["stop"].set()
            bot.reply_to(msg, "🛑 Download ရပ်လိုက်ပါသည်။")
        else:
            bot.reply_to(msg, "ရပ်ရန် download မရှိပါ။")

# ===== QUEUE PROCESSOR =====
def process_queue(chat_id):
    stop_event = active_downloads[chat_id]["stop"]
    q = active_downloads[chat_id]["queue"]
    while not q.empty() and not stop_event.is_set():
        query = q.get()
        download_and_send(chat_id, query, stop_event)
        q.task_done()
    with lock:
        active_downloads.pop(chat_id, None)

# ===== DOWNLOAD FUNCTION =====
def download_and_send(chat_id, query, stop_event):
    tmpdir = tempfile.mkdtemp(prefix="music4u_")
    progress_msg_id = None
    last_update = 0
    UPDATE_INTERVAL = 0.8
    TIMEOUT = 180  # Increased for Railway slow download

    try:
        # Search YouTube video
        info_json = subprocess.check_output([
            "yt-dlp",
            "--no-playlist", "--ignore-errors", "--no-warnings",
            "--print-json", "--skip-download",
            f"ytsearch5:{query}"
        ], text=True)

        data_list = [json.loads(line) for line in info_json.strip().split("\n") if line.strip()]
        if not data_list:
            bot.send_message(chat_id, "🚫 သီချင်းမတွေ့ပါ။ Keyword အသစ်နဲ့စမ်းကြည့်ပါ။")
            return

        # Take first result
        data = data_list[0]
        title = data.get("title", "Unknown Title")
        url = data.get("webpage_url")
        thumb_url = data.get("thumbnail")

        bot.send_message(chat_id, f"🎧 `{title}` ကို ဒေါင်းလုပ်ဆွဲနေပါသည်...", parse_mode="Markdown")

        out = os.path.join(tmpdir, "%(title)s.%(ext)s")
        cmd = [
            "yt-dlp", "--extract-audio", "--audio-format", "mp3",
            "--audio-quality", "0", "--no-playlist", "--quiet",
            "--output", out, url
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        start_time = time.time()

        while proc.poll() is None:
            if stop_event.is_set():
                proc.terminate()
                bot.send_message(chat_id, "❌ Download stopped.")
                return
            if time.time() - start_time > TIMEOUT:
                proc.terminate()
                bot.send_message(chat_id, "⚠️ Timeout — Download မပြီးပါ။")
                return

            now = time.time()
            if now - last_update > UPDATE_INTERVAL:
                dots = "." * int(((now * 2) % 4) + 1)
                msg_text = f"📥 Downloading{dots}"
                if not progress_msg_id:
                    m = bot.send_message(chat_id, msg_text)
                    progress_msg_id = m.message_id
                else:
                    try:
                        bot.edit_message_text(msg_text, chat_id, progress_msg_id)
                    except:
                        pass
                last_update = now
            time.sleep(0.5)

        # Find mp3 file
        mp3_files = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
        if not mp3_files:
            bot.send_message(chat_id, "🚫 mp3 file မရပါ။ ffmpeg မပါလို့ဖြစ်နိုင်ပါတယ်။")
            return

        fpath = os.path.join(tmpdir, mp3_files[0])
        if os.path.getsize(fpath) > MAX_FILESIZE:
            bot.send_message(chat_id, "⚠️ ဖိုင်အရွယ်အစားကြီးလွန်းပါသည်။ Telegram မှပို့လို့မရပါ။")
            return

        caption = f"🎶 {title}\n\n_Music 4U မှ ပေးပို့နေပါသည်_ 🎧"

        # Try thumbnail
        try:
            if thumb_url:
                img = Image.open(BytesIO(requests.get(thumb_url, timeout=5).content))
                thumb_path = os.path.join(tmpdir, "thumb.jpg")
                img.save(thumb_path)
                with open(fpath, "rb") as aud, open(thumb_path, "rb") as th:
                    bot.send_audio(chat_id, aud, caption=caption, thumb=th, parse_mode="Markdown")
            else:
                with open(fpath, "rb") as aud:
                    bot.send_audio(chat_id, aud, caption=caption, parse_mode="Markdown")
        except Exception:
            with open(fpath, "rb") as aud:
                bot.send_audio(chat_id, aud, caption=caption, parse_mode="Markdown")

        bot.send_message(chat_id, "✅ သီချင်း ပေးပို့ပြီးပါပြီ 🎧")

    except subprocess.CalledProcessError as e:
        bot.send_message(chat_id, f"❌ yt-dlp error: {e}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ အမှားတစ်ခုဖြစ်ပါသည်: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ===== START BOT =====
def start_bot():
    print("✅ Bot is starting and polling...")
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=30)

# ===== MAIN =====
if __name__ == "__main__":
    keep_alive()
    start_bot()
