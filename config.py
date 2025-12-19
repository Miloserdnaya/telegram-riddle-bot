import os
from dotenv import load_dotenv

# Загружаем .env только если файл существует (для локальной разработки)
# На Railway переменные окружения доступны напрямую
if os.path.exists(".env"):
    load_dotenv()

# BOT_TOKEN должен быть установлен как переменная окружения на Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set! Please set it in Railway Variables.")
BOT_NAME = os.getenv("BOT_NAME", "riddle_bbe_bot")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

