import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

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
                UNIQUE(owner_id, spot_number),
                FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS availability_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_id INTEGER NOT NULL,
                start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL,
                is_booked BOOLEAN DEFAULT 0,
                booked_by INTEGER,
                booked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id) ON DELETE CASCADE,
                FOREIGN KEY (booked_by) REFERENCES users(user_id),
                CHECK (end_datetime > start_datetime)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                spot_id INTEGER NOT NULL,
                period_id INTEGER,
                start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL,
                total_price REAL NOT NULL,
                status TEXT DEFAULT 'active',
                payment_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id),
                FOREIGN KEY (period_id) REFERENCES availability_periods(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS availability_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                spot_id INTEGER,
                start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS free_slots_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spot_id INTEGER NOT NULL,
                start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(spot_id, start_datetime, end_datetime),
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id)
            )
            """
        ]
        
        try:
            cursor = self.connection.cursor()
            for query in queries:
                cursor.execute(query)
            
            # Создание индексов для ускорения запросов
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_periods_datetime 
                ON availability_periods(start_datetime, end_datetime, is_booked)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_periods_spot 
                ON availability_periods(spot_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bookings_user 
                ON bookings(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bookings_datetime 
                ON bookings(start_datetime, end_datetime)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_spots_owner 
                ON parking_spots(owner_id, is_active)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_availability_notifications 
                ON availability_notifications(user_id, is_active)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_free_slots_cache 
                ON free_slots_cache(spot_id, start_datetime)
            """)
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            return False
    
    # ============ USER METHODS ============
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
    
    def get_user(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
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
    
    # ============ PARKING SPOT METHODS ============
    def add_parking_spot(self, owner_id, spot_number, price_per_hour, price_per_day):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO parking_spots (owner_id, spot_number, price_per_hour, price_per_day)
                VALUES (?, ?, ?, ?)
            """, (owner_id, spot_number, price_per_hour, price_per_day))
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        except Exception as e:
            logger.error(f"Ошибка добавления парковочного места: {e}")
            return None
    
    def get_parking_spot(self, spot_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, u.username, u.first_name, u.phone
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ps.id = ?
            """, (spot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения места: {e}")
            return None
    
    def get_user_spots(self, owner_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, 
                       COUNT(DISTINCT ap.id) as total_periods,
                       SUM(CASE WHEN ap.is_booked = 1 THEN 1 ELSE 0 END) as booked_periods,
                       (SELECT COUNT(*) FROM bookings b 
                        WHERE b.spot_id = ps.id AND b.status = 'active') as active_bookings
                FROM parking_spots ps
                LEFT JOIN availability_periods ap ON ps.id = ap.spot_id
                WHERE ps.owner_id = ? AND ps.is_active = 1
                GROUP BY ps.id
                ORDER BY ps.spot_number
            """, (owner_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения мест пользователя: {e}")
            return []
    
    def get_all_active_spots(self):
        """Получает все активные места с информацией о владельцах"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, u.username, u.first_name, u.phone
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ps.is_active = 1
                ORDER BY ps.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех активных мест: {e}")
            return []
    
    # ============ AVAILABILITY PERIODS METHODS ============
    def add_availability_period(self, spot_id, start_datetime, end_datetime):
        """Добавляет период доступности"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO availability_periods (spot_id, start_datetime, end_datetime)
                VALUES (?, ?, ?)
            """, (spot_id, start_datetime, end_datetime))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления периода доступности: {e}")
            return None
    
    def check_period_availability(self, spot_id, start_datetime, end_datetime):
        """Проверяет, свободен ли период"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM availability_periods
                WHERE spot_id = ? 
                  AND is_booked = 0
                  AND NOT (end_datetime <= ? OR start_datetime >= ?)
            """, (spot_id, start_datetime, end_datetime))
            
            result = cursor.fetchone()
            return result['count'] == 0 if result else False
        except Exception as e:
            logger.error(f"Ошибка проверки доступности периода: {e}")
            return False
    
    def get_available_periods_for_spot(self, spot_id, start_date=None, end_date=None):
        """Получает все свободные периоды для места"""
        try:
            cursor = self.connection.cursor()
            
            if start_date and end_date:
                cursor.execute("""
                    SELECT * FROM availability_periods
                    WHERE spot_id = ? 
                      AND is_booked = 0
                      AND NOT (end_datetime <= ? OR start_datetime >= ?)
                    ORDER BY start_datetime
                """, (spot_id, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT * FROM availability_periods
                    WHERE spot_id = ? AND is_booked = 0
                    ORDER BY start_datetime
                """, (spot_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения периодов для места: {e}")
            return []
    
    def get_available_spots_by_date_range(self, start_datetime, end_datetime):
        """Получает все места, доступные в указанный период времени"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT DISTINCT ps.*, u.username, u.first_name,
                       ap.start_datetime, ap.end_datetime
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                LEFT JOIN availability_periods ap ON ps.id = ap.spot_id
                WHERE ps.is_active = 1 
                  AND ap.is_booked = 0
                  AND ap.start_datetime <= ?
                  AND ap.end_datetime >= ?
                GROUP BY ps.id
                ORDER BY ps.spot_number
            """, (end_datetime, start_datetime))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения мест по диапазону дат: {e}")
            return []
    
    def find_available_periods(self, spot_id, start_datetime, end_datetime):
        """Находит подходящие свободные периоды для бронирования"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM availability_periods
                WHERE spot_id = ? 
                  AND is_booked = 0
                  AND start_datetime <= ?
                  AND end_datetime >= ?
                ORDER BY start_datetime
            """, (spot_id, start_datetime, end_datetime))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка поиска периодов: {e}")
            return []
    
    def get_next_available_periods(self, days_ahead=7, limit=20):
        """Получает ближайшие свободные периоды на несколько дней вперед"""
        try:
            cursor = self.connection.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                SELECT ap.*, ps.spot_number, ps.price_per_hour, ps.price_per_day,
                       u.username, u.first_name
                FROM availability_periods ap
                JOIN parking_spots ps ON ap.spot_id = ps.id
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ap.is_booked = 0 
                  AND ap.start_datetime >= ?
                  AND ap.start_datetime <= ?
                  AND ps.is_active = 1
                ORDER BY ap.start_datetime
                LIMIT ?
            """, (now, future_date, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения ближайших периодов: {e}")
            return []
    
    def get_free_periods_by_spot(self, spot_id, days_ahead=7):
        """Получает свободные периоды для конкретного места"""
        try:
            cursor = self.connection.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                SELECT * FROM availability_periods
                WHERE spot_id = ? 
                  AND is_booked = 0
                  AND start_datetime >= ?
                  AND start_datetime <= ?
                ORDER BY start_datetime
            """, (spot_id, now, future_date))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения свободных периодов места: {e}")
            return []
    
    # ============ BOOKING METHODS ============
    def create_booking(self, user_id, spot_id, period_id, start_datetime, end_datetime, total_price):
        """Создает бронирование"""
        try:
            cursor = self.connection.cursor()
            
            # Проверяем, что период все еще свободен
            cursor.execute("""
                SELECT id FROM availability_periods
                WHERE id = ? AND is_booked = 0
            """, (period_id,))
            
            period = cursor.fetchone()
            if not period:
                return None
            
            # Создаем бронирование
            cursor.execute("""
                INSERT INTO bookings (user_id, spot_id, period_id, start_datetime, end_datetime, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, spot_id, period_id, start_datetime, end_datetime, total_price))
            
            booking_id = cursor.lastrowid
            
            # Помечаем период как занятый
            cursor.execute("""
                UPDATE availability_periods 
                SET is_booked = 1, booked_by = ?, booked_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id, period_id))
            
            # Проверяем подписки на уведомления
            cursor.execute("""
                SELECT an.*, u.user_id as subscriber_id
                FROM availability_notifications an
                JOIN users u ON an.user_id = u.user_id
                WHERE an.is_active = 1 
                  AND (
                    (an.spot_id IS NULL AND an.start_datetime <= ? AND an.end_datetime >= ?)
                    OR
                    (an.spot_id = ? AND an.start_datetime <= ? AND an.end_datetime >= ?)
                  )
            """, (end_datetime, start_datetime, spot_id, end_datetime, start_datetime))
            
            notifications = cursor.fetchall()
            
            # Деактивируем найденные подписки
            for notification in notifications:
                cursor.execute("""
                    UPDATE availability_notifications 
                    SET is_active = 0 
                    WHERE id = ?
                """, (notification['id'],))
                
                # Добавляем уведомление пользователю
                spot_info = self.get_parking_spot(spot_id)
                if spot_info:
                    notification_text = (
                        f"🔔 <b>Появилось свободное место!</b>\n\n"
                        f"📍 Место: {spot_info['spot_number']}\n"
                        f"💰 Цена: {spot_info['price_per_hour']} руб./час\n"
                        f"📅 Период: {start_datetime} - {end_datetime}\n\n"
                        f"Скорее бронируйте!"
                    )
                    
                    cursor.execute("""
                        INSERT INTO notifications (user_id, message)
                        VALUES (?, ?)
                    """, (notification['subscriber_id'], notification_text))
            
            self.connection.commit()
            return booking_id
        except Exception as e:
            logger.error(f"Ошибка создания бронирования: {e}")
            self.connection.rollback()
            return None
    
    def get_user_bookings(self, user_id, include_cancelled=False):
        try:
            cursor = self.connection.cursor()
            if include_cancelled:
                cursor.execute("""
                    SELECT b.*, ps.spot_number, ps.price_per_hour, ps.price_per_day,
                           u.username as owner_username, u.first_name as owner_name
                    FROM bookings b
                    JOIN parking_spots ps ON b.spot_id = ps.id
                    JOIN users u ON ps.owner_id = u.user_id
                    WHERE b.user_id = ?
                    ORDER BY b.start_datetime DESC
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT b.*, ps.spot_number, ps.price_per_hour, ps.price_per_day,
                           u.username as owner_username, u.first_name as owner_name
                    FROM bookings b
                    JOIN parking_spots ps ON b.spot_id = ps.id
                    JOIN users u ON ps.owner_id = u.user_id
                    WHERE b.user_id = ? AND b.status = 'active'
                    ORDER BY b.start_datetime DESC
                """, (user_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения бронирований пользователя: {e}")
            return []
    
    def cancel_booking(self, booking_id):
        try:
            cursor = self.connection.cursor()
            
            # Получаем информацию о бронировании
            cursor.execute("""
                SELECT period_id, spot_id, start_datetime, end_datetime 
                FROM bookings WHERE id = ?
            """, (booking_id,))
            booking = cursor.fetchone()
            
            if not booking:
                return False
            
            # Отменяем бронирование
            cursor.execute("""
                UPDATE bookings SET status = 'cancelled' WHERE id = ?
            """, (booking_id,))
            
            # Освобождаем период
            cursor.execute("""
                UPDATE availability_periods 
                SET is_booked = 0, booked_by = NULL, booked_at = NULL
                WHERE id = ?
            """, (booking['period_id'],))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены бронирования: {e}")
            self.connection.rollback()
            return False
    
    # ============ NOTIFICATION METHODS ============
    def add_notification(self, user_id, message):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO notifications (user_id, message)
                VALUES (?, ?)
            """, (user_id, message))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления уведомления: {e}")
            return False
    
    def get_unread_notifications(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY created_at DESC
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения уведомлений: {e}")
            return []
    
    def mark_notifications_as_read(self, user_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE notifications SET is_read = 1
                WHERE user_id = ? AND is_read = 0
            """, (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка пометки уведомлений как прочитанных: {e}")
            return False
    
    # ============ AVAILABILITY NOTIFICATIONS ============
    def add_availability_notification(self, user_id, spot_id, start_datetime, end_datetime):
        """Добавляет подписку на уведомление о свободном месте"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO availability_notifications (user_id, spot_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?)
            """, (user_id, spot_id, start_datetime, end_datetime))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления подписки на уведомление: {e}")
            return None
    
    def get_user_notifications(self, user_id):
        """Получает подписки пользователя на уведомления"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT an.*, ps.spot_number
                FROM availability_notifications an
                LEFT JOIN parking_spots ps ON an.spot_id = ps.id
                WHERE an.user_id = ? AND an.is_active = 1
                ORDER BY an.created_at DESC
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения подписок пользователя: {e}")
            return []
    
    def remove_notification(self, notification_id):
        """Удаляет подписку на уведомление"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                DELETE FROM availability_notifications WHERE id = ?
            """, (notification_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления подписки: {e}")
            return False
    
    # ============ FREE SLOTS CACHE ============
    def cache_free_slots(self, spot_id, start_datetime, end_datetime):
        """Кэширует информацию о свободных слотах"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO free_slots_cache (spot_id, start_datetime, end_datetime)
                VALUES (?, ?, ?)
            """, (spot_id, start_datetime, end_datetime))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка кэширования слотов: {e}")
            return False
    
    def get_cached_free_slots(self, days_ahead=7):
        """Получает кэшированные свободные слоты"""
        try:
            cursor = self.connection.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                SELECT fsc.*, ps.spot_number, ps.price_per_hour, ps.price_per_day,
                       u.username, u.first_name
                FROM free_slots_cache fsc
                JOIN parking_spots ps ON fsc.spot_id = ps.id
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE fsc.start_datetime >= ? AND fsc.start_datetime <= ?
                ORDER BY fsc.start_datetime
            """, (now, future_date))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения кэшированных слотов: {e}")
            return []
    
    # ============ ADMIN METHODS ============
    def get_all_users(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT u.*, 
                       COUNT(DISTINCT ps.id) as total_spots,
                       COUNT(DISTINCT b.id) as total_bookings,
                       SUM(CASE WHEN b.status = 'active' THEN b.total_price ELSE 0 END) as total_spent
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
                       COUNT(DISTINCT ap.id) as total_periods,
                       SUM(CASE WHEN ap.is_booked = 1 THEN 1 ELSE 0 END) as booked_periods,
                       COUNT(DISTINCT b.id) as total_bookings
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                LEFT JOIN availability_periods ap ON ps.id = ap.spot_id
                LEFT JOIN bookings b ON ps.id = b.spot_id
                GROUP BY ps.id
                ORDER BY ps.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех мест: {e}")
            return []
    
    def get_all_bookings(self, days=30):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, 
                       ps.spot_number,
                       u.username as user_username, u.first_name as user_name, u.phone as user_phone,
                       owner.username as owner_username, owner.first_name as owner_name, owner.phone as owner_phone
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON b.user_id = u.user_id
                JOIN users owner ON ps.owner_id = owner.user_id
                WHERE b.created_at >= DATE('now', ?)
                ORDER BY b.created_at DESC
            """, (f'-{days} days',))
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
            
            cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'active' AND start_datetime >= DATETIME('now')")
            stats['active_bookings'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT SUM(total_price) as total FROM bookings WHERE status = 'active'")
            stats['total_income'] = cursor.fetchone()['total'] or 0
            
            cursor.execute("SELECT COUNT(*) as count FROM availability_periods WHERE is_booked = 0")
            stats['available_periods'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM availability_periods WHERE is_booked = 1")
            stats['booked_periods'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM availability_notifications WHERE is_active = 1")
            stats['active_notifications'] = cursor.fetchone()['count']
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    def close(self):
        if self.connection:
            self.connection.close()
