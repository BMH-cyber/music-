import os
import json
import time
import tempfile
import shutil
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import telebot
import requests
from yt_dlp import YoutubeDL
from flask import Flask, request
from dotenv import load_dotenv
import subprocess

# ===== CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
APP_URL = os.getenv("APP_URL")
MAX_FILE_SIZE = 48 * 1024 * 1024

BOT = telebot.TeleBot(TOKEN, parse_mode=None)
THREADS = ThreadPoolExecutor(max_workers=3)

# ===== LOGGING =====
logging.basicConfig(
    filename="music4u_error.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ===== CHECK FFMPEG =====
def ensure_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        logging.warning(f"ffmpeg not found: {e}")
        return False

# ===== DOWNLOAD HANDLER =====
def download_audio(url):
    tempdir = tempfile.mkdtemp(prefix="music4u_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": outtmpl,
        "postprocessors": []
    }

    if ensure_ffmpeg():
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        })

    for attempt in range(3):
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            for file in os.listdir(tempdir):
                if file.endswith(".mp3"):
                    return os.path.join(tempdir, file)
        except Exception as e:
            logging.error(f"Download attempt {attempt+1} failed: {e}")
            time.sleep(1)
    shutil.rmtree(tempdir, ignore_errors=True)
    return None

# ===== SEARCH HANDLER =====
def youtube_search(query):
    opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "default_search": "ytsearch1"
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info and info["entries"]:
                return info["entries"][0]
            return info
    except Exception as e:
        logging.error(f"Search error: {e}")
        return None

# ===== CORE PROCESS =====
def handle_query(chat_id, text):
    try:
        BOT.send_chat_action(chat_id, "typing")
        info = youtube_search(text)
        if not info:
            BOT.send_message(chat_id, "သီချင်းမတွေ့ပါ။ နာမည်ပြန်စမ်းပါ။")
            return

        title = info.get("title", "unknown")
        url = info.get("webpage_url")
        BOT.send_message(chat_id, f"🎵 {title} ကို ပြင်ဆင်နေပါတယ်...")

        mp3_path = download_audio(url)
        if not mp3_path:
            BOT.send_message(chat_id, "မအောင်မြင်ပါ။ ပြန်ကြိုးစားပါ။")
            return

        size = os.path.getsize(mp3_path)
        if size <= MAX_FILE_SIZE:
            with open(mp3_path, "rb") as f:
                BOT.send_audio(chat_id, f, title=title)
        else:
            BOT.send_message(chat_id, f"⚠️ ဖိုင်ကြီးနေပါတယ် ({round(size/1024/1024,2)} MB)")
        shutil.rmtree(os.path.dirname(mp3_path), ignore_errors=True)
    except Exception as e:
        BOT.send_message(chat_id, "Error တစ်ခုရှိနေပါတယ်။ ပြန်ကြိုးစားပါ။")
        logging.error(f"Main handle error: {e}")

# ===== TELEGRAM COMMANDS =====
@BOT.message_handler(commands=["start", "help"])
def start_cmd(m):
    BOT.reply_to(m, "🎶 Music4U Bot\nသီချင်းနာမည်ပေးပြီး MP3 ကိုယူနိုင်ပါတယ်။")

@BOT.message_handler(func=lambda m: True)
def text_handler(m):
    query = (m.text or "").strip()
    if not query or query.startswith("/"): return
    THREADS.submit(handle_query, m.chat.id, query)

# ===== FLASK KEEPALIVE =====
app = Flask("music4u_keepalive")

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot running"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    BOT.process_new_updates([update])
    return "ok", 200

# ===== MAIN =====
if __name__ == "__main__":
    if APP_URL:
        BOT.remove_webhook()
        BOT.set_webhook(url=f"{APP_URL}/{TOKEN}")
        print("✅ Webhook set:", f"{APP_URL}/{TOKEN}")
    print("🎧 Music4U bot is live.")
    app.run(host="0.0.0.0", port=PORT)
