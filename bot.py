import os
import json
import time
import asyncio
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import telebot
import aiohttp
import requests
from yt_dlp import YoutubeDL
from flask import Flask, request
from dotenv import load_dotenv

# ===== CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = 30 * 1024 * 1024
APP_URL = os.getenv("APP_URL")

# ===== TELEBOT =====
BOT = telebot.TeleBot(TOKEN, parse_mode=None)
THREAD_POOL = ThreadPoolExecutor(max_workers=5)

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

# ===== SEARCH =====
def ytdlp_search_sync(query):
    opts = {
        "quiet": True,
        "noplaylist": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "http_headers": {"User-Agent": "Mozilla/5.0"}
    }
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            return info.get("entries") or []
    except:
        return []

async def find_video(query):
    cached = cache_get(query)
    if cached:
        return cached
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, ytdlp_search_sync, query)
    if result:
        video = result[0]
        cache_put(query, video)
        return video
    return None

# ===== FAST AUDIO SEND =====
def fast_send_audio(chat_id, video_url, title):
    try:
        opts = {"format": "bestaudio[ext=m4a]/bestaudio/best", "quiet": True, "noplaylist": True}
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info.get("url")
            if audio_url:
                buffer = BytesIO()
                r = requests.get(audio_url, stream=True)
                for chunk in r.iter_content(1024*1024):
                    buffer.write(chunk)
                buffer.seek(0)
                BOT.send_audio(chat_id, buffer, title=title)
                return True
    except:
        pass
    return False

def search_and_send_fast(chat_id, query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    video = loop.run_until_complete(find_video(query))
    if not video:
        BOT.send_message(chat_id, f"🚫 '{query}' သီချင်း မတွေ့ပါ။")
        return
    url = video.get("webpage_url")
    title = video.get("title")
    if not fast_send_audio(chat_id, url, title):
        BOT.send_message(chat_id, "❌ သီချင်းပို့လို့မရပါ။")

# ===== HANDLER =====
@BOT.message_handler(func=lambda m: True)
def handle_message(m):
    chat_id = m.chat.id
    query = (m.text or "").strip()
    if not query or query.startswith("/"):
        BOT.reply_to(m, "✅ /start ကိုနှိပ်ပြီး သီချင်းနာမည် ရိုက်ထည့်ပါ။")
        return
    BOT.send_chat_action(chat_id, "upload_audio")
    THREAD_POOL.submit(search_and_send_fast, chat_id, query)

# ===== COMMANDS =====
@BOT.message_handler(commands=["start","help"])
def cmd_start(m):
    BOT.reply_to(m, "🎶 Music4U သို့ ကြိုဆိုပါသည် — သီချင်းနာမည် ရိုက်ထည့်ပါ, MP3 အပြည့်အစုံ ပို့ပါမည်။")

@BOT.message_handler(commands=["stop"])
def cmd_stop(m):
    BOT.send_message(m.chat.id, "🛑 Queue ဖျက်ပြီး ရပ်ပါပြီ။")

# ===== FLASK SERVER =====
app = Flask("music4u_keepalive")

@app.route("/", methods=["GET"])
def home():
    return "✅ Music4U bot ရှိနေပါသည်"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    BOT.process_new_updates([update])
    return "ok", 200

# ===== MAIN =====
if __name__ == "__main__":
    if APP_URL:
        BOT.remove_webhook()
        BOT.set_webhook(url=f"{APP_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=PORT)
