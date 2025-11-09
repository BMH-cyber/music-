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
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = 30 * 1024 * 1024  # 30MB
APP_URL = os.getenv("APP_URL")  # https://your-app.up.railway.app

# ===== TELEBOT SETUP =====
BOT = telebot.TeleBot(TOKEN, parse_mode=None)
THREAD_POOL = ThreadPoolExecutor(max_workers=5)

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
def ytdlp_search_sync(query, use_proxy=True):
    opts = {
        "quiet": True,
        "noplaylist": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "http_headers": {"User-Agent": "Mozilla/5.0"}
    }
    if use_proxy and YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            return info.get("entries") or []
    except:
        return []

async def invidious_search(query, session, timeout=5):
    results = []
    for base in INVIDIOUS_INSTANCES:
        try:
            url = f"{base.rstrip('/')}/api/v1/search?q={requests.utils.requote_uri(query)}&type=video&per_page=5"
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200: continue
                data = await resp.json()
                for v in data:
                    results.append({
                        "title": v.get("title"),
                        "webpage_url": f"https://www.youtube.com/watch?v={v.get('videoId')}",
                        "id": v.get("videoId")
                    })
        except:
            continue
    return results

async def find_videos_for_query(query):
    cached = cache_get(query)
    if cached:
        return [cached]
    loop = asyncio.get_event_loop()
    yt_future = loop.run_in_executor(None, ytdlp_search_sync, query, True)
    async with aiohttp.ClientSession() as session:
        inv_future = invidious_search(query, session)
        results = await asyncio.gather(yt_future, inv_future, return_exceptions=True)
    videos = []
    for r in results:
        if isinstance(r, list):
            videos.extend(r)
    for v in videos:
        if v.get("webpage_url"):
            cache_put(query, v)
    return videos

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

# ===== BOT COMMANDS =====
@BOT.message_handler(commands=["start", "help"])
def cmd_start(m):
    BOT.reply_to(m, "🎶 Welcome to Music4U — Type song name to download as MP3.")

@BOT.message_handler(commands=["stop"])
def cmd_stop(m):
    chat_id = m.chat.id
    BOT.send_message(chat_id, "🛑 Queue cleared / stopped.")

# ===== SEARCH & SHOW INLINE OPTIONS =====
@BOT.message_handler(func=lambda m: True)
def handle_message(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    if not text or text.startswith("/"):
        BOT.reply_to(m, "Use /start or type a song name.")
        return
    BOT.send_chat_action(chat_id, "typing")
    THREAD_POOL.submit(search_and_show_choices, chat_id, text)

def search_and_show_choices(chat_id, query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    videos = loop.run_until_complete(find_videos_for_query(query))
    if not videos:
        BOT.send_message(chat_id, f"🚫 Couldn't find: {query}")
        return
    markup = InlineKeyboardMarkup()
    for v in videos[:5]:
        btn = InlineKeyboardButton(text=v['title'][:40], callback_data=f"download::{v['webpage_url']}")
        markup.add(btn)
    BOT.send_message(chat_id, f"Select the song you want:", reply_markup=markup)

# ===== CALLBACK HANDLER =====
@BOT.callback_query_handler(func=lambda call: call.data.startswith("download::"))
def callback_download(call: CallbackQuery):
    chat_id = call.message.chat.id
    video_url = call.data.split("::", 1)[1]
    BOT.answer_callback_query(call.id, "Downloading your song...")
    THREAD_POOL.submit(download_and_send, chat_id, video_url)

def download_and_send(chat_id, video_url):
    mp3_file = download_to_mp3(video_url)
    if mp3_file:
        size = os.path.getsize(mp3_file)
        if size > MAX_TELEGRAM_FILE:
            BOT.send_message(chat_id, f"⚠️ File too large ({round(size/1024/1024,2)} MB)")
        else:
            with open(mp3_file, "rb") as f:
                BOT.send_audio(chat_id, f)
        shutil.rmtree(os.path.dirname(mp3_file), ignore_errors=True)
    else:
        BOT.send_message(chat_id, "❌ Download failed.")

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
    if APP_URL:
        webhook_url = f"{APP_URL}/{TOKEN}"
        BOT.remove_webhook()
        BOT.set_webhook(url=webhook_url)
        print(f"✅ Webhook set to {webhook_url}")
    print("✅ Music4U bot running...")
    app.run(host="0.0.0.0", port=PORT)
