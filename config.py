import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8552794244:AAEEMnwCkRmNWV8hC_wyU26B-0OUheHFZjc")
BOT_NAME = os.getenv("BOT_NAME", "riddle_bbe_bot")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

