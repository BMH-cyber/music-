import os
import json
import time
import asyncio
import threading
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import telebot
import aiohttp
import requests
from yt_dlp import YoutubeDL
from flask import Flask, request
from dotenv import load_dotenv
import subprocess
from googlesearch import search  # pip install googlesearch-python

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = 30 * 1024 * 1024  # 30MB
APP_URL = os.getenv("APP_URL")  # https://your-app.up.railway.app
SOUNDCLOUD_CLIENT_ID = os.getenv("SOUNDCLOUD_CLIENT_ID")  # optional

# ===== TELEBOT SETUP =====
BOT = telebot.TeleBot(TOKEN, parse_mode=None)
THREAD_POOL = ThreadPoolExecutor(max_workers=5)
ACTIVE = {}
CHAT_QUEUE = {}

# ===== CACHE SYSTEM =====
CACHE_FILE = Path("music4u_cache.json")
CACHE_TTL_DAYS = 7
INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://yewtu.cafe",
    "https://invidious.privacydev.net"
]

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

# ===== SEARCH HELPERS =====
def ytdlp_search_top_results(query, max_results=5):
    opts = {
        "quiet": True,
        "noplaylist": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "extract_flat": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"}
    }
    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    results = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            for e in info.get("entries", []):
                results.append({
                    "title": e.get("title"),
                    "webpage_url": e.get("url"),
                    "id": e.get("id")
                })
    except:
        return []
    return results

async def invidious_search(query, session, timeout=5):
    for base in INVIDIOUS_INSTANCES:
        try:
            url = f"{base.rstrip('/')}/api/v1/search?q={requests.utils.requote_uri(query)}&type=video&per_page=1"
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200: continue
                data = await resp.json()
                if data:
                    v = data[0]
                    return {
                        "title": v.get("title"),
                        "webpage_url": f"https://www.youtube.com/watch?v={v.get('videoId')}",
                        "id": v.get("videoId")
                    }
        except:
            continue
    return None

async def google_search_fallback(query):
    for url in search(query + " mp3", num_results=5):
        if url.endswith(".mp3"):
            return {"title": query, "webpage_url": url, "id": url}
    return None

async def soundcloud_search(query):
    if not SOUNDCLOUD_CLIENT_ID:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api-v2.soundcloud.com/search/tracks?q={requests.utils.requote_uri(query)}&client_id={SOUNDCLOUD_CLIENT_ID}&limit=1"
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                if data.get("collection"):
                    t = data["collection"][0]
                    return {
                        "title": t.get("title"),
                        "webpage_url": t.get("permalink_url"),
                        "id": t.get("id")
                    }
    except:
        return None
    return None

async def find_video_for_query(query):
    cached = cache_get(query)
    if cached:
        return cached
    loop = asyncio.get_event_loop()
    results = []

    # YouTube top 5
    results.extend(await loop.run_in_executor(None, ytdlp_search_top_results, query, 5))

    # Invidious fallback
    async with aiohttp.ClientSession() as session:
        inv_result = await invidious_search(query, session)
        if inv_result:
            results.append(inv_result)

    # Google fallback
    google_result = await google_search_fallback(query)
    if google_result:
        results.append(google_result)

    # SoundCloud fallback
    sc_result = await soundcloud_search(query)
    if sc_result:
        results.append(sc_result)

    for r in results:
        if r and r.get("webpage_url"):
            cache_put(query, r)
            return r
    return None

# ===== DOWNLOAD AUDIO =====
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except:
        return False

def download_to_mp3(video_url):
    tempdir = tempfile.mkdtemp(prefix="music4u_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": []
    }
    if check_ffmpeg():
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
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

# ===== PROCESSING QUEUE =====
def process_queue(chat_id, query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    video_info = loop.run_until_complete(find_video_for_query(query))
    if not video_info:
        BOT.send_message(chat_id, f"🚫 Couldn't find: {query}")
        return
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

# ===== BOT COMMANDS =====
@BOT.message_handler(commands=["start", "help"])
def cmd_start(m):
    BOT.reply_to(m, "🎶 Welcome to Music4U — Type song name to download as MP3.")

@BOT.message_handler(commands=["stop"])
def cmd_stop(m):
    chat_id = m.chat.id
    BOT.send_message(chat_id, "🛑 Queue cleared / stopped.")

@BOT.message_handler(func=lambda m: True)
def on_message(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    if not text or text.startswith("/"):
        BOT.reply_to(m, "Use /start or type a song name.")
        return
    BOT.send_chat_action(chat_id, "typing")
    THREAD_POOL.submit(process_queue, chat_id, text)

# ===== FLASK SERVER FOR WEBHOOK =====
app = Flask("music4u_keepalive")

@app.route("/", methods=["GET"])
def home():
    return "✅ Music4U bot is alive"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    BOT.process_new_updates([update])
    return "ok", 200

# ===== MAIN =====
if __name__ == "__main__":
    # Set webhook
    if APP_URL:
        webhook_url = f"{APP_URL}/{TOKEN}"
        BOT.remove_webhook()
        BOT.set_webhook(url=webhook_url)
        print(f"✅ Webhook set to {webhook_url}")

    print("✅ Music4U bot running...")
    # Start Flask server
    app.run(host="0.0.0.0", port=PORT)
