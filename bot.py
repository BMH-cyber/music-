import os
import sys
import telebot
import threading
import time
from dotenv import load_dotenv
import subprocess

# ===== Kill previous Telebot processes =====
try:
    subprocess.run(["pkill", "-f", "telebot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("🧹 Old telebot instances killed successfully.")
except Exception as e:
    print(f"⚠️ Could not kill old processes: {e}")

# ===== Load Config =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found in .env file!")
    sys.exit()

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ===== Start message =====
START_MESSAGE = """ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵

တစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်ကတော့အောက်ကခလုတ်တွေပါ ❤️

တစ်ခါတည်းဂရုအကုန်ဝင်ချင်တဲ့ညီကိုတွေက‌တော့ “🌐 Join All Groups” ကိုနှိပ်ပါ 👇

သာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘"""

# ===== Threaded send message =====
def send_start_message(message):
    try:
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
        bot.send_message(
            message.chat.id,
            START_MESSAGE,
            reply_markup=markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"❌ Error sending message: {e}")

# ===== /start command =====
@bot.message_handler(commands=['start'])
def handle_start(message):
    threading.Thread(target=send_start_message, args=(message,)).start()

# ===== Prevent Multiple Instances =====
def ensure_single_instance():
    pid_file = "bot.pid"
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            old_pid = f.read().strip()
        if old_pid:
            try:
                os.kill(int(old_pid), 0)
                print("⚠️ Another instance is already running. Exiting...")
                sys.exit()
            except OSError:
                pass
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

# ===== Run Bot =====
if __name__ == "__main__":
    ensure_single_instance()
    print("✅ Bot is running...")
    while True:
        try:
            bot.polling(non_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"❌ Polling error: {e}")
            time.sleep(5)
