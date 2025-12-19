"""
Интеграция с Google Sheets для записи выданных грантов
"""
import os
import logging

logger = logging.getLogger(__name__)

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    logger.warning("gspread не установлен. Google Sheets интеграция будет отключена.")

# Настройки Google Sheets
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ID таблицы Google Sheets (будет создана или указана пользователем)
# Можно задать через переменную окружения или использовать config
try:
    import config
    SPREADSHEET_ID = config.GOOGLE_SHEET_ID
    CREDENTIALS_FILE = config.GOOGLE_CREDENTIALS_FILE
except:
    SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
    CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Название листа в таблице
SHEET_NAME = "Гранты"


def get_google_sheets_client():
    """Получить клиент Google Sheets"""
    if not GSPREAD_AVAILABLE:
        return None
    
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            logger.warning(f"Файл {CREDENTIALS_FILE} не найден. Google Sheets интеграция отключена.")
            return None
        
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Ошибка при подключении к Google Sheets: {e}")
        return None


async def add_grant_to_sheet(user_id: int, username: str, first_name: str, promo_code: str, grant_amount: int = 30000):
    """Добавить запись о гранте в Google Sheets"""
    if not GSPREAD_AVAILABLE:
        logger.warning("gspread не установлен. Google Sheets интеграция отключена.")
        return False
    
    try:
        client = get_google_sheets_client()
        if not client:
            logger.warning("Google Sheets клиент недоступен, пропускаем запись")
            return False
        
        if not SPREADSHEET_ID:
            logger.warning("SPREADSHEET_ID не указан, пропускаем запись")
            return False
        
        # Открываем таблицу
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        
        # Получаем или создаем лист
        try:
            worksheet = spreadsheet.worksheet(SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=10)
            # Добавляем заголовки
            worksheet.append_row([
                "Дата выдачи",
                "User ID",
                "Имя пользователя",
                "Имя",
                "Промокод",
                "Сумма гранта (руб)"
            ])
        
        # Добавляем запись
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        worksheet.append_row([
            current_date,
            user_id,
            username or "",
            first_name or "",
            promo_code,
            grant_amount
        ])
        
        logger.info(f"Грант {promo_code} записан в Google Sheets для пользователя {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при записи в Google Sheets: {e}", exc_info=True)
        return False


def create_sample_credentials_template():
    """Создать шаблон файла credentials.json"""
    template = {
        "type": "service_account",
        "project_id": "your-project-id",
        "private_key_id": "your-private-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
        "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
        "client_id": "your-client-id",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com"
    }
    
    import json
    with open("credentials_template.json", "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    logger.info("Создан шаблон credentials_template.json. Заполните его своими данными и переименуйте в credentials.json")

