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

import telebot
import aiohttp
from yt_dlp import YoutubeDL
from flask import Flask, request
from dotenv import load_dotenv

# ===== CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = 50 * 1024 * 1024

BOT = telebot.TeleBot(TOKEN)
THREAD_POOL = ThreadPoolExecutor(max_workers=5)

CACHE_FILE = Path("music4u_cache.json")
CACHE_TTL_DAYS = 7

def load_cache():
    if CACHE_FILE.exists():
        try: return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except: return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

_cache = load_cache()
def cache_get(q):
    item = _cache.get(q.lower().strip())
    if not item: return None
    if time.time() - item.get("ts", 0) > CACHE_TTL_DAYS*86400:
        _cache.pop(q, None)
        save_cache(_cache)
        return None
    return item
def cache_put(q, info):
    _cache[q.lower().strip()] = {"ts": int(time.time()), "video_id": info.get("id"), "title": info.get("title"), "webpage_url": info.get("webpage_url")}
    save_cache(_cache)

# ===== SEARCH =====
def best_match(entries, query):
    query_lower = query.lower()
    for e in entries:
        if query_lower in e.get("title","").lower():
            return e
    return entries[0] if entries else None

def ytdlp_search_sync(query, use_proxy=True):
    opts = {"quiet": True,"noplaylist": True,"no_warnings": True,"format": "bestaudio/best","encoding": "utf-8","http_headers": {"User-Agent": "Mozilla/5.0"}}
    if use_proxy and YTDLP_PROXY: opts["proxy"]=YTDLP_PROXY
    try:
        info = YoutubeDL(opts).extract_info(f"ytsearch10:{query}", download=False)
        entries = info.get("entries") or []
        best = best_match(entries, query)
        return [best] if best else []
    except: return []

async def find_videos(query):
    cached = cache_get(query)
    if cached: return [cached]
    loop = asyncio.get_event_loop()
    yt_future = loop.run_in_executor(None, ytdlp_search_sync, query, True)
    results = await asyncio.gather(yt_future, return_exceptions=True)
    videos = []
    for r in results:
        if isinstance(r,list): videos.extend(r)
    for v in videos:
        if v.get("webpage_url"): cache_put(query,v)
    return videos[:1]

# ===== DOWNLOAD AUDIO =====
def check_ffmpeg():
    try: subprocess.run(["ffmpeg","-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE); return True
    except: return False

def download_to_audio(url):
    tempdir = tempfile.mkdtemp(prefix="music4u_")
    outtmpl = os.path.join(tempdir, "%(title)s.%(ext)s")
    opts = {"format": "bestaudio/best","outtmpl": outtmpl,"noplaylist": True,"quiet": True,"no_warnings": True,"postprocessors":[]}
    if check_ffmpeg(): opts["postprocessors"]=[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"320"}]
    if YTDLP_PROXY: opts["proxy"]=YTDLP_PROXY
    try:
        with YoutubeDL(opts) as ydl: ydl.extract_info(url, download=True)
        for f in os.listdir(tempdir):
            if f.lower().endswith((".mp3",".m4a")): return os.path.join(tempdir,f)
    except: shutil.rmtree(tempdir,ignore_errors=True); return None
    return None

def download_and_send(chat_id, video_url, title=None):
    BOT.send_chat_action(chat_id,"upload_audio")
    audio_file = download_to_audio(video_url)
    if audio_file:
        size = os.path.getsize(audio_file)
        if size > MAX_TELEGRAM_FILE: BOT.send_message(chat_id,f"⚠️ File too large ({round(size/1024/1024,2)} MB)")
        else:
            with open(audio_file,"rb") as f: BOT.send_audio(chat_id,f,caption=f"🎵 {title or 'Song'}")
        shutil.rmtree(os.path.dirname(audio_file),ignore_errors=True)
    else: BOT.send_message(chat_id,"❌ Download failed.")

def search_and_send(chat_id, query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    videos = loop.run_until_complete(find_videos(query))
    if not videos: BOT.send_message(chat_id,f"🚫 Couldn't find: {query}"); return
    v = videos[0]; download_and_send(chat_id,v['webpage_url'],v.get("title"))

# ===== BOT HANDLERS =====
@BOT.message_handler(commands=["start","help"])
def cmd_start(m): BOT.reply_to(m,"🎶 Music4U Turbo Edition\nType any song name ⬇️")

@BOT.message_handler(func=lambda m: True)
def handle_message(m):
    text = (m.text or "").strip()
    if not text or text.startswith("/"): BOT.reply_to(m,"Use /start or type a song name."); return
    THREAD_POOL.submit(search_and_send,m.chat.id,text)

# ===== FLASK WEBHOOK =====
app = Flask("music4u")
@app.route("/",methods=["GET"])
def home(): return "✅ Music4U alive"
@app.route(f"/{TOKEN}",methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    BOT.process_new_updates([update])
    return "ok",200

# ===== RUN =====
if __name__=="__main__":
    if APP_URL:
        BOT.remove_webhook()
        BOT.set_webhook(f"{APP_URL}/{TOKEN}")
        print(f"✅ Webhook set: {APP_URL}/{TOKEN}")
    print("✅ Music4U running...")
    app.run(host="0.0.0.0",port=PORT)
