# Telegram Music Bot (Burmese Search)

- Telegram bot with `/play <song>` command
- Uses `yt-dlp` to search YouTube songs
- Unicode Burmese song search supported
- 24/7 running on Railway using Flask keep-alive

## Deployment

1. Copy `.env.example` to `.env` and fill your TOKEN and ADMIN_ID
2. Install dependencies: `pip install -r requirements.txt`
3. Start bot: `python bot.py`
4. On Railway: set Start Command to `python bot.py`
