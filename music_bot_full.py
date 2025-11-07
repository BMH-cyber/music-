import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from youtubesearchpython import VideosSearch
import youtube_dl
import tempfile
from collections import defaultdict

# Load .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Queue per chat
queues = defaultdict(list)           # {chat_id: [video_url, ...]}
currently_playing = {}               # {chat_id: video_url}

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🎵 Welcome to Music Bot with Playlist & Controls!\nType /song <song name> to search music.")

# Song search command
@bot.message_handler(commands=['song'])
def get_song(message):
    try:
        query = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Please provide a song name.\nUsage: /song <song name>")
        return

    bot.reply_to(message, f"🔍 Searching '{query}' on YouTube...")

    videos_search = VideosSearch(query, limit=5)
    results = videos_search.result()['result']

    if not results:
        bot.reply_to(message, "❌ Song not found.")
        return

    for video in results:
        video_url = video['link']
        title = video['title']
        thumbnail = video['thumbnails'][0]['url']

        buttons = InlineKeyboardMarkup()
        buttons.row(
            InlineKeyboardButton("▶️ Play", callback_data=f"play|{video_url}"),
            InlineKeyboardButton("⏭ Skip", callback_data="skip"),
            InlineKeyboardButton("📃 Queue", callback_data="queue"),
            InlineKeyboardButton("🗑 Clear", callback_data="clear"),
            InlineKeyboardButton("🔗 Open", url=video_url)
        )

        bot.send_photo(
            message.chat.id,
            thumbnail,
            caption=f"🎶 {title}",
            reply_markup=buttons
        )

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    data = call.data

    if data.startswith("play|"):
        video_url = data.split("|", 1)[1]
        queues[chat_id].append(video_url)
        bot.answer_callback_query(call.id, "Added to queue 🎵")
        if chat_id not in currently_playing:
            play_next(chat_id)

    elif data == "skip":
        if queues[chat_id]:
            bot.answer_callback_query(call.id, "⏭ Skipping current song")
            currently_playing.pop(chat_id, None)
            play_next(chat_id)
        else:
            bot.answer_callback_query(call.id, "Queue is empty ❌")

    elif data == "queue":
        if queues[chat_id]:
            text = "\n".join([f"{i+1}. {v}" for i, v in enumerate(queues[chat_id])])
        else:
            text = "Queue is empty."
        bot.answer_callback_query(call.id, text, show_alert=True)

    elif data == "clear":
        queues[chat_id].clear()
        currently_playing.pop(chat_id, None)
        bot.answer_callback_query(call.id, "🗑 Queue cleared")

# Play next song function
def play_next(chat_id):
    if not queues[chat_id]:
        currently_playing.pop(chat_id, None)
        bot.send_message(chat_id, "✅ Playlist finished!")
        return

    video_url = queues[chat_id][0]
    currently_playing[chat_id] = video_url
    bot.send_message(chat_id, "⬇️ Downloading audio...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')

    with open(filename, 'rb') as f:
        bot.send_audio(chat_id, f, title=info['title'])

    os.remove(filename)
    queues[chat_id].pop(0)
    currently_playing.pop(chat_id, None)

    if queues[chat_id]:
        play_next(chat_id)

print("✅ Full-feature Music Bot running...")
bot.infinity_polling()
