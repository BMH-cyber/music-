import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import telebot
from pytube import YouTube
from youtubesearchpython import VideosSearch

# ====== Bot Setup ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN မထည့်ထားပါ")

bot = telebot.TeleBot(BOT_TOKEN)
executor = ThreadPoolExecutor(max_workers=3)

# ====== Start Command ======
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "မင်္ဂလာပါ! သီချင်းနာမည်ရိုက်ပြီး ပို့ပါ။")

# ====== Download & Send Audio ======
def download_and_send(message, query):
    status_msg = bot.send_message(message.chat.id, f"'{query}' သီချင်း download လုပ်နေပါသည်...")

    try:
        video = VideosSearch(query, limit=1).result()['result'][0]
        url = video['link']
        yt = YouTube(url)

        # Audio-only 128kbps
        audio_stream = yt.streams.filter(only_audio=True, abr="128kbps").first()
        audio_file = BytesIO()
        audio_stream.stream_to_buffer(audio_file)
        audio_file.seek(0)

        bot.send_audio(message.chat.id, audio_file, title=yt.title)
        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=status_msg.message_id,
                              text=f"သီချင်းရှာမတွေ့ပါ: {str(e)}")

# ====== Message Handler ======
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    query = message.text
    executor.submit(download_and_send, message, query)

# ====== Start Bot ======
bot.infinity_polling()
