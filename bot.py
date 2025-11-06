import telebot, threading, subprocess, tempfile, os, time, json, requests, shutil
from pathlib import Path
from PIL import Image
from io import BytesIO
from flask import Flask
from threading import Thread

# ===== CONFIG =====
TOKEN = "8492766093:AAEv316ExLHVlNm9j0otjpKS319BqUiowu0"
ADMIN_ID = 5720351176
DATA_FILE = Path("music_mm_subscribers.json")
DOWNLOAD_DIR = Path("downloads_music_mm")
RATE_LIMIT_SECONDS = 60
MAX_FILESIZE = 30 * 1024 * 1024

bot = telebot.TeleBot(TOKEN)
DOWNLOAD_DIR.mkdir(exist_ok=True)
subscribers = set()
user_last_use = {}
active_downloads = {}

# ===== FLASK KEEP_ALIVE =====
app = Flask('')

@app.route('/')
def home():
    return "Music 4U Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

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
        "သီချင်းရှာရန် /play <နာမည်သို့ YouTube link>\n"
        "/stop - ဒေါင်းလုပ်ရပ်ရန်\n"
        "/subscribe - Broadcast join\n"
        "/unsubscribe - Broadcast cancel\n\n"
        "🕐 သတိပေးချက် - တစ်ကြိမ်ဖွင့်ပြီးနောက် အချို့အချိန်ကြာမှ ပြန်အသုံးပြုနိုင်ပါသည်။"
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

@bot.message_handler(commands=['blast'])
def blast(msg):
    if not is_admin(msg.from_user.id):
        bot.reply_to(msg, "သင် admin မဟုတ်ပါ။")
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "အသုံးပြုနည်း: /blast <မက်ဆေ့ချ်>")
        return
    text = parts[1]
    bot.reply_to(msg, f"📢 Subscribers {len(subscribers)} ဦးသို့ မက်ဆေ့ချ်ပေးနေသည်...")
    for uid in list(subscribers):
        try:
            bot.send_message(uid, text)
            time.sleep(0.3)
        except:
            continue
    bot.send_message(msg.chat.id, "✅ ပေးပို့ပြီးပါပြီ။")

# ===== PLAY COMMAND =====
@bot.message_handler(commands=['play'])
def play(msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    now = time.time()
    last_use = user_last_use.get(user_id,0)
    if now - last_use < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last_use))
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
    th = threading.Thread(target=download_and_send, args=(chat_id, query, stop_event))
    th.start()

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
def download_and_send(chat_id, query, stop_event):
    tmpdir = tempfile.mkdtemp(prefix="music_mm_")
    progress_msg_id = None
    last_update_time = 0
    UPDATE_INTERVAL = 0.8
    TIMEOUT = 20

    try:
        try:
            info_json = subprocess.check_output([
                "yt-dlp","--no-playlist","--print-json","--skip-download",
                f"ytsearch1:{query}"
            ], text=True)
            data = json.loads(info_json)
            title = data.get("title","Unknown")
            bot.send_message(chat_id,f"🔎 `{title}` ရှာနေပါသည်…", parse_mode="Markdown")
        except:
            bot.send_message(chat_id,"🚫 သီချင်း ရှာမတွေ့ပါ /play နဲ့ search ပြန်စမ်းပါ")
            return

        out = os.path.join(tmpdir, "%(title)s.%(ext)s")
        cmd = ["yt-dlp","--no-playlist","--extract-audio","--audio-format","mp3",
               "--audio-quality","5","--output",out,"--print-json",f"ytsearch1:{query}"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        start_time = time.time()
        info_line = None

        while True:
            if stop_event.is_set():
                proc.terminate()
                bot.send_message(chat_id,"❌ Download stopped")
                return
            if time.time() - start_time > TIMEOUT:
                proc.terminate()
                bot.send_message(chat_id,"⏱️ Download timeout, auto cancel")
                return

            line = proc.stdout.readline()
            if not line:
                break
            try:
                data_line = json.loads(line)
                if 'title' in data_line:
                    info_line = line
                if 'progress_percent' in data_line:
                    percent = int(data_line['progress_percent'])
                    now = time.time()
                    if now - last_update_time > UPDATE_INTERVAL:
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

        if not info_line:
            bot.send_message(chat_id,"🚫 သီချင်း မတွေ့ပါ /play နဲ့ search ပြန်စမ်းပါ")
            return

        files = [f for f in os.listdir(tmpdir) if f.endswith(".mp3")]
        if not files:
            bot.send_message(chat_id,"🚫 ဖိုင် မတွေ့ပါ။")
            return
        fpath = os.path.join(tmpdir, files[0])
        if os.path.getsize(fpath) > MAX_FILESIZE:
            bot.send_message(chat_id,"⚠️ ဖိုင်အရွယ်အစားကြီးနေသည်။ Telegram မှ ပို့လို့မရပါ။")
            return

        caption = f"🎶 {title}\n\nMusic_MM မှ ပေးပို့နေပါသည်။"
        thumbnail = data.get("thumbnail",None)
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

# ===== START EVERYTHING =====
keep_alive()           # Flask server start for Replit 24/7
bot.infinity_polling()  # Telegram bot start
