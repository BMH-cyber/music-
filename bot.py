import telebot, threading, subprocess, tempfile, os, time, json, requests, shutil
from pathlib import Path
from PIL import Image
from io import BytesIO
from flask import Flask
from threading import Thread

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATA_FILE = Path("music_mm_subscribers.json")
DOWNLOAD_DIR = Path("downloads_music_mm")
RATE_LIMIT_SECONDS = 60
MAX_FILESIZE = 30 * 1024 * 1024

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR.mkdir(exist_ok=True)
subscribers = set()
user_last_use = {}
active_downloads = {}

# ===== LOAD SUBSCRIBERS =====
def load_subscribers():
    global subscribers
    if DATA_FILE.exists():
        try:
            subscribers = set(json.loads(DATA_FILE.read_text()))
        except:
            subscribers = set()
threading.Thread(target=load_subscribers).start()

def save_subs():
    DATA_FILE.write_text(json.dumps(list(subscribers)))

def is_admin(uid): return uid == ADMIN_ID

# ===== COMMANDS =====
@bot.message_handler(commands=['start','help'])
def start(msg):
    bot.reply_to(msg, (
        "🎵 *Music_MM Myanmar Version*\n\n"
        "/play <နာမည်သို့ YouTube link>\n"
        "/stop - ဒေါင်းလုပ်ရပ်ရန်\n"
        "/subscribe - Broadcast join\n"
        "/unsubscribe - Broadcast cancel\n"
    ), parse_mode="Markdown")

@bot.message_handler(commands=['subscribe'])
def sub(msg):
    subscribers.add(msg.from_user.id)
    save_subs()
    bot.reply_to(msg, "✅ သင်သည် Broadcast မက်ဆေ့ချ်များ ရရှိရန် သဘောတူပြီးဖြစ်သည်။")

@bot.message_handler(commands=['unsubscribe'])
def unsub(msg):
    if msg.from_user.id in subscribers:
        subscribers.remove(msg.from_user.id)
        save_subs()
        bot.reply_to(msg, "❌ Broadcast မက်ဆေ့ချ်များ ရပ်လိုက်ပါသည်။")
    else:
        bot.reply_to(msg, "သင်မရရှိထားပါ။")

# ===== PLAY COMMAND =====
@bot.message_handler(commands=['play'])
def play(msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    now = time.time()
    if now - user_last_use.get(user_id,0) < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - user_last_use.get(user_id,0)))
        bot.reply_to(msg, f"⚠️ တစ်ခဏမကြာသေးပါ။ {wait} စက္ကန့်အကြာ ပြန်အသုံးပြုနိုင်ပါသည်။")
        return
    user_last_use[user_id] = now

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "အသုံးပြုနည်း: /play <YouTube link သို့ သီချင်းနာမည်>")
        return
    query = parts[1].strip()

    if chat_id in active_downloads:
        bot.reply_to(msg, "ဤ chat တွင် download တစ်ခုရှိနေပါသည်။ /stop ဖြင့် ရပ်ပါ။")
        return

    stop_event = threading.Event()
    active_downloads[chat_id] = {"stop": stop_event}
    threading.Thread(target=download_and_send_fast, args=(chat_id, query, stop_event)).start()

# ===== STOP COMMAND =====
@bot.message_handler(commands=['stop'])
def stop(msg):
    chat_id = msg.chat.id
    if chat_id not in active_downloads:
        bot.reply_to(msg, "ရပ်ရန် download မရှိပါ။")
        return
    active_downloads[chat_id]['stop'].set()
    bot.reply_to(msg, "🛑 ဒေါင်းလုပ် ရပ်လိုက်ပါသည်။")

# ===== CORE LOGIC =====
def download_and_send_fast(chat_id, query, stop_event):
    tmpdir = tempfile.mkdtemp(prefix="music_mm_")
    progress_msg_id = None
    last_update_time = 0
    UPDATE_INTERVAL = 0.5
    try:
        out = os.path.join(tmpdir, "%(title)s.%(ext)s")
        cmd = [
            "yt-dlp","--no-playlist","--extract-audio","--audio-format","mp3",
            "--audio-quality","5","--print-json","--output",out,f"ytsearch1:{query}"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        title, thumbnail, fpath = None, None, None

        for line in proc.stdout:
            if stop_event.is_set():
                proc.terminate()
                bot.send_message(chat_id,"❌ Download stopped")
                return
            try:
                data = json.loads(line)
                if not title and 'title' in data:
                    title = data['title']
                    thumbnail = data.get('thumbnail',None)
                    bot.send_message(chat_id,f"🔎 `{title}` ရှာနေပါသည်…", parse_mode="Markdown")
                if 'filename' in data:
                    fpath = data['filename']
                if 'progress_percent' in data:
                    now = time.time()
                    if now - last_update_time > UPDATE_INTERVAL:
                        percent = int(float(data['progress_percent']))
                        if not progress_msg_id:
                            m = bot.send_message(chat_id,f"📥 Downloading… {percent}%")
                            progress_msg_id = m.message_id
                        else:
                            try:
                                bot.edit_message_text(f"📥 Downloading… {percent}%", chat_id, progress_msg_id)
                            except:
                                pass
                        last_update_time = now
            except:
                continue
        proc.wait()

        if not fpath or not os.path.exists(fpath):
            bot.send_message(chat_id,"🚫 သီချင်းမတွေ့ပါ")
            return
        if os.path.getsize(fpath) > MAX_FILESIZE:
            bot.send_message(chat_id,"⚠️ ဖိုင်အရွယ်အစားကြီးနေသည်။ Telegram မှ ပို့လို့မရပါ။")
            return

        caption = f"🎶 {title}\n\nMusic_MM မှ ပေးပို့နေပါသည်။"
        if thumbnail:
            try:
                img = Image.open(BytesIO(requests.get(thumbnail).content))
                thumb_path = os.path.join(tmpdir,"thumb.jpg")
                img.save(thumb_path)
                with open(fpath,"rb") as aud, open(thumb_path,"rb") as thumb:
                    bot.send_audio(chat_id,aud,caption=caption,thumb=thumb)
            except:
                with open(fpath,"rb") as aud:
                    bot.send_audio(chat_id,aud,caption=caption)
        else:
            with open(fpath,"rb") as aud:
                bot.send_audio(chat_id,aud,caption=caption)

        bot.send_message(chat_id,"✅ သီချင်း ပေးပို့ပြီးပါပြီ 🎧")

    except Exception as e:
        bot.send_message(chat_id,f"❌ အမှားတစ်ခုဖြစ်ပါသည်: {e}")
    finally:
        shutil.rmtree(tmpdir,ignore_errors=True)
        active_downloads.pop(chat_id,None)

# ===== KEEP ALIVE (Flask) =====
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run_flask():
    app.run(host='0.0.0.0', port=3000)

Thread(target=run_flask).start()
bot.infinity_polling()
