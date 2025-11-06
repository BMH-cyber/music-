import telebot, threading, subprocess, tempfile, os, time, json, requests, shutil
from pathlib import Path
from PIL import Image
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from queue import Queue

# ===== KEEP ALIVE SERVER =====
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "✅ Music 4U Bot is Alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

keep_alive()  # 🚀 Start keep-alive web server (for Replit 24/7)

# ===== LOAD CONFIG =====
load_dotenv()  # load .env file
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DOWNLOAD_DIR = Path("downloads_music4u")
MAX_FILESIZE = 30 * 1024 * 1024
START_TIME = datetime.utcnow()

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR.mkdir(exist_ok=True)
subscribers = set()
active_downloads = {}  # chat_id -> {"stop": Event, "queue": Queue()}

# ===== LOAD SUBSCRIBERS =====
DATA_FILE = Path("music4u_subscribers.json")
def load_subscribers():
    global subscribers
    if DATA_FILE.exists():
        try:
            subscribers = set(json.loads(DATA_FILE.read_text()))
        except:
            subscribers = set()
threading.Thread(target=load_subscribers, daemon=True).start()

def save_subs():
    DATA_FILE.write_text(json.dumps(list(subscribers)))

def is_admin(uid): return uid == ADMIN_ID

# ===== BASIC COMMANDS =====
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

@bot.message_handler(commands=['about'])
def about(msg):
    bot.reply_to(msg, (
        "🎵 *Music 4U Bot*\nCreated by ❤️ Developer\nPowered by `yt-dlp`\n24/7 Cloud Hosted\n\n"
        "Commands:\n• /play <song>\n• /stop\n• /subscribe\n• /unsubscribe\n• /status\n• /about"
    ), parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def status(msg):
    uptime = datetime.utcnow() - START_TIME
    bot.reply_to(msg, f"🕐 *Uptime:* {str(uptime).split('.')[0]}\n👥 Subscribers: {len(subscribers)}",
                 parse_mode="Markdown")

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
        bot.reply_to(msg, "သင်မရရှိထားပါ။")

@bot.message_handler(commands=['blast'])
def blast(msg):
    if not is_admin(msg.from_user.id):
        bot.reply_to(msg, "🚫 သင် admin မဟုတ်ပါ။")
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "အသုံးပြုနည်း: `/blast <မက်ဆေ့ချ်>`", parse_mode="Markdown")
        return
    text = parts[1]
    bot.reply_to(msg, f"📢 Subscribers {len(subscribers)} ဦးသို့ မက်ဆေ့ချ်ပေးနေသည်...")
    for uid in list(subscribers):
        try:
            bot.send_message(uid, text)
            time.sleep(0.2)
        except:
            continue
    bot.send_message(msg.chat.id, "✅ ပေးပို့ပြီးပါပြီ။")

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
        threading.Thread(target=process_queue, args=(chat_id,)).start()
    else:
        active_downloads[chat_id]['queue'].put(query)
        bot.reply_to(msg, "⏳ Download queue ထဲသို့ထည့်လိုက်ပါသည်။")

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
        active_downloads.pop(chat_id,None)

# ===== CORE LOGIC =====
def download_and_send(chat_id, query, stop_event):
    tmpdir = tempfile.mkdtemp(prefix="music4u_")
    progress_msg_id = None
    last_update_time = 0
    UPDATE_INTERVAL = 0.5
    TIMEOUT = 30

    try:
        info_json = subprocess.check_output(
            ["yt-dlp","--no-playlist","--print-json","--skip-download",f"ytsearch1:{query}"],
            text=True
        )
        data = json.loads(info_json)
        title = data.get("title","Unknown")
        bot.send_message(chat_id,f"🔎 `{title}` ကိုရှာနေပါသည်…", parse_mode="Markdown")

        out = os.path.join(tmpdir, "%(title)s.%(ext)s")
        cmd = [
            "yt-dlp","--no-playlist","--extract-audio","--audio-format","mp3",
            "--audio-quality","0","--quiet","--output",out,f"ytsearch1:{query}"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        start_time = time.time()

        while proc.poll() is None:
            if stop_event.is_set():
                proc.terminate()
                bot.send_message(chat_id,"❌ Download stopped")
                return
            if time.time() - start_time > TIMEOUT:
                proc.terminate()
                bot.send_message(chat_id,"⏱️ Download timeout")
                return
            now = time.time()
            if now - last_update_time > UPDATE_INTERVAL:
                dots = "." * int(((now*2)%4)+1)
                msg_text = f"📥 Downloading{dots}"
                if not progress_msg_id:
                    m = bot.send_message(chat_id,msg_text)
                    progress_msg_id = m.message_id
                else:
                    try: bot.edit_message_text(msg_text,chat_id,progress_msg_id)
                    except: pass
                last_update_time = now
            time.sleep(0.3)

        files = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
        if not files:
            bot.send_message(chat_id,"🚫 ဖိုင် မတွေ့ပါ။")
            return
        fpath = os.path.join(tmpdir, files[0])
        if os.path.getsize(fpath) > MAX_FILESIZE:
            bot.send_message(chat_id,"⚠️ ဖိုင်အရွယ်အစားကြီးနေသည်။ Telegram မှ ပို့လို့မရပါ။")
            return

        caption = f"🎶 {title}\n\n_Music 4U မှ ပေးပို့နေပါသည်_ 🎧"
        thumb_url = data.get("thumbnail")
        if thumb_url:
            try:
                img = Image.open(BytesIO(requests.get(thumb_url, timeout=5).content))
                thumb_path = os.path.join(tmpdir,"thumb.jpg")
                img.save(thumb_path)
                with open(fpath,"rb") as aud, open(thumb_path,"rb") as th:
                    bot.send_audio(chat_id,aud,caption=caption,thumb=th,parse_mode="Markdown")
            except:
                with open(fpath,"rb") as aud:
                    bot.send_audio(chat_id,aud,caption=caption,parse_mode="Markdown")
        else:
            with open(fpath,"rb") as aud:
                bot.send_audio(chat_id,aud,caption=caption,parse_mode="Markdown")

        bot.send_message(chat_id,"✅ သီချင်း ပေးပို့ပြီးပါပြီ 🎧")

    except Exception as e:
        bot.send_message(chat_id,f"❌ အမှားတစ်ခုဖြစ်ပါသည်: {e}")
    finally:
        shutil.rmtree(tmpdir,ignore_errors=True)

# ===== RUN BOT =====
bot.infinity_polling(timeout=60, long_polling_timeout=30)
