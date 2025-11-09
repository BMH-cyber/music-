import os
import telebot
from io import BytesIO
from pytube import YouTube
from youtubesearchpython import VideosSearch

BOT_TOKEN = os.getenv("BOT_TOKEN")  # .env မှာ BOT_TOKEN သိမ်းထားရမယ်
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "မင်္ဂလာပါ! သီချင်းနာမည်ရိုက်ပြီး ပို့ပါ။")

@bot.message_handler(func=lambda m: True)
def send_music(message):
    query = message.text
    status_msg = bot.send_message(message.chat.id, f"'{query}' သီချင်း download လုပ်နေပါသည်...")

    try:
        video = VideosSearch(query, limit=1).result()['result'][0]
        url = video['link']
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        audio_file = BytesIO()
        audio_stream.stream_to_buffer(audio_file)
        audio_file.seek(0)

        bot.send_audio(message.chat.id, audio_file, title=yt.title)
        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(chat_id=message.chat.id, message_id=status_msg.message_id,
                              text=f"သီချင်းရှာမတွေ့ပါ: {str(e)}")

bot.infinity_polling()
