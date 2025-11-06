import os
import telebot
from flask import Flask, request
from pathlib import Path
from dotenv import load_dotenv
import threading
import json
import tempfile
import shutil
from PIL import Image
from io import BytesIO
import requests
import subprocess
from datetime import datetime

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MAX_FILESIZE = 30 * 1024 * 1024

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR = Path("downloads_music4u")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ===== SUBSCRIBERS =====
DATA_FILE = Path("music4u_subscribers.json")
subscribers = set()
if DATA_FILE.exists():
    try:
        subscribers = set(json.loads(DATA_FILE.read_text()))
    except:
        subscribers = set()

def save_subs():
    DATA_FILE.write_text(json.dumps(list(subscribers)))

# ===== HELPERS =====
def is_admin(uid):
    return uid == ADMIN_ID

# ===== CORE LOGIC =====
active_downloads = {}

def download_and_send(chat_id, query, stop_event):
    tmpdir = tempfile.mkdtemp(prefix="music4u_")
    try:
        info_json = subprocess.check_output(
            [
                "yt-dlp",
                "--no-playlist",
                "--ignore-errors",
                "--no-warnings",
                "--print-json",
                "--skip-download",
                f"ytsearch5:{query}"
            ],
            text=True
        )
        data_list = [json.loads(line) for line in info_json.strip().split("\n") if line.strip()]
        video_found = False
        for data in data_list:
            title = data.get("title", "Unknown")
            url = data.get("webpage_url")
            if not url:
                continue

            out = os.path.join(tmpdir, "%(title)s.%(ext)s")
            cmd = [
                "yt-dlp", "--no-playlist", "--ignore-errors", "--no-warnings",
                "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
                "--quiet", "--output", out, url
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while proc.poll() is None:
                if stop_event.is_set():
                    proc.terminate()
                    bot.send_message(chat_id, "❌ Download stopped")
                    return
            files = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
            if files:
                fpath = os.path.join(tmpdir, files[0])
                if os.path.getsize(fpath) > MAX_FILESIZE:
                    bot.send_message(chat_id, "⚠️ ဖိုင်အရွယ်အစားကြီးနေသည်။ Telegram မှ ပို့လို့မရပါ။")
                    return
                caption = f"🎶 {title}\n\n_Music 4U မှ ပေးပို့နေပါသည်_ 🎧"
                thumb_url = data.get("thumbnail")
                if thumb_url:
                    try:
                        img = Image.open(BytesIO(requests.get(thumb_url, timeout=5).content))
                        thumb_path = os.path.join(tmpdir, "thumb.jpg")
                        img.save(thumb_path)
                        with open(fpath, "rb") as aud, open(thumb_path, "rb") as th:
                            bot.send_audio(chat_id, aud, caption=caption, thumb=th, parse_mode="Markdown")
                    except:
                        with open(fpath, "rb") as aud:
                            bot.send_audio(chat_id, aud, caption=caption, parse_mode="Markdown")
                else:
                    with open(fpath, "rb") as aud:
                        bot.send_audio(chat_id, aud, caption=caption, parse_mode="Markdown")
                bot.send_message(chat_id, "✅ သီချင်း ပေးပို့ပြီးပါပြီ 🎧")
                video_found = True
                break
        if not video_found:
            bot.send_message(chat_id, "🚫 ဖိုင်မတွေ့ပါ၊ အခြား keyword ဖြင့်စမ်းကြည့်ပါ။")
    except Exception as e:
        bot.send_message(chat_id, f"❌ အမှားတစ်ခုဖြစ်ပါသည်: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def process_queue(chat_id):
    stop_event = active_downloads[chat_id]['stop']
    q = active_downloads[chat_id]['queue']
    while not q.empty() and not stop_event.is_set():
        query = q.get()
        download_and_send(chat_id, query, stop_event)
        q.task_done()
    if chat_id in active_downloads and q.empty():
        active_downloads.pop(chat_id, None)

# ===== TELEGRAM COMMANDS =====
@bot.message_handler(commands=['start','help'])
def start(msg):
    bot.reply_to(msg, (
        "🎶 *Welcome to Music 4U*\n\n"
        "သီချင်းရှာရန်: `/play <နာမည်>` သို့မဟုတ် YouTube link\n"
        "/stop - ဒေါင်းလုပ်ရပ်ရန်\n"
        "/subscribe - Broadcast join\n"
        "/unsubscribe - Broadcast cancel\n"
        "/status - Server uptime\n"
        "/about - Bot info\n"
        "\n⚡ Fast • Reliable • 24/7 Online"
    ), parse_mode="Markdown")

@bot.message_handler(commands=['play'])
def play(msg):
    chat_id = msg.chat.id
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "အသုံးပြုနည်း: `/play <နာမည်>`", parse_mode="Markdown")
        return
    query = parts[1].strip()
    if chat_id not in active_downloads:
        from queue import Queue
        import threading
        stop_event = threading.Event()
        q = Queue()
        q.put(query)
        active_downloads[chat_id] = {"stop": stop_event, "queue": q}
        threading.Thread(target=process_queue, args=(chat_id,), daemon=True).start()
    else:
        active_downloads[chat_id]['queue'].put(query)
        bot.reply_to(msg, "⏳ Download queue ထဲသို့ထည့်လိုက်ပါသည်။")

@bot.message_handler(commands=['stop'])
def stop(msg):
    chat_id = msg.chat.id
    if chat_id in active_downloads:
        active_downloads[chat_id]['stop'].set()
        bot.send_message(chat_id, "🛑 Download ရပ်လိုက်ပါသည်။")
    else:
        bot.send_message(chat_id, "ရပ်ရန် download မရှိပါ။")

# ===== FLASK SERVER & WEBHOOK =====
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def home():
    return "✅ Music 4U Bot is Alive!"

if __name__ == "__main__":
    # Set webhook
    bot.remove_webhook()
    WEBHOOK_URL = f"https://YOUR_RAILWAY_APP_URL/{TOKEN}"  # <-- Change to your Railway app URL
    bot.set_webhook(url=WEBHOOK_URL)
    port = int(os.environ.get("PORT", 8080))
    print("✅ Bot and Webhook server running!")
    app.run(host="0.0.0.0", port=port)
