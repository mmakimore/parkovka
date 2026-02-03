import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.connection = None
        self.db_path = self.get_db_path()
        self.connect()
        self.create_tables()
    
    def get_db_path(self):
        data_dir = Path("/data")
        if data_dir.exists() and data_dir.is_dir():
            db_path = data_dir / "parking_bot.db"
            return str(db_path)
        else:
            db_path = Path(".") / "data" / "parking_bot.db"
            db_path.parent.mkdir(exist_ok=True)
            return str(db_path)
    
    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    
    def create_tables(self):
        queries = [
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
            return True
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            return False
    
    def add_user(self, user_id, username, first_name, phone):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name, phone) 
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, phone))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    def check_user_exists(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки пользователя: {e}")
            return False
    
    def is_admin(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return bool(result['is_admin']) if result else False
        except Exception as e:
            logger.error(f"Ошибка проверки администратора: {e}")
            return False
    
    def set_admin(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка назначения администратора: {e}")
            return False
    
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
            logger.error(f"Ошибка добавления парковочного места: {e}")
            return None
    
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
            logger.error(f"Ошибка добавления доступности: {e}")
            return False
    
    def get_available_spots(self, date):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, a.date, a.start_time, a.end_time,
                       u.username, u.first_name
                FROM parking_spots ps
                JOIN availability a ON ps.id = a.spot_id
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE a.date = ? AND a.is_available = 1 AND ps.is_active = 1
                ORDER BY ps.spot_number
            """, (date,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения доступных мест: {e}")
            return []
    
    def create_booking(self, user_id, spot_id, date, start_time, end_time, total_price):
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                SELECT id FROM availability 
                WHERE spot_id = ? AND date = ? 
                AND start_time <= ? AND end_time >= ?
                AND is_available = 1
            """, (spot_id, date, start_time, end_time))
            
            if not cursor.fetchone():
                return None
            
            cursor.execute("""
                INSERT INTO bookings (user_id, spot_id, date, start_time, end_time, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, spot_id, date, start_time, end_time, total_price))
            
            booking_id = cursor.lastrowid
            
            cursor.execute("""
                UPDATE availability SET is_available = 0
                WHERE spot_id = ? AND date = ?
                AND start_time <= ? AND end_time >= ?
            """, (spot_id, date, start_time, end_time))
            
            self.connection.commit()
            return booking_id
        except Exception as e:
            logger.error(f"Ошибка создания бронирования: {e}")
            self.connection.rollback()
            return None
    
    def get_user_spots(self, owner_id):
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
            logger.error(f"Ошибка получения мест пользователя: {e}")
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
            logger.error(f"Ошибка получения бронирований: {e}")
            return []
    
    def get_all_users(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT u.*, 
                       COUNT(DISTINCT ps.id) as total_spots,
                       COUNT(DISTINCT b.id) as total_bookings
                FROM users u
                LEFT JOIN parking_spots ps ON u.user_id = ps.owner_id
                LEFT JOIN bookings b ON u.user_id = b.user_id
                GROUP BY u.user_id
                ORDER BY u.registered_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
    def get_all_spots(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, 
                       u.username, u.first_name, u.phone,
                       COUNT(DISTINCT a.id) as total_availability,
                       COUNT(DISTINCT b.id) as total_bookings
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
            logger.error(f"Ошибка получения всех мест: {e}")
            return []
    
    def get_all_bookings(self, limit=30):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, 
                       ps.spot_number,
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
            logger.error(f"Ошибка получения всех бронирований: {e}")
            return []
    
    def get_statistics(self):
        try:
            cursor = self.connection.cursor()
            stats = {}
            
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
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    def close(self):
        if self.connection:
            self.connection.close()
