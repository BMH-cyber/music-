# music4u_v3.py — Music 4U FastBot V3
# Fast, cached, fallback-search, background download (yt-dlp Python API)
# Usage: put BOT_TOKEN in .env and run: python music4u_v3.py

import os
import sys
import json
import time
import shutil
import asyncio
import tempfile
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# ----- Auto install common deps if missing -----
def ensure_packages(pkgs):
    import importlib
    for pkg in pkgs:
        name = pkg.split("==")[0]
        try:
            importlib.import_module(name)
        except Exception:
            print(f"Installing {pkg} ...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

ensure_packages([
    "pyTelegramBotAPI",
    "yt-dlp",
    "aiohttp",
    "python-dotenv",
    "requests",
    "Pillow"
])

# ----- Imports (after install) -----
import telebot
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
import aiohttp
import requests
from PIL import Image
from flask import Flask

# ----- Config -----
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
if not TOKEN:
    print("ERROR: BOT_TOKEN missing in .env")
    sys.exit(1)

BOT = telebot.TeleBot(TOKEN, parse_mode=None)
DOWNLOAD_DIR = Path("downloads_music4u_v3")
DOWNLOAD_DIR.mkdir(exist_ok=True)
CACHE_FILE = Path("music4u_cache.json")
CACHE_TTL_DAYS = 7
MAX_TELEGRAM_FILE = 30 * 1024 * 1024  # 30MB
THREAD_POOL = ThreadPoolExecutor(max_workers=3)
ACTIVE = {}  # chat_id -> future/flag lock

# public invidious instances fallback list (best-effort)
INVIDIOUS_INSTANCES = [
    "https://yewtu.cafe",
    "https://yewtu.cafe",         # duplicate intentionally low list — you can add more known working instances
    "https://yewtu.cafe"          # (user can add others if desired)
]

# ----- Cache helpers -----
def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass

_cache = load_cache()

def cache_get(query):
    q = query.lower().strip()
    item = _cache.get(q)
    if not item: return None
    ts = item.get("ts", 0)
    if time.time() - ts > CACHE_TTL_DAYS * 86400:
        # expired
        _cache.pop(q, None)
        save_cache(_cache)
        return None
    return item

def cache_put(query, video_info):
    q = query.lower().strip()
    item = {
        "ts": int(time.time()),
        "video_id": video_info.get("id") or video_info.get("webpage_url") or video_info.get("id"),
        "title": video_info.get("title"),
        "webpage_url": video_info.get("webpage_url") or video_info.get("url") or video_info.get("id"),
    }
    _cache[q] = item
    save_cache(_cache)

# ----- Utility: sanitize filename -----
def sanitize_filename(name: str):
    # simple sanitize
    return "".join(c for c in name if c.isalnum() or c in " ._-").strip()

# ----- Invidious fallback search (best-effort) -----
async def invidious_search(query, session, timeout=6):
    for base in INVIDIOUS_INSTANCES:
        try:
            url = f"{base.rstrip('/')}/api/v1/search?q={requests.utils.requote_uri(query)}&type=video&per_page=3"
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                if data:
                    # pick first
                    v = data[0]
                    return {
                        "title": v.get("title"),
                        "webpage_url": f"https://www.youtube.com/watch?v={v.get('videoId')}" if v.get("videoId") else v.get("url"),
                        "id": v.get("videoId") or v.get("url")
                    }
        except Exception:
            continue
    return None

# ----- Primary search using yt-dlp (fast, single-shot) -----
def ytdlp_search_sync(query, timeout=30):
    """Use yt-dlp to run ytsearch1 and return a dict of video info (no download)."""
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            # add headers to appear like a browser
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
            },
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            # ytsearch1 returns dict with 'entries'
            entries = info.get("entries") or []
            if entries:
                first = entries[0]
                return {
                    "title": first.get("title"),
                    "webpage_url": first.get("webpage_url") or first.get("url"),
                    "id": first.get("id")
                }
    except Exception as e:
        # return None on failure
        # print("ytdlp_search_sync error:", e)
        return None
    return None

# ----- Download function (yt-dlp Python API) -----
def ytdlp_download_to_mp3(video_url, chat_id, timeout=80):
    """Download the video_url to mp3 and return path or None"""
    tempdir = tempfile.mkdtemp(prefix="music4u_")
    outtmpl = os.path.join(tempdir, f"{chat_id}_%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        # user agent header
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
        },
        # limit file size? yt-dlp doesn't enforce size; we'll check later
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Use extract_info with download=True to perform both metadata fetch and download once
            info = ydl.extract_info(video_url, download=True)
            # find resulting mp3 file
            for f in os.listdir(tempdir):
                if f.lower().endswith(".mp3"):
                    return os.path.join(tempdir, f)
    except Exception as e:
        # cleanup and return None
        # print("download error:", e)
        shutil.rmtree(tempdir, ignore_errors=True)
        return None
    # nothing found
    shutil.rmtree(tempdir, ignore_errors=True)
    return None

# ----- Orchestrator: search (cache -> ytdlp -> invidious) -----
async def find_video_for_query(query):
    # 1. cache
    item = cache_get(query)
    if item:
        return item.get("webpage_url") or item.get("video_id"), item.get("title")
    # 2. try yt-dlp search (sync via thread)
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, ytdlp_search_sync, query)
    if info:
        cache_put(query, info)
        return info.get("webpage_url"), info.get("title")
    # 3. try invidious fallback async
    async with aiohttp.ClientSession() as session:
        try:
            inv = await invidious_search(query, session)
            if inv:
                cache_put(query, inv)
                return inv.get("webpage_url"), inv.get("title")
        except Exception:
            pass
    # 4. no result
    return None, None

# ----- Send helper (file size check, cleanup) -----
def send_mp3_to_chat(chat_id, mp3_path, title):
    try:
        size = os.path.getsize(mp3_path)
        if size > MAX_TELEGRAM_FILE:
            BOT.send_message(chat_id, f"⚠️ File too large to send ({round(size/(1024*1024),2)} MB).")
            return False
        with open(mp3_path, "rb") as f:
            BOT.send_audio(chat_id, f, title=title)
        return True
    except Exception as e:
        BOT.send_message(chat_id, f"❌ Send failed: {e}")
        return False
    finally:
        try:
            os.remove(mp3_path)
            # remove tempdir if empty
            td = Path(mp3_path).parent
            if td.exists():
                shutil.rmtree(td, ignore_errors=True)
        except Exception:
            pass

# ----- Background task that does search+download+send ----- 
def background_fetch_and_send(chat_id, query):
    try:
        # mark active
        ACTIVE[chat_id] = True
        # find video
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        video_url, title = loop.run_until_complete(find_video_for_query(query))
        if not video_url:
            BOT.send_message(chat_id, "🚫 Couldn't find the song. Try a different name.")
            ACTIVE.pop(chat_id, None)
            return

        BOT.send_message(chat_id, f"🎵 Found: {title}\n⬇️ Downloading now...")
        # download (blocking)
        mp3 = ytdlp_download_to_mp3(video_url, chat_id)
        if not mp3:
            BOT.send_message(chat_id, "❌ Download failed. Try again later.")
            ACTIVE.pop(chat_id, None)
            return

        # send
        ok = send_mp3_to_chat(chat_id, mp3, title or query)
        if ok:
            BOT.send_message(chat_id, "✅ Sent. Enjoy! 🎧")
        ACTIVE.pop(chat_id, None)
    except Exception as e:
        try:
            BOT.send_message(chat_id, f"❌ Unexpected error: {e}")
        finally:
            ACTIVE.pop(chat_id, None)

# ----- Bot handlers ----- 
@BOT.message_handler(commands=["start","help"])
def cmd_start(m):
    BOT.reply_to(m,
        "🎶 *Music 4U (Fast v3)*\n\n"
        "သုံးပုံ - သီချင်းနာမည် (ဥပမာ: `Shape of You`) ကိုရိုက်ပေးပါ။\n"
        "Bot က အလုပ်လုပ်ပြီး mp3 ကို ၅–၁၅ စက္ကန့်အတွင်းပို့ပေးပါမယ်။\n\n"
        "သတိ - မိမိနေရာရဲ့ network က YouTube ကို block ထားရင် VPN/Proxy လိုအပ်နိုင်ပါတယ်။",
        parse_mode="Markdown"
    )

@BOT.message_handler(func=lambda m: True)
def on_message(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    if not text:
        return
    # avoid commands processed here
    if text.startswith("/"):
        BOT.reply_to(m, "Use /start or just type song name.")
        return

    # quick reply
    BOT.send_chat_action(chat_id, "typing")
    BOT.send_message(chat_id, f"🔍 Searching for *{text}* ... (fast)", parse_mode="Markdown")
    # prevent duplicate requests
    if chat_id in ACTIVE:
        BOT.send_message(chat_id, "⏳ A request is already running. Wait a moment or send /stop to cancel.")
        return

    # dispatch background worker
    THREAD_POOL.submit(background_fetch_and_send, chat_id, text)

@BOT.message_handler(commands=["stop"])
def cmd_stop(m):
    chat_id = m.chat.id
    # best-effort: mark active False — long-running yt-dlp cannot be forcibly killed here without tracking PIDs
    if chat_id in ACTIVE:
        # this simply prevents new work; current download keeps running but user got notified
        ACTIVE.pop(chat_id, None)
        BOT.send_message(chat_id, "🛑 Stop requested; current job will finish but no new jobs will start.")
    else:
        BOT.send_message(chat_id, "No active download.")

# ----- Keepalive webserver (Railway/Replit) -----
def keep_alive():
    app = Flask("music4u_v3")
    @app.route("/")
    def home(): 
        return "✅ Music 4U V3 alive"
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT), daemon=True).start()

# ----- Start bot -----
if __name__ == "__main__":
    keep_alive()
    print("✅ Music4U Fast V3 starting...")
    try:
        BOT.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        print("Shutting down")
        THREAD_POOL.shutdown(wait=False)
        
