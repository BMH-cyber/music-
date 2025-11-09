# bot.py (Music4U - upgraded)
import os
import json
import time
import asyncio
import tempfile
import shutil
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import telebot
import aiohttp
import requests
from yt_dlp import YoutubeDL
from flask import Flask, request
from dotenv import load_dotenv
import subprocess

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")
MAX_TELEGRAM_FILE = int(os.getenv("MAX_TELEGRAM_FILE", 30 * 1024 * 1024))  # default 30MB
APP_URL = os.getenv("APP_URL")
SOUNDCLOUD_CLIENT_ID = os.getenv("SOUNDCLOUD_CLIENT_ID", "")

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
    if not item:
        return None
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

# ===== Utilities =====
def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

def get_cookies_path():
    env = os.getenv("COOKIES_FILE")
    if env and os.path.exists(env):
        return env
    for p in ("./cookies.txt", "/tmp/cookies.txt"):
        if os.path.exists(p):
            return p
    return None

def is_signin_required_error(err_text):
    if not err_text:
        return False
    s = err_text.lower()
    keywords = [
        "sign in to confirm",
        "sign in to confirm you’re not a bot",
        "sign in to confirm you’re not a robot",
        "use --cookies",
        "verify you are human",
        "sign in to continue"
    ]
    return any(k in s for k in keywords)

# ===== SEARCH HELPERS =====
def ytdlp_search_top_results(query, max_results=5, use_proxy=True):
    opts = {
        "quiet": True,
        "noplaylist": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "extract_flat": True,
        "skip_download": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }
    if use_proxy and YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY
    results = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            for e in (info.get("entries") or []):
                # e might have 'url' as id
                url = e.get("url") or e.get("webpage_url") or (f"https://www.youtube.com/watch?v={e.get('id')}")
                results.append({
                    "title": e.get("title"),
                    "webpage_url": url,
                    "id": e.get("id") or url
                })
    except Exception as e:
        print("ytdlp_search_top_results error:", e)
    return results

async def invidious_search(query, session, timeout=5):
    for base in INVIDIOUS_INSTANCES:
        try:
            url = f"{base.rstrip('/')}/api/v1/search?q={requests.utils.requote_uri(query)}&type=video&per_page=1"
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                if data:
                    v = data[0]
                    return {
                        "title": v.get("title"),
                        "webpage_url": f"https://www.youtube.com/watch?v={v.get('videoId')}",
                        "id": v.get("videoId")
                    }
        except Exception as e:
            print("invidious_search error for", base, ":", e)
            continue
    return None

def google_search_fallback_sync(query, max_results=5):
    try:
        from googlesearch import search
    except Exception as e:
        # not installed
        print("googlesearch not available:", e)
        return None
    try:
        for url in search(query + " mp3", num_results=max_results):
            if url and url.lower().endswith(".mp3"):
                return {"title": query, "webpage_url": url, "id": url}
    except Exception as e:
        print("google_search_fallback_sync error:", e)
    return None

def soundcloud_search_sync(query):
    if not SOUNDCLOUD_CLIENT_ID:
        return None
    try:
        url = f"https://api-v2.soundcloud.com/search/tracks?q={requests.utils.requote_uri(query)}&client_id={SOUNDCLOUD_CLIENT_ID}&limit=1"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("collection"):
                t = data["collection"][0]
                return {"title": t.get("title"), "webpage_url": t.get("permalink_url"), "id": t.get("id")}
    except Exception as e:
        print("soundcloud_search_sync error:", e)
    return None

def vidmate_search_sync(query):
    # lightweight attempt: search web for vidmate mp3 mirrors via google (sync)
    res = google_search_fallback_sync(query + " vidmate mp3")
    return res

# ===== FIND VIDEO (multi-source, multi-result) =====
async def find_video_for_query(query):
    # 1) cache
    cached = cache_get(query)
    if cached:
        return cached

    loop = asyncio.get_event_loop()
    results = []

    # 2) YouTube top results (sync called in executor)
    try:
        yt_results = await loop.run_in_executor(None, ytdlp_search_top_results, query, 5, True)
        if yt_results:
            results.extend(yt_results)
    except Exception as e:
        print("yt search executor error:", e)

    # 3) Invidious fallback
    async with aiohttp.ClientSession() as session:
        try:
            inv = await invidious_search(query, session)
            if inv:
                results.append(inv)
        except Exception as e:
            print("invidious search gather error:", e)

    # 4) direct yt-dlp without proxy
    try:
        direct = await loop.run_in_executor(None, ytdlp_search_top_results, query, 3, False)
        if direct:
            results.extend(direct)
    except Exception as e:
        print("direct yt search error:", e)

    # 5) Google mp3 fallback (sync)
    try:
        g = await loop.run_in_executor(None, google_search_fallback_sync, query, 5)
        if g:
            results.append(g)
    except Exception as e:
        print("google fallback error:", e)

    # 6) SoundCloud fallback (sync)
    try:
        sc = await loop.run_in_executor(None, soundcloud_search_sync, query)
        if sc:
            results.append(sc)
    except Exception as e:
        print("soundcloud fallback error:", e)

    # 7) Vidmate fallback
    try:
        v = await loop.run_in_executor(None, vidmate_search_sync, query)
        if v:
            results.append(v)
    except Exception as e:
        print("vidmate fallback error:", e)

    # return first valid result
    for r in results:
        if r and r.get("webpage_url"):
            cache_put(query, r)
            return r
    return None

# ===== DOWNLOAD WITH COOKIE AUTO-RETRY =====
def download_to_mp3_with_retry(video_url, title_hint=None):
    """
    Try download using yt-dlp. If sign-in required error appears, retry with cookies if available.
    Returns path to mp3 file or None.
    """
    def _attempt(cookiefile=None):
        tmpdir = tempfile.mkdtemp(prefix="music4u_")
        outtmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        if check_ffmpeg():
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        if YTDLP_PROXY:
            opts["proxy"] = YTDLP_PROXY
        if cookiefile:
            opts["cookiefile"] = cookiefile

        try:
            with YoutubeDL(opts) as ydl:
                ydl.extract_info(video_url, download=True)
            # find mp3
            for f in os.listdir(tmpdir):
                if f.lower().endswith(".mp3"):
                    return os.path.join(tmpdir, f), None
            # if no file found, cleanup and treat as fail
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None, "no_mp3_found"
        except Exception as e:
            tb = traceback.format_exc()
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None, str(e) + "\n" + tb

    # attempt without cookies
    path, err = _attempt(cookiefile=None)
    if path:
        return path

    # if error suggests sign-in/captcha then try cookies if available
    if err and is_signin_required_error(err):
        cookies = get_cookies_path()
        if cookies:
            print("🔁 Retrying with cookies:", cookies)
            path2, err2 = _attempt(cookiefile=cookies)
            if path2:
                return path2
            print("❌ Cookie retry failed:", err2)
        else:
            print("⚠️ Sign-in required but no cookies found.")

    # final: no success
    print("download_to_mp3_with_retry final fail for:", video_url, "err:", err)
    return None

# ===== PROCESSING QUEUE =====
def process_queue(chat_id, query):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        BOT.send_message(chat_id, f"🔎 Searching: {query} ...")
        video_info = loop.run_until_complete(find_video_for_query(query))
        if not video_info:
            BOT.send_message(chat_id, f"🚫 Couldn't find: {query}")
            return

        BOT.send_message(chat_id, f"🎵 Found: {video_info.get('title')}\n⬇️ Downloading now...")
        # try to download the chosen candidate; if fails, try other candidates from search list
        # build candidate list (first try cached/primary, then re-run multi-search to get list)
        candidates = []
        # primary candidate
        candidates.append(video_info)
        # supplement with top yt results (sync)
        try:
            more = ytdlp_search_top_results(query, 5, True)
            for m in more:
                if m.get("webpage_url") and m.get("webpage_url") not in [c.get("webpage_url") for c in candidates]:
                    candidates.append(m)
        except Exception as e:
            print("error fetching supplemental yt results:", e)

        # also add invidious / google / soundcloud quick checks
        try:
            import asyncio as _a
            _loop = asyncio.get_event_loop()
            # invidious
            async def _gather_fallbacks(q):
                out = []
                async with aiohttp.ClientSession() as session:
                    inv = await invidious_search(q, session)
                    if inv: out.append(inv)
                g = await _loop.run_in_executor(None, google_search_fallback_sync, q, 5)
                if g: out.append(g)
                sc = await _loop.run_in_executor(None, soundcloud_search_sync, q)
                if sc: out.append(sc)
                vm = await _loop.run_in_executor(None, vidmate_search_sync, q)
                if vm: out.append(vm)
                return out
            additional = loop.run_until_complete(_gather_fallbacks(query))
            for a in additional:
                if a and a.get("webpage_url") and a.get("webpage_url") not in [c.get("webpage_url") for c in candidates]:
                    candidates.append(a)
        except Exception as e:
            print("gather additional candidates error:", e)

        # try each candidate until mp3 produced
        mp3_file = None
        used_title = video_info.get("title", query)
        for cand in candidates:
            url = cand.get("webpage_url")
            if not url:
                continue
            print("Trying candidate:", url)
            mp3_file = download_to_mp3_with_retry(url, title_hint=cand.get("title"))
            if mp3_file:
                used_title = cand.get("title") or used_title
                break
            else:
                print("candidate failed, continuing to next.")

        # final fallback: google mp3 direct (sync)
        if not mp3_file:
            try:
                g = google_search_fallback_sync(query, 8)
                if g and g.get("webpage_url"):
                    print("Trying google mp3 direct:", g.get("webpage_url"))
                    mp3_file = download_to_mp3_with_retry(g.get("webpage_url"))
                    used_title = g.get("title") or used_title
            except Exception as e:
                print("google direct final fallback error:", e)

        # result handling
        if mp3_file:
            try:
                size = os.path.getsize(mp3_file)
                if size > MAX_TELEGRAM_FILE:
                    BOT.send_message(chat_id, f"⚠️ File too large ({round(size/1024/1024,2)} MB)")
                else:
                    with open(mp3_file, "rb") as f:
                        BOT.send_audio(chat_id, f, title=used_title)
                    BOT.send_message(chat_id, "✅ Done!")
            finally:
                shutil.rmtree(os.path.dirname(mp3_file), ignore_errors=True)
        else:
            BOT.send_message(chat_id, f"❌ Download failed: {query} (tried multiple sources)")
    except Exception as e:
        print("process_queue unexpected error:", traceback.format_exc())
        try:
            BOT.send_message(chat_id, f"❌ Error processing: {e}")
        except:
            pass

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
