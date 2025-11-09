import os
import json
import time
import asyncio
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
import urllib.parse
import unicodedata

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiohttp
import requests
from yt_dlp import YoutubeDL
from flask import Flask, request
from dotenv import load_dotenv

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = 30 * 1024 * 1024  # 30MB
APP_URL = os.getenv("APP_URL")

# ===== TELEBOT SETUP =====
if not TOKEN:
    raise Exception("BOT_TOKEN မထည့်ထားပါ")
BOT = telebot.TeleBot(TOKEN, parse_mode=None)
THREAD_POOL = ThreadPoolExecutor(max_workers=5)

# ===== CACHE SYSTEM =====
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

# ===== UNICODE / MULTILINGUAL SUPPORT =====
def normalize_query(q: str) -> str:
    """Normalize input string to NFKC form for Unicode-safe search"""
    if not q: return ""
    return unicodedata.normalize("NFKC", q.strip())

# ===== INVIDIOUS INSTANCES =====
INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://yewtu.cafe",
    "https://invidious.snopyta.org",
    "https://vid.puffyan.us",
    "https://invidious.kavin.rocks"
]

async def refresh_invidious_instances():
    url = "https://api.invidious.io/instances.json"
    while True:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            instances = [inst["uri"] for inst in data if inst.get("type") == "https"]
            if instances:
                global INVIDIOUS_INSTANCES
                INVIDIOUS_INSTANCES = instances
                print(f"✅ Refreshed {len(instances)} Invidious instances")
        except Exception as e:
            print("❌ Failed to refresh instances:", e)
        await asyncio.sleep(1800)

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
            safe_query = urllib.parse.quote(query)
            info = ydl.extract_info(f"ytsearch5:{safe_query}", download=False)
            return info.get("entries") or []
    except Exception as e:
        print("yt-dlp search error:", e)
        return []

async def invidious_search(query, session, timeout=5):
    for base in INVIDIOUS_INSTANCES:
        try:
            url = f"{base.rstrip('/')}/api/v1/search?q={requests.utils.requote_uri(query)}&type=video&per_page=5"
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200: continue
                data = await resp.json()
                return [{
                    "title": v.get("title"),
                    "webpage_url": f"https://www.youtube.com/watch?v={v.get('videoId')}",
                    "id": v.get("videoId")
                } for v in data]
        except:
            continue
    return []

async def find_videos_for_query(query):
    query = normalize_query(query)
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
    if not videos:
        print(f"⚠️ No result found in Invidious, trying yt-dlp fallback")
        yt_fallback = ytdlp_search_sync(query, True)
        videos.extend(yt_fallback)
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

def download_and_send(chat_id, video_url):
    BOT.send_chat_action(chat_id, "upload_audio")
    mp3_file = download_to_mp3(video_url)
    if mp3_file:
        size = os.path.getsize(mp3_file)
        if size > MAX_TELEGRAM_FILE:
            BOT.send_message(chat_id, normalize_query(f"⚠️ File too large ({round(size/1024/1024,2)} MB)"))
        else:
            with open(mp3_file, "rb") as f:
                BOT.send_audio(chat_id, f)
        shutil.rmtree(os.path.dirname(mp3_file), ignore_errors=True)
    else:
        BOT.send_message(chat_id, normalize_query("❌ Download failed."))

# ===== BOT COMMANDS =====
@BOT.message_handler(commands=["start", "help"])
def cmd_start(m):
    BOT.reply_to(m, normalize_query("🎶 Welcome to Music4U — Type song name to download as MP3."))

@BOT.message_handler(commands=["stop"])
def cmd_stop(m):
    chat_id = m.chat.id
    BOT.send_message(chat_id, normalize_query("🛑 Queue cleared / stopped."))
