import os
import re
import time
import json
import yt_dlp
import tempfile
from telebot import TeleBot, types
from youtubesearchpython import VideosSearch
from pathlib import Path

BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace this
bot = TeleBot(BOT_TOKEN)

# ----------------- CACHE SYSTEM -----------------
CACHE_FILE = Path("music_cache.json")
CACHE_TTL = 7 * 86400  # 7 days in seconds

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.load(open(CACHE_FILE, "r", encoding="utf-8"))
        except:
            return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE, "w", encoding="utf-8"))

cache_data = load_cache()

def cache_get(query):
    item = cache_data.get(query.lower().strip())
    if not item:
        return None
    if time.time() - item.get("ts", 0) > CACHE_TTL:
        cache_data.pop(query.lower().strip(), None)
        save_cache(cache_data)
        return None
    return item.get("results")

def cache_put(query, results):
    cache_data[query.lower().strip()] = {
        "ts": int(time.time()),
        "results": results
    }
    save_cache(cache_data)

# ----------------- YouTube Search -----------------
def search_youtube(query):
    """Enhanced YouTube search (Myanmar + English) with cache"""
    cached = cache_get(query)
    if cached:
        return cached

    try:
        query = query.strip()
        results = []
        is_myanmar = bool(re.search(r'[\u1000-\u109F]', query))

        search_terms = [
            query,
            f"{query} song",
            f"{query} official music video",
            f"{query} lyrics",
        ]
        if is_myanmar:
            search_terms += [
                f"{query} သီချင်း",
                f"{query} သီချင်းများ",
                f"{query} official",
                f"{query} cover"
            ]

        for term in search_terms:
            search = VideosSearch(term, limit=10)  # Top 10 results
            res = search.result().get('result', [])
            for r in res:
                if 'link' in r and r['link'] not in [x['link'] for x in results]:
                    results.append({
                        "title": r.get("title"),
                        "link": r.get("link"),
                        "duration": r.get("duration"),
                        "channel": r.get("channel", {}).get("name", "Unknown")
                    })
            if results:
                break

        if results:
            cache_put(query, results)
        return results if results else None

    except Exception as e:
        print(f"[❌ ERROR search_youtube]: {e}")
        return None

# ----------------- Download YouTube MP3 -----------------
def download_audio(url):
    try:
        temp_dir = tempfile.mkdtemp()
        out_path = os.path.join(temp_dir, "%(title)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_path,
            "quiet": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info)
            mp3_file = os.path.splitext(file_name)[0] + ".mp3"

        return mp3_file

    except Exception as e:
        print(f"[❌ ERROR download_audio]: {e}")
        return None

# ----------------- Queue System -----------------
song_queue = {}  # chat_id: list of song dicts

def play_next_song(chat_id):
    if chat_id not in song_queue or not song_queue[chat_id]:
        bot.send_message(chat_id, "✅ Queue finished.")
        return

    song = song_queue[chat_id].pop(0)
    bot.send_message(chat_id, f"⬇️ Downloading: {song['title']}")
    mp3_file = download_audio(song['link'])
    if mp3_file:
        with open(mp3_file, "rb") as f:
            bot.send_audio(chat_id, f, caption=f"🎵 {song['title']}")
        os.remove(mp3_file)
    else:
        bot.send_message(chat_id, f"❌ Failed to download: {song['title']}")

    if song_queue[chat_id]:
        play_next_song(chat_id)

# ----------------- Telegram Handlers -----------------
@bot.message_handler(commands=['start'])
def start_message(msg):
    bot.reply_to(msg, "🎵 မင်္ဂလာပါ!\nသီချင်းနာမည်ကိုသာ ပေးပါ။ English + မြန်မာ နှစ်မျိုးနားလည်ပါတယ်။")

@bot.message_handler(func=lambda m: True)
def search_and_inline(msg):
    query = msg.text.strip()
    bot.reply_to(msg, f"🔍 Searching songs for: {query}")

    results = search_youtube(query)
    if not results:
        bot.send_message(msg.chat.id, "🚫 Couldn't find any songs for this query.")
        return

    song_queue[msg.chat.id] = results[:10]  # Top 10 results

    markup = types.InlineKeyboardMarkup()
    for i, song in enumerate(song_queue[msg.chat.id]):
        markup.add(types.InlineKeyboardButton(
            f"{i+1}. {song['title']} ({song['channel']})", callback_data=song['link']
        ))
    bot.send_message(msg.chat.id, "🎶 Click a song to download:", reply_markup=markup)

# ----------------- Callback for Inline Buttons -----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    url = call.data
    chat_id = call.message.chat.id

    # Add clicked song to front of queue
    song_queue.setdefault(chat_id, [])
    # Remove from queue if already exists
    song_queue[chat_id] = [s for s in song_queue[chat_id] if s['link'] != url]
    # Add clicked song at front
    song_info = next((s for s in cache_data.get(chat_id, {}).get('results', []) if s['link']==url), None)
    if song_info:
        song_queue[chat_id].insert(0, song_info)
    else:
        # fallback minimal info
        song_queue[chat_id].insert(0, {"title":"Selected song","link":url,"duration":"","channel":"Unknown"})

    bot.answer_callback_query(call.id, "⬇️ Downloading...")
    play_next_song(chat_id)
    bot.answer_callback_query(call.id, "✅ Sent!")

# ----------------- Run Bot -----------------
if __name__ == "__main__":
    print("✅ Music Bot Running with Cache + Inline Buttons + Queue Optimized...")
    bot.infinity_polling(timeout=30, long_polling_timeout=10)
