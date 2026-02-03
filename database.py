import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.connection = None
        self.db_path = self.get_db_path()
        self.connect()
        self.create_tables()
    
    def get_db_path(self):
        """Определяем путь к базе данных в папке /data для BotHost"""
        data_dir = Path("/data")
        if data_dir.exists() and data_dir.is_dir():
            db_path = data_dir / "parking_bot.db"
            logger.info(f"✅ Используем папку /data для базы данных: {db_path}")
            return str(db_path)
        else:
            db_path = Path(".") / "data" / "parking_bot.db"
            db_path.parent.mkdir(exist_ok=True)
            logger.info(f"📁 Используем локальную папку data: {db_path}")
            return str(db_path)
    
    def connect(self):
        """Подключение к SQLite базе данных"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"✅ Подключение к SQLite базе установлено")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к SQLite: {e}")
            return False
    
    def create_tables(self):
        """Создание таблиц в базе данных"""
        queries = [
            # Таблица пользователей
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                is_admin BOOLEAN DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # Таблица парковочных мест
            """
            CREATE TABLE IF NOT EXISTS parking_spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                spot_number TEXT NOT NULL,
                price_per_hour REAL NOT NULL,
                price_per_day REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Таблица доступности мест
            """
            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_id INTEGER NOT NULL,
                date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                is_available BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id) ON DELETE CASCADE
            )
            """,
            
            # Таблица бронирований
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                spot_id INTEGER NOT NULL,
                date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                total_price REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id)
            )
            """
        ]
        
        try:
            cursor = self.connection.cursor()
            for query in queries:
                cursor.execute(query)
            self.connection.commit()
            logger.info("✅ Таблицы SQLite успешно созданы!")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при создании таблиц: {e}")
            return False
    
    def add_user(self, user_id, username, first_name, phone):
        """Добавление или обновление пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name, phone) 
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, phone))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")
            return False
    
    def add_parking_spot(self, owner_id, spot_number, price_per_hour, price_per_day):
        """Добавление парковочного места"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO parking_spots (owner_id, spot_number, price_per_hour, price_per_day)
                VALUES (?, ?, ?, ?)
            """, (owner_id, spot_number, price_per_hour, price_per_day))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"❌ Ошибка добавления парковочного места: {e}")
            return None
    
    def add_availability(self, spot_id, date, start_time, end_time):
        """Добавление доступности места"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO availability (spot_id, date, start_time, end_time)
                VALUES (?, ?, ?, ?)
            """, (spot_id, date, start_time, end_time))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления доступности: {e}")
            return False
    
    def get_available_spots(self, date):
        """Получение доступных мест на дату"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, a.date, a.start_time, a.end_time
                FROM parking_spots ps
                JOIN availability a ON ps.id = a.spot_id
                WHERE a.date = ? AND a.is_available = 1
            """, (date,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения доступных мест: {e}")
            return []
    
    def create_booking(self, user_id, spot_id, date, start_time, end_time, total_price):
        """Создание бронирования"""
        try:
            cursor = self.connection.cursor()
            
            # Проверка доступности
            cursor.execute("""
                SELECT id FROM availability 
                WHERE spot_id = ? AND date = ? 
                AND start_time <= ? AND end_time >= ?
                AND is_available = 1
            """, (spot_id, date, start_time, end_time))
            
            if not cursor.fetchone():
                return None
            
            # Создание брони
            cursor.execute("""
                INSERT INTO bookings (user_id, spot_id, date, start_time, end_time, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, spot_id, date, start_time, end_time, total_price))
            
            booking_id = cursor.lastrowid
            
            # Обновление доступности
            cursor.execute("""
                UPDATE availability SET is_available = 0
                WHERE spot_id = ? AND date = ?
                AND start_time <= ? AND end_time >= ?
            """, (spot_id, date, start_time, end_time))
            
            self.connection.commit()
            return booking_id
        except Exception as e:
            logger.error(f"❌ Ошибка создания бронирования: {e}")
            self.connection.rollback()
            return None
    
    def get_user_spots(self, owner_id):
        """Получение мест пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, 
                       (SELECT COUNT(*) FROM availability a WHERE a.spot_id = ps.id) as total_days,
                       (SELECT COUNT(*) FROM bookings b WHERE b.spot_id = ps.id AND b.status = 'confirmed') as total_bookings
                FROM parking_spots ps
                WHERE ps.owner_id = ?
            """, (owner_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения мест пользователя: {e}")
            return []
    
    def get_user_bookings(self, user_id):
        """Получение бронирований пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, ps.spot_number, ps.price_per_hour, ps.price_per_day
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                WHERE b.user_id = ?
                ORDER BY b.date DESC, b.start_time DESC
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения бронирований: {e}")
            return []
    
    def set_admin(self, user_id):
        """Назначение администратора"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка назначения администратора: {e}")
            return False
    
    def is_admin(self, user_id):
        """Проверка является ли пользователь администратором"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return bool(result['is_admin']) if result else False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки администратора: {e}")
            return False
    
    def check_user_exists(self, user_id):
        """Проверка существования пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки пользователя: {e}")
            return False
    
    def close(self):
        """Закрытие соединения с БД"""
        if self.connection:
            self.connection.close()
