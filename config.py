import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Токен бота
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8569990381:AAG9wr0L9g5pUn9bp1H2wwfDZju3vIuVOBI")
    
    # ID администратора
    ADMIN_ID = int(os.getenv("ADMIN_ID", 7884533080))
    
    # Настройки базы данных
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/parking_bot.db")
    
    # Настройки времени
    TIMEZONE = "Europe/Moscow"
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    DATE_FORMAT = "%d.%m.%Y"
    
    # Лимиты
    MAX_SPOTS_PER_USER = 10
    MIN_BOOKING_HOURS = 1
    MAX_BOOKING_DAYS = 30
    AUTO_CANCEL_HOURS = 24
    
    # Комиссия системы (%)
    COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", 0))
    
    # Настройки уведомлений
    ENABLE_EMAIL_NOTIFICATIONS = False
    ENABLE_SMS_NOTIFICATIONS = False
    
    # Пути к файлам
    LOGS_DIR = "logs"
    BACKUP_DIR = "backups"
    
    # Режим отладки
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

config = Config()