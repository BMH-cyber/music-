# ===== Create bot.py =====
cat <<'EOL' > bot.py
import os
import telebot
from flask import Flask, request
import requests
import yt_dlp
import traceback

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("❌ BOT_TOKEN or WEBHOOK_URL missing in environment variables!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===== Webhook setup =====
def setup_webhook():
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    except Exception as e:
        print("Webhook setup failed:", e)

# ===== Common Buttons =====
def common_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("🎬 Main Channel", url="https://t.me/+FS5GVrQz-9xjMWNl"),
        telebot.types.InlineKeyboardButton("🎵 MV Channel", url="https://t.me/+CziNFfkLJSRjNjBl")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💬 Main Chat", url="https://t.me/+RqYCRdFavhM0NTc1"),
        telebot.types.InlineKeyboardButton("💭 Chat Group 2", url="https://t.me/+qOU88Pm12pMzZGM1")
    )
    return markup

# ===== Handlers =====
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = common_markup()
    markup.add(telebot.types.InlineKeyboardButton("🌐 Join All Groups", url="https://t.me/addlist/T_JawSxSbmA3ZTRl"))
    bot.send_message(
        message.chat.id,
        "ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵\n\nအောက်ကခလုတ်တွေကို နှိပ်ပြီး ဝင်နိုင်ပါတယ် ❤️",
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['help'])
def help_handler(message):
    markup = common_markup()
    bot.send_message(
        message.chat.id,
        "/start - စတင်ရန်\n/help - အသုံးပြုပုံ\n/about - ကြော်ငြာဆက်သွယ်ရန်\n/download <YouTube URL> - MP3 Download",
        reply_markup=markup
    )

@bot.message_handler(commands=['about'])
def about_handler(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📩 Contact Now", url="https://t.me/twentyfour7ithinkingaboutyou"))
    bot.send_message(
        message.chat.id,
        "📢 ကြော်ငြာအကြောင်း ဆက်သွယ်ရန်\n👇 @twentyfour7ithinkingaboutyou",
        reply_markup=markup
    )

# ===== Download Command =====
@bot.message_handler(commands=['download'])
def download_handler(message):
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "❌ Please provide YouTube URL.\nUsage: /download <URL>")
            return
        url = args[1]
        bot.reply_to(message, "⬇️ Downloading MP3...")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
        with open(file_path, 'rb') as f:
            bot.send_audio(message.chat.id, f, title=info.get('title'))
    except Exception as e:
        traceback.print_exc()
        bot.reply_to(message, f"❌ Error: {e}")

# ===== Webhook route =====
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        if json_str:
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
    except Exception:
        pass
    return "!", 200

# ===== Health check =====
@app.route("/")
def index():
    return "✅ Bot is running!"

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    setup_webhook()
    app.run(host="0.0.0.0", port=PORT)
EOL

# ===== Run with Gunicorn =====
gunicorn bot:app -b 0.0.0.0:$PORT
