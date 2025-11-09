import os, json, time, asyncio, threading, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import telebot, aiohttp, requests
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from flask import Flask, request

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # ex: https://yourapp.up.railway.app
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = 30 * 1024 * 1024

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

async def find_video_for_query(query):
    cached = cache_get(query)
    if cached:
        return cached
    loop = asyncio.get_event_loop()
    yt_future = loop.run_in_executor(None, ytdlp_search_sync, query, True)
    async with aiohttp.ClientSession() as session:
        inv_future = invidious_search(query, session)
        results = await asyncio.gather(yt_future, inv_future, return_exceptions=True)
        for r in results:
            if isinstance(r, dict) and r.get("webpage_url"):
                cache_put(query, r)
                return r
    direct_res = await loop.run_in_executor(None, ytdlp_search_sync, query, False)
    if direct_res and direct_res.get("webpage_url"):
        cache_put(query, direct_res)
        return direct_res
    return None

# ===== DOWNLOAD AUDIO =====
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

# ===== PROCESSING QUEUE =====
def process_queue(chat_id):
    if chat_id not in CHAT_QUEUE or not CHAT_QUEUE[chat_id]:
        ACTIVE.pop(chat_id, None)
        return
    if ACTIVE.get(chat_id): return
    ACTIVE[chat_id] = True
    try:
        while CHAT_QUEUE[chat_id]:
            query = CHAT_QUEUE[chat_id].pop(0)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            video_info = loop.run_until_complete(find_video_for_query(query))
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

# ===== BOT HANDLERS =====
@BOT.message_handler(commands=["start", "help"])
def cmd_start(message):
    BOT.reply_to(message, "🎶 Welcome to Music4U — Type song name to download as MP3.")

@BOT.message_handler(commands=["stop"])
def cmd_stop(message):
    chat_id = message.chat.id
    CHAT_QUEUE[chat_id] = []
    ACTIVE.pop(chat_id, None)
    BOT.send_message(chat_id, "🛑 Queue cleared / stopped.")

@BOT.message_handler(func=lambda m: True)
def on_message(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        BOT.reply_to(message, "Use /start or type a song name.")
        return
    if chat_id not in CHAT_QUEUE:
        CHAT_QUEUE[chat_id] = []
    CHAT_QUEUE[chat_id].append(text)
    BOT.send_chat_action(chat_id, "typing")
    BOT.send_message(chat_id, f"🔍 Queued: {text}")
    THREAD_POOL.submit(process_queue, chat_id)

# ===== FLASK + WEBHOOK =====
app = Flask("music4u_keepalive")

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    BOT.process_new_updates([update])
    return "!", 200

@app.route("/")
def index():
    return "✅ Music4U bot is running", 200

if __name__ == "__main__":
    # Telegram webhook set (one-time)
    BOT.remove_webhook()
    BOT.set_webhook(url=f"{APP_URL}/{TOKEN}")
    print("✅ Music4U bot webhook set and running")
    app.run(host="0.0.0.0", port=PORT)
