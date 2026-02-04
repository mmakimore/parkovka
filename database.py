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
        self.create_admin()
    
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
    
    def create_admin(self):
        """Создаем администратора при первом запуске"""
        try:
            cursor = self.connection.cursor()
            # ID админа из конфига
            cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (7884533080,))
            admin = cursor.fetchone()
            
            if not admin:
                cursor.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, username, first_name, phone, is_admin) 
                    VALUES (?, ?, ?, ?, ?)
                """, (7884533080, "admin", "Администратор", "+79990000000", 1))
                self.connection.commit()
                logger.info("Администратор создан")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания админа: {e}")
            return False
    
    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                card_number TEXT,
                bank TEXT,
                car_brand TEXT,
                car_model TEXT,
                car_plate TEXT,
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
            """
        ]
        
        try:
            cursor = self.connection.cursor()
            for query in queries:
                cursor.execute(query)
            
            # Индексы
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
                CREATE INDEX IF NOT EXISTS idx_spots_owner 
                ON parking_spots(owner_id, is_active)
            """)
            
            self.connection.commit()
            logger.info("Все таблицы созданы/проверены")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания таблиц: {e}")
            return False
    
    # ============ ПОЛЬЗОВАТЕЛИ ============
    def add_user(self, user_id, username, first_name, phone, card_number=None, bank=None, 
                car_brand=None, car_model=None, car_plate=None):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, phone, card_number, bank, car_brand, car_model, car_plate) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, phone, card_number, bank, car_brand, car_model, car_plate))
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
    
    def get_all_users(self):
        """Получить всех пользователей (для админа)"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, phone, card_number, bank, 
                       car_brand, car_model, car_plate, is_admin, registered_at
                FROM users 
                ORDER BY registered_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
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
    
    # ============ МЕСТА ============
    def add_parking_spot(self, owner_id, spot_number, price_per_hour, price_per_day):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO parking_spots (owner_id, spot_number, price_per_hour, price_per_day)
                VALUES (?, ?, ?, ?)
            """, (owner_id, spot_number, price_per_hour, price_per_day))
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.error(f"Место уже существует: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка добавления парковочного места: {e}")
            return None
    
    def get_parking_spot(self, spot_id):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, u.username, u.first_name, u.phone, u.card_number, u.bank
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ps.id = ? AND ps.is_active = 1
            """, (spot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения места: {e}")
            return None
    
    def get_all_spots(self):
        """Получить все места (для админа)"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, u.username, u.first_name, u.phone, 
                       (SELECT COUNT(*) FROM availability_periods ap 
                        WHERE ap.spot_id = ps.id AND ap.is_booked = 0) as available_periods,
                       (SELECT COUNT(*) FROM availability_periods ap 
                        WHERE ap.spot_id = ps.id AND ap.is_booked = 1) as booked_periods,
                       (SELECT COUNT(*) FROM bookings b 
                        WHERE b.spot_id = ps.id AND b.status = 'active') as active_bookings
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ps.is_active = 1
                ORDER BY ps.spot_number
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех мест: {e}")
            return []
    
    def get_user_spots(self, owner_id):
        """Получить места пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT ps.*, 
                       COUNT(DISTINCT ap.id) as total_periods,
                       SUM(CASE WHEN ap.is_booked = 1 THEN 1 ELSE 0 END) as booked_periods
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
    
    def get_available_spots_for_guest(self):
        """Получить места для гостей (без деталей владельцев)"""
        try:
            cursor = self.connection.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                SELECT DISTINCT ps.id, ps.spot_number, ps.price_per_hour, ps.price_per_day
                FROM parking_spots ps
                JOIN availability_periods ap ON ps.id = ap.spot_id
                WHERE ps.is_active = 1 
                  AND ap.is_booked = 0
                  AND ap.end_datetime > ?
                GROUP BY ps.id
                ORDER BY ps.price_per_hour
            """, (now,))
            
            rows = cursor.fetchall()
            spots = []
            for row in rows:
                spot = dict(row)
                # Получаем периоды для этого места
                cursor.execute("""
                    SELECT start_datetime, end_datetime 
                    FROM availability_periods 
                    WHERE spot_id = ? AND is_booked = 0 AND end_datetime > ?
                    ORDER BY start_datetime
                """, (spot['id'], now))
                periods = cursor.fetchall()
                spot['periods'] = [dict(p) for p in periods]
                spots.append(spot)
            
            return spots
        except Exception as e:
            logger.error(f"Ошибка получения мест для гостей: {e}")
            return []
    
    def get_available_spots_by_date_range(self, start_datetime, end_datetime):
        """Получить доступные места по диапазону дат"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT DISTINCT ps.*, u.username, u.first_name, u.card_number, u.bank
                FROM parking_spots ps
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE ps.id IN (
                    SELECT ap.spot_id 
                    FROM availability_periods ap
                    WHERE ap.is_booked = 0
                      AND ap.start_datetime <= ?
                      AND ap.end_datetime >= ?
                )
                AND ps.is_active = 1
                ORDER BY ps.price_per_hour
            """, (end_datetime, start_datetime))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения мест по диапазону дат: {e}")
            return []
    
    def find_available_periods(self, spot_id, start_datetime, end_datetime):
        """Найти доступные периоды для места"""
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
    
    def add_availability_period(self, spot_id, start_datetime, end_datetime):
        """Добавить период доступности"""
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
    
    def delete_spot(self, spot_id, owner_id):
        """Удалить место"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE parking_spots 
                SET is_active = 0 
                WHERE id = ? AND owner_id = ?
            """, (spot_id, owner_id))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления места: {e}")
            return False
    
    # ============ БРОНИРОВАНИЯ ============
    def create_booking(self, user_id, spot_id, period_id, start_datetime, end_datetime, total_price):
        """Создать бронирование"""
        try:
            cursor = self.connection.cursor()
            
            # Проверяем, что период свободен
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
            
            self.connection.commit()
            return booking_id
        except Exception as e:
            logger.error(f"Ошибка создания бронирования: {e}")
            self.connection.rollback()
            return None
    
    def get_user_bookings(self, user_id):
        """Получить бронирования пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, ps.spot_number, ps.price_per_hour,
                       u.username as owner_username, u.first_name as owner_name,
                       u.phone as owner_phone, u.card_number as owner_card, u.bank as owner_bank
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                LEFT JOIN users u ON ps.owner_id = u.user_id
                WHERE b.user_id = ? AND b.status = 'active'
                ORDER BY b.start_datetime DESC
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения бронирований пользователя: {e}")
            return []
    
    def get_all_bookings(self):
        """Получить все бронирования (для админа)"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT b.*, 
                       ps.spot_number, ps.price_per_hour,
                       u1.username as renter_username, u1.first_name as renter_name, 
                       u1.phone as renter_phone, u1.car_brand, u1.car_model, u1.car_plate,
                       u2.username as owner_username, u2.first_name as owner_name,
                       u2.card_number as owner_card, u2.bank as owner_bank,
                       u2.phone as owner_phone
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u1 ON b.user_id = u1.user_id
                JOIN users u2 ON ps.owner_id = u2.user_id
                ORDER BY b.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения всех бронирований: {e}")
            return []
    
    def cancel_booking(self, booking_id, user_id):
        """Отменить бронирование"""
        try:
            cursor = self.connection.cursor()
            
            # Получаем данные бронирования
            cursor.execute("""
                SELECT b.*, ap.id as period_id
                FROM bookings b
                LEFT JOIN availability_periods ap ON b.period_id = ap.id
                WHERE b.id = ? AND b.user_id = ?
            """, (booking_id, user_id))
            
            booking = cursor.fetchone()
            if not booking:
                return False
            
            # Отменяем бронирование
            cursor.execute("""
                UPDATE bookings 
                SET status = 'cancelled' 
                WHERE id = ?
            """, (booking_id,))
            
            # Освобождаем период
            if booking['period_id']:
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
    
    # ============ УВЕДОМЛЕНИЯ ============
    def add_notification(self, user_id, message):
        """Добавить уведомление"""
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
        """Получить непрочитанные уведомления"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY created_at DESC
                LIMIT 10
            """, (user_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения уведомлений: {e}")
            return []
    
    def mark_notifications_as_read(self, user_id):
        """Пометить уведомления как прочитанные"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE notifications 
                SET is_read = 1 
                WHERE user_id = ? AND is_read = 0
            """, (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка пометки уведомлений: {e}")
            return False
    
    def add_availability_notification(self, user_id, spot_id, start_datetime, end_datetime):
        """Добавить подписку на уведомление о доступности"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO availability_notifications (user_id, spot_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?)
            """, (user_id, spot_id, start_datetime, end_datetime))
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления подписки: {e}")
            return None
    
    def get_user_notifications(self, user_id):
        """Получить подписки пользователя"""
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
            logger.error(f"Ошибка получения подписок: {e}")
            return []
    
    def remove_notification(self, notification_id):
        """Удалить подписку"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                DELETE FROM availability_notifications 
                WHERE id = ?
            """, (notification_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления подписки: {e}")
            return False
    
    # ============ СТАТИСТИКА ============
    def get_statistics(self):
        """Получить статистику"""
        try:
            cursor = self.connection.cursor()
            stats = {}
            
            cursor.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM parking_spots WHERE is_active = 1")
            stats['active_spots'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'active'")
            stats['active_bookings'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM bookings")
            stats['total_bookings'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT SUM(total_price) as total FROM bookings WHERE status = 'active'")
            stats['total_income'] = cursor.fetchone()['total'] or 0
            
            cursor.execute("SELECT COUNT(*) as count FROM availability_periods WHERE is_booked = 0")
            stats['available_periods'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM availability_periods WHERE is_booked = 1")
            stats['booked_periods'] = cursor.fetchone()['count']
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    def close(self):
        """Закрыть соединение"""
        if self.connection:
            self.connection.close()
