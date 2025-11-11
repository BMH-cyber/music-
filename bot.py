# bot.py
import os
import threading
import traceback
import tempfile
import shutil
from flask import Flask, request
import telebot
import yt_dlp
import requests
from collections import defaultdict

# ===== Environment Variables =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("❌ BOT_TOKEN or WEBHOOK_URL missing in environment variables!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===== Webhook Setup =====
def setup_webhook():
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
        print("✅ Webhook set successfully")
    except Exception as e:
        print("❌ Webhook setup failed:", e)

# ===== Song Queue =====
song_queues = defaultdict(list)
queue_lock = threading.Lock()

def download_song(chat_id, video_url, title):
    temp_dir = tempfile.mkdtemp()
    msg = bot.send_message(chat_id, f"🔎 Downloading '{title}'...")
    try:
        def progress_hook(d):
            if d['status']=='downloading':
                percent = d.get('_percent_str','0%').strip()
                bot.edit_message_text(f"⬇ Downloading: {percent}", chat_id, msg.message_id)
            elif d['status']=='finished':
                bot.edit_message_text("✅ Download finished, sending...", chat_id, msg.message_id)

        ydl_opts = {
            'format':'bestaudio/best',
            'outtmpl':os.path.join(temp_dir,'%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks':[progress_hook],
            'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}],
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            file_path = ydl.prepare_filename(info).replace(".webm",".mp3").replace(".m4a",".mp3")
        with open(file_path,'rb') as f:
            bot.send_audio(chat_id, f, title=title)
    except Exception as e:
        traceback.print_exc()
        bot.send_message(chat_id, f"❌ Error: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def user_queue_worker(user_id):
    while True:
        with queue_lock:
            if song_queues[user_id]:
                video_url, title = song_queues[user_id].pop(0)
            else:
                break
        download_song(user_id, video_url, title)

# ===== /song Command =====
@bot.message_handler(commands=['song'])
def song_handler(message):
    args = message.text.split(maxsplit=1)
    if len(args)<2:
        bot.reply_to(message, "❌ သီချင်းနာမည်ထည့်ပါ\nUsage: /song <သီချင်းနာမည်>")
        return
    query = args[1]
    try:
        ydl_opts = {'quiet':True, 'noplaylist':True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch5:{query}", download=False)['entries']
        if not search_results:
            bot.reply_to(message,"❌ သီချင်းမတွေ့ပါ")
            return
        markup = telebot.types.InlineKeyboardMarkup()
        for i, entry in enumerate(search_results,1):
            title = entry.get('title','Unknown')
            video_url = entry.get('webpage_url')
            markup.add(
                telebot.types.InlineKeyboardButton(f"{i}. {title}", callback_data=f"download|{video_url}|{title}")
            )
        bot.send_message(message.chat.id,"✅ Select a song to download:", reply_markup=markup)
    except Exception as e:
        traceback.print_exc()
        bot.reply_to(message,f"❌ Error: {e}")

# ===== Callback for Song Selection =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("download|"))
def callback_download(call):
    try:
        _, video_url, title = call.data.split("|",2)
        user_id = call.message.chat.id
        with queue_lock:
            song_queues[user_id].append((video_url, title))
        bot.answer_callback_query(call.id, f"✅ Added to queue: {title}")
        threading.Thread(target=user_queue_worker, args=(user_id,), daemon=True).start()
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {e}")

# ===== /cancel Command =====
@bot.message_handler(commands=['cancel'])
def cancel_handler(message):
    user_id = message.chat.id
    with queue_lock:
        if song_queues[user_id]:
            song_queues[user_id].clear()
            bot.reply_to(message, "❌ သင့် queue ကိုဖျက်ပြီးပါပြီ")
        else:
            bot.reply_to(message, "⚠️ သင့် queue ရှိခြင်းမရှိပါ")

# ===== /status Command =====
@bot.message_handler(commands=['status'])
def status_handler(message):
    user_id = message.chat.id
    with queue_lock:
        queue = song_queues[user_id]
    if queue:
        text = "📝 သင့် queue မှာရှိတဲ့သီချင်းများ:\n"
        for i, (url, title) in enumerate(queue,1):
            text += f"{i}. {title}\n"
    else:
        text = "✅ သင့် queue လတ်တလောအချိန်တွင် ဘာမှမရှိပါ"
    bot.reply_to(message, text)

# ===== /start Command =====
START_MESSAGE = """ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵

တစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်ကတော့အောက်ကခလုတ်တွေပါ ❤️

သာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘"""

@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        telebot.types.InlineKeyboardButton("🎵 MV Channel", url="https://t.me/+CziNFfkLJSRjNjBl")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💬 Main Chat", url="https://t.me/+RqYCRdFavhM0NTc1"),
        telebot.types.InlineKeyboardButton("💭 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🌐 Join All Groups", url="https://t.me/addlist/T_JawSxSbmA3ZTRl")
    )
    bot.send_message(message.chat.id, START_MESSAGE, reply_markup=markup, disable_web_page_preview=True)

# ===== /about Command =====
ABOUT_MESSAGE = "ကြော်ငြာကိစ္စများအတွက်ဆက်သွယ်ရန် 👇 @twentyfour7ithinkingaboutyou"

@bot.message_handler(commands=['about'])
def handle_about(message):
    bot.send_message(message.chat.id, ABOUT_MESSAGE)

# ===== Webhook =====
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        if json_str:
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
    except Exception:
        pass
    return "!",200

# ===== Health Check =====
@app.route("/")
def index():
    return "✅ Bot is running!"

# ===== Run App =====
if __name__=="__main__":
    PORT = int(os.environ.get("PORT",8080))
    setup_webhook()
    app.run(host="0.0.0.0", port=PORT)
