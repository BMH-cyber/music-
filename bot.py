import os
import sys
import telebot
import threading
import time
from dotenv import load_dotenv
from flask import Flask
import subprocess

# ===== Kill previous Telebot processes (local only) =====
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

# ===== Flask App (for Railway) =====
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running successfully on Railway!"

# ===== /start =====
@bot.message_handler(commands=['start'])
def handle_start(message):
    def send_start():
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
                """ညီကိုတို့အတွက် အပန်းဖြေရာ 🥵

တစ်ခုချင်းဝင်ချင်တဲ့ညီကိုတွေအတွက်ကတော့အောက်ကခလုတ်တွေပါ ❤️

တစ်ခါတည်းဂရုအကုန်ဝင်ချင်တဲ့ညီကိုတွေက‌တော့ “🌐 Join All Groups” ကိုနှိပ်ပါ 👇

သာယာသောနေ့လေးဖြစ်ပါစေညိုကီတို့ 😘""",
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"❌ Error sending /start message: {e}")

    threading.Thread(target=send_start).start()

# ===== /help =====
@bot.message_handler(commands=['help'])
def handle_help(message):
    def send_help():
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
            bot.send_message(
                message.chat.id,
                """🆘 <b>အသုံးပြုပုံ</b>

/start - ညီကိုတို့အတွက် အပန်းဖြေရာ စတင်ရန်  
/help - အသုံးပြုပုံလမ်းညွှန် ကြည့်ရန်  
/about - ကြော်ငြာအကြောင်းဆက်သွယ်ရန်  

မေးချင်တာရှိရင် Main Chat မှာ မေးလို့ရပါတယ် 💬""",
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"❌ Error sending /help message: {e}")

    threading.Thread(target=send_help).start()

# ===== /about =====
@bot.message_handler(commands=['about'])
def handle_about(message):
    def send_about():
        try:
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton(
                    "📩 Contact Now", url="https://t.me/twentyfour7ithinkingaboutyou"
                )
            )
            bot.send_message(
                message.chat.id,
                """📢 <b>ကြော်ငြာကိစ္စများအတွက် ဆက်သွယ်ရန်</b>

👇 @twentyfour7ithinkingaboutyou""",
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"❌ Error sending /about message: {e}")

    threading.Thread(target=send_about).start()

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

# ===== Polling Thread =====
def run_bot():
    print("✅ Bot polling started...")
    while True:
        try:
            bot.polling(non_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"❌ Polling error: {e}")
            time.sleep(5)

# ===== Run Flask + Bot =====
if __name__ == "__main__":
    ensure_single_instance()

    # Bot background thread
    threading.Thread(target=run_bot).start()

    # Flask server for Railway
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Flask web server running on port {port} ...")
    app.run(host="0.0.0.0", port=port)
