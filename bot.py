import os, json, time, threading, tempfile, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import telebot
from yt_dlp import YoutubeDL
from flask import Flask, request, abort
from dotenv import load_dotenv

# ===== CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAX_TELEGRAM_FILE = 30 * 1024 * 1024
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")

# ===== TELEGRAM BOT =====
BOT = telebot.TeleBot(TOKEN)
THREAD_POOL = ThreadPoolExecutor(max_workers=5)
CHAT_QUEUE = {}
ACTIVE = {}

# ===== CACHE =====
CACHE_FILE = Path("music4u_cache.json")
CACHE_TTL_DAYS = 7

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"))

_cache = load_cache()

def cache_get(q):
    item = _cache.get(q.lower().strip())
    if not item: return None
    if time.time() - item.get("ts", 0) > CACHE_TTL_DAYS * 86400:
        _cache.pop(q, None)
        save_cache(_cache)
        return None
    return item

def cache_put(q, info):
    _cache[q.lower().strip()] = {
        "ts": int(time.time()),
        "video_id": info.get("id"),
        "title": info.get("title"),
        "webpage_url": info.get("webpage_url")
    }
    save_cache(_cache)

# ===== SEARCH & DOWNLOAD =====
def ytdlp_search_sync(query):
    opts = {
        "quiet": True,
        "noplaylist": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "http_headers": {"User-Agent": "Mozilla/5.0"}
    }
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            e = (info.get("entries") or [None])[0]
            if e:
                return {
                    "title": e.get("title"),
                    "webpage_url": e.get("webpage_url") or e.get("url"),
                    "id": e.get("id")
                }
    except:
        return None
    return None

def download_to_mp3(video_url):
    tempdir = tempfile.mkdtemp(prefix="music4u_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    }
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    try:
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(video_url, download=True)
        for f in os.listdir(tempdir):
            if f.lower().endswith(".mp3"):
                return os.path.join(tempdir, f)
    except:
        shutil.rmtree(tempdir, ignore_errors=True)
        return None
    return None

# ===== PROCESS QUEUE =====
def process_queue(chat_id):
    if chat_id not in CHAT_QUEUE or not CHAT_QUEUE[chat_id]:
        ACTIVE.pop(chat_id, None)
        return
    if ACTIVE.get(chat_id): return
    ACTIVE[chat_id] = True
    try:
        while CHAT_QUEUE[chat_id]:
            query = CHAT_QUEUE[chat_id].pop(0)
            video_info = ytdlp_search_sync(query)
            if not video_info:
                BOT.send_message(chat_id, f"🚫 Couldn't find: {query}")
                continue
            BOT.send_message(chat_id, f"🎵 Found: {video_info['title']}\n⬇️ Downloading now...")
            mp3_file = download_to_mp3(video_info["webpage_url"])
            if mp3_file:
                size = os.path.getsize(mp3_file)
                if size > MAX_TELEGRAM_FILE:
                    BOT.send_message(chat_id, f"⚠️ File too large ({round(size/1024/1024,2)} MB)")
                else:
                    with open(mp3_file, "rb") as f:
                        BOT.send_audio(chat_id, f, title=video_info["title"])
                shutil.rmtree(os.path.dirname(mp3_file), ignore_errors=True)
            else:
                BOT.send_message(chat_id, f"❌ Download failed: {query}")
    finally:
        ACTIVE.pop(chat_id, None)

# ===== FLASK APP FOR WEBHOOK =====
app = Flask(__name__)

@app.route("/"+TOKEN, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        BOT.process_new_updates([update])
        return "", 200
    else:
        abort(403)

# ===== TELEGRAM HANDLERS =====
@BOT.message_handler(commands=["start", "help"])
def cmd_start(m):
    BOT.reply_to(m, "🎶 Welcome to Music4U — Type song name to download as MP3.")

@BOT.message_handler(commands=["stop"])
def cmd_stop(m):
    chat_id = m.chat.id
    CHAT_QUEUE[chat_id] = []
    ACTIVE.pop(chat_id, None)
    BOT.send_message(chat_id, "🛑 Queue cleared / stopped.")

@BOT.message_handler(func=lambda m: True)
def on_message(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    if not text or text.startswith("/"):
        BOT.reply_to(m, "Use /start or type a song name.")
        return
    if chat_id not in CHAT_QUEUE:
        CHAT_QUEUE[chat_id] = []
    CHAT_QUEUE[chat_id].append(text)
    BOT.send_chat_action(chat_id, "typing")
    BOT.send_message(chat_id, f"🔍 Queued: {text}")
    THREAD_POOL.submit(process_queue, chat_id)

# ===== SET WEBHOOK =====
def set_webhook():
    BOT.remove_webhook()
    BOT.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
