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
                is_active BOOLEAN DEFAULT 1,
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
            """,
            
            # Индексы
            """
            CREATE INDEX IF NOT EXISTS idx_availability_date ON availability(date)
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
    
    # Парковочные места
    def add_parking_spot(self, owner_id, spot_number, price_per_hour, price_per_day):
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
    
    def update_parking_spot(self, spot_id, spot_number=None, price_per_hour=None, price_per_day=None, is_active=None):
        """Обновление парковочного места"""
        try:
            cursor = self.connection.cursor()
            updates = []
            params = []
            
            if spot_number is not None:
                updates.append("spot_number = ?")
                params.append(spot_number)
            if price_per_hour is not None:
                updates.append("price_per_hour = ?")
                params.append(price_per_hour)
            if price_per_day is not None:
                updates.append("price_per_day = ?")
                params.append(price_per_day)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(is_active)
            
            if not updates:
                return False
            
            params.append(spot_id)
            query = f"UPDATE parking_spots SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ Ошибка обновления парковочного места: {e}")
            return False
    
    def delete_parking_spot(self, spot_id):
        """Удаление парковочного места"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM parking_spots WHERE id = ?", (spot_id,))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ Ошибка удаления парковочного места: {e}")
            return False
    
    def get_parking_spot(self, spot_id):
        """Получение парковочного места по ID"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, u.username, u.first_name, u.phone
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ps.id = ?
            """, (spot_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения парковочного места: {e}")
            return None
    
    # Доступность
    def add_availability(self, spot_id, date, start_time, end_time):
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
    
    def get_available_dates_for_spot(self, spot_id, start_date=None, end_date=None):
        """Получение всех дат с доступностью для места"""
        try:
            cursor = self.connection.cursor()
            query = "SELECT DISTINCT date FROM availability WHERE spot_id = ? AND is_available = 1"
            params = [spot_id]
            
            if start_date and end_date:
                query += " AND date BETWEEN ? AND ?"
                params.extend([start_date, end_date])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [row['date'] for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения доступных дат: {e}")
            return []
    
    # Бронирования
    def create_booking(self, user_id, spot_id, date, start_time, end_time, total_price):
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
    
    def update_booking(self, booking_id, status=None, date=None, start_time=None, end_time=None, total_price=None):
        """Обновление бронирования"""
        try:
            cursor = self.connection.cursor()
            updates = []
            params = []
            
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if date is not None:
                updates.append("date = ?")
                params.append(date)
            if start_time is not None:
                updates.append("start_time = ?")
                params.append(start_time)
            if end_time is not None:
                updates.append("end_time = ?")
                params.append(end_time)
            if total_price is not None:
                updates.append("total_price = ?")
                params.append(total_price)
            
            if not updates:
                return False
            
            params.append(booking_id)
            query = f"UPDATE bookings SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ Ошибка обновления бронирования: {e}")
            return False
    
    def cancel_booking(self, booking_id):
        """Отмена бронирования"""
        try:
            # Получаем данные брони
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT spot_id, date, start_time, end_time 
                FROM bookings WHERE id = ? AND status != 'cancelled'
            """, (booking_id,))
            booking = cursor.fetchone()
            
            if not booking:
                return False
            
            # Обновляем статус брони
            cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
            
            # Освобождаем место
            cursor.execute("""
                UPDATE availability SET is_available = 1
                WHERE spot_id = ? AND date = ?
                AND start_time <= ? AND end_time >= ?
            """, (booking['spot_id'], booking['date'], booking['start_time'], booking['end_time']))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отмены бронирования: {e}")
            self.connection.rollback()
            return False
    
    def get_booking(self, booking_id):
        """Получение бронирования по ID"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, ps.spot_number, ps.price_per_hour, ps.price_per_day,
                       u.username as user_username, u.first_name as user_name, u.phone as user_phone,
                       owner.username as owner_username, owner.first_name as owner_name
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON b.user_id = u.user_id
                JOIN users owner ON ps.owner_id = owner.user_id
                WHERE b.id = ?
            """, (booking_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения бронирования: {e}")
            return None
    
    # Поиск доступных мест
    def get_available_spots(self, date):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, a.date, a.start_time, a.end_time,
                       u.username, u.first_name, u.phone
                FROM parking_spots ps
                JOIN availability a ON ps.id = a.spot_id
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE a.date = ? AND a.is_available = 1 AND ps.is_active = 1
                ORDER BY ps.spot_number
            """, (date,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения доступных мест: {e}")
            return []
    
    # Получение данных пользователя
    def get_user_spots(self, owner_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, 
                       COUNT(DISTINCT a.id) as total_days,
                       COUNT(DISTINCT b.id) as total_bookings,
                       SUM(CASE WHEN b.status = 'confirmed' THEN b.total_price ELSE 0 END) as total_income
                FROM parking_spots ps
                LEFT JOIN availability a ON ps.id = a.spot_id
                LEFT JOIN bookings b ON ps.id = b.spot_id
                WHERE ps.owner_id = ?
                GROUP BY ps.id
                ORDER BY ps.created_at DESC
            """, (owner_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения мест пользователя: {e}")
            return []
    
    def get_user_bookings(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, ps.spot_number, ps.price_per_hour, ps.price_per_day,
                       u.username as owner_username, u.first_name as owner_name
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON ps.owner_id = u.user_id
                WHERE b.user_id = ?
                ORDER BY b.date DESC, b.start_time DESC
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения бронирований: {e}")
            return []
    
    # Админские функции
    def set_admin(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка назначения администратора: {e}")
            return False
    
    def is_admin(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return bool(result['is_admin']) if result else False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки администратора: {e}")
            return False
    
    def get_all_users(self):
        """Получение всех пользователей"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT u.*, 
                       COUNT(DISTINCT ps.id) as total_spots,
                       COUNT(DISTINCT b.id) as total_bookings,
                       COUNT(DISTINCT b2.id) as active_bookings
                FROM users u
                LEFT JOIN parking_spots ps ON u.user_id = ps.owner_id
                LEFT JOIN bookings b ON u.user_id = b.user_id
                LEFT JOIN bookings b2 ON u.user_id = b2.user_id AND b2.status = 'pending'
                GROUP BY u.user_id
                ORDER BY u.registered_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения всех пользователей: {e}")
            return []
    
    def get_all_spots(self):
        """Получение всех парковочных мест"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, 
                       u.username, u.first_name, u.phone,
                       COUNT(DISTINCT a.id) as total_availability,
                       COUNT(DISTINCT b.id) as total_bookings,
                       SUM(CASE WHEN b.status = 'confirmed' THEN b.total_price ELSE 0 END) as total_income
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                LEFT JOIN availability a ON ps.id = a.spot_id
                LEFT JOIN bookings b ON ps.id = b.spot_id
                GROUP BY ps.id
                ORDER BY ps.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения всех мест: {e}")
            return []
    
    def get_all_bookings(self, limit=50):
        """Получение всех бронирований"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, 
                       ps.spot_number, ps.price_per_hour, ps.price_per_day,
                       u.username as user_username, u.first_name as user_name, u.phone as user_phone,
                       owner.username as owner_username, owner.first_name as owner_name
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON b.user_id = u.user_id
                JOIN users owner ON ps.owner_id = owner.user_id
                ORDER BY b.booked_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка получения всех бронирований: {e}")
            return []
    
    def get_statistics(self):
        """Получение статистики"""
        try:
            cursor = self.connection.cursor()
            
            stats = {}
            
            # Общая статистика
            cursor.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM parking_spots WHERE is_active = 1")
            stats['active_spots'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM bookings")
            stats['total_bookings'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'pending'")
            stats['pending_bookings'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT SUM(total_price) as total FROM bookings WHERE status = 'confirmed'")
            stats['total_income'] = cursor.fetchone()['total'] or 0
            
            # Статистика по дням (последние 7 дней)
            cursor.execute("""
                SELECT date, COUNT(*) as bookings, SUM(total_price) as income
                FROM bookings 
                WHERE date >= date('now', '-7 days')
                GROUP BY date
                ORDER BY date DESC
            """)
            stats['last_7_days'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}
    
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
