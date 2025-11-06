import telebot, threading, subprocess, tempfile, os, time, json, shutil
from pathlib import Path
from PIL import Image
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from queue import Queue
from flask import Flask
import requests

# ===== KEEP ALIVE SERVER =====
app = Flask(__name__)
@app.route('/')
def home():
    return "✅ Music 4U Bot သည် အသက်ရှင်နေပါသည်!"

def run_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()

# ===== LOAD CONFIG =====
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DOWNLOAD_DIR = Path("downloads_music4u")
MAX_FILESIZE = 30 * 1024 * 1024
START_TIME = datetime.utcnow()

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR.mkdir(exist_ok=True)
subscribers = set()
active_downloads = {}

keep_alive()

# ===== SUBSCRIBERS =====
DATA_FILE = Path("music4u_subscribers.json")
def load_subscribers():
    global subscribers
    if DATA_FILE.exists():
        try: subscribers = set(json.loads(DATA_FILE.read_text()))
        except: subscribers = set()
threading.Thread(target=load_subscribers, daemon=True).start()

def save_subs():
    DATA_FILE.write_text(json.dumps(list(subscribers)))

def is_admin(uid): return uid == ADMIN_ID

# ===== COMMANDS =====
@bot.message_handler(commands=['start','help'])
def start(msg):
    bot.reply_to(msg, (
        "🎶 *Music 4U သို့ကြိုဆိုပါတယ်!*\n\n"
        "သီချင်းရှာရန်: `/play <နာမည်>` သို့မဟုတ် YouTube link\n"
        "/stop - ဒေါင်းလုပ်ရပ်ရန်\n"
        "/subscribe - Broadcast join\n"
        "/unsubscribe - Broadcast cancel\n"
        "/status - Server uptime\n"
        "/about - Bot info\n"
        "\n⚡ လျင်မြန် • ယုံကြည်စိတ်ချ • 24/7 Online"
    ), parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def about(msg):
    bot.reply_to(msg, (
        "🎵 *Music 4U Bot*\n"
        "Created by ❤️ Developer\n"
        "Powered by `yt-dlp`\n24/7 Cloud Hosted\n\n"
        "Commands:\n• /play <သီချင်း>\n• /stop\n• /subscribe\n• /unsubscribe\n• /status\n• /about"
    ), parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def status(msg):
    uptime = datetime.utcnow() - START_TIME
    bot.reply_to(msg, f"🕐 *Uptime:* {str(uptime).split('.')[0]}\n👥 Subscribers: {len(subscribers)}", parse_mode="Markdown")

@bot.message_handler(commands=['subscribe'])
def sub(msg):
    subscribers.add(msg.from_user.id)
    save_subs()
    bot.reply_to(msg, "✅ Broadcast မက်ဆေ့ချ်များ ရရှိရန် သဘောတူပြီးပါပြီ။")

@bot.message_handler(commands=['unsubscribe'])
def unsub(msg):
    if msg.from_user.id in subscribers:
        subscribers.remove(msg.from_user.id)
        save_subs()
        bot.reply_to(msg, "❌ Broadcast မက်ဆေ့ချ်များ ရပ်လိုက်ပါသည်။")
    else:
        bot.reply_to(msg, "သင်သည် စာရင်းတွင်မပါသေးပါ။")

# ===== PLAY / STOP =====
@bot.message_handler(commands=['play'])
def play(msg):
    chat_id = msg.chat.id
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "အသုံးပြုနည်း: `/play <နာမည်>`", parse_mode="Markdown")
        return
    query = parts[1].strip()
    if chat_id not in active_downloads:
        stop_event = threading.Event()
        q = Queue()
        q.put(query)
        active_downloads[chat_id] = {"stop": stop_event, "queue": q}
        threading.Thread(target=process_queue, args=(chat_id,), daemon=True).start()
    else:
        active_downloads[chat_id]['queue'].put(query)
        bot.reply_to(msg, "⏳ Queue ထဲသို့ထည့်လိုက်ပါသည်။")

@bot.message_handler(commands=['stop'])
def stop(msg):
    chat_id = msg.chat.id
    if chat_id in active_downloads:
        active_downloads[chat_id]['stop'].set()
        bot.reply_to(msg, "🛑 Download ရပ်လိုက်ပါသည်။")
    else:
        bot.reply_to(msg, "ရပ်ရန် download မရှိပါ။")

# ===== QUEUE PROCESSING =====
def process_queue(chat_id):
    stop_event = active_downloads[chat_id]['stop']
    q = active_downloads[chat_id]['queue']
    while not q.empty() and not stop_event.is_set():
        query = q.get()
        download_and_send(chat_id, query, stop_event)
        q.task_done()
    if chat_id in active_downloads and q.empty():
        active_downloads.pop(chat_id, None)

# ===== CORE LOGIC =====
def download_and_send(chat_id, query, stop_event):
    tmpdir = tempfile.mkdtemp(prefix="music4u_")
    try:
        info_json = subprocess.check_output(
            ["yt-dlp","--no-playlist","--print-json","--skip-download",f"ytsearch5:{query}"],
            text=True
        )
        data_list = [json.loads(line) for line in info_json.strip().split("\n")]
        video_found = False
        for data in data_list:
            title = data.get("title","Unknown")
            url = data.get("webpage_url")
            if not url: continue

            out = os.path.join(tmpdir, "%(title)s.%(ext)s")
            cmd = ["yt-dlp","--no-playlist","--extract-audio","--audio-format","mp3","--audio-quality","0","--quiet","--output",out,url]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while proc.poll() is None:
                if stop_event.is_set():
                    proc.terminate()
                    bot.send_message(chat_id,"❌ Download ရပ်လိုက်ပါသည်။")
                    return
                time.sleep(0.3)

            files = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
            if files:
                fpath = os.path.join(tmpdir, files[0])
                if os.path.getsize(fpath) > MAX_FILESIZE:
                    bot.send_message(chat_id,"⚠️ ဖိုင်အရွယ်အစားကြီးနေပါသည်။ Telegram မှ ပို့လို့မရပါ။")
                    return
                caption = f"🎶 {title}\n\n_Music 4U မှ ပေးပို့နေပါသည်_ 🎧"
                with open(fpath,"rb") as aud:
                    bot.send_audio(chat_id,aud,caption=caption,parse_mode="Markdown")
                bot.send_message(chat_id,"✅ သီချင်း ပေးပို့ပြီးပါပြီ 🎧")
                video_found = True
                break

        if not video_found:
            bot.send_message(chat_id,"🚫 ဖိုင် မတွေ့ပါ၊ အခြား keyword ဖြင့် စမ်းကြည့်ပါ။")

    except Exception as e:
        bot.send_message(chat_id,f"❌ အမှားတစ်ခုဖြစ်ပါသည်: {e}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ===== RUN BOT =====
print("✅ Bot is running...")
bot.infinity_polling(skip_pending=True)
