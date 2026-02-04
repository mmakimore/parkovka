#!/usr/bin/env python3
"""
База данных для бота парковки
"""
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/parking_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self.connection = None
        self.connect()
        self.init_database()
        
    def connect(self):
        """Установка соединения с БД"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            logger.info(f"✅ База данных подключена: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise
            
    def init_database(self):
        """Инициализация всех таблиц"""
        try:
            cursor = self.connection.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    email TEXT,
                    card_number TEXT,
                    bank TEXT,
                    car_brand TEXT,
                    car_model TEXT,
                    car_plate TEXT UNIQUE,
                    is_admin BOOLEAN DEFAULT 0,
                    is_blocked BOOLEAN DEFAULT 0,
                    balance DECIMAL(10, 2) DEFAULT 0,
                    rating DECIMAL(3, 2) DEFAULT 5.0,
                    rating_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица парковочных мест
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parking_spots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    spot_number TEXT NOT NULL,
                    address TEXT NOT NULL,
                    description TEXT,
                    latitude REAL,
                    longitude REAL,
                    price_per_hour DECIMAL(10, 2) NOT NULL,
                    price_per_day DECIMAL(10, 2) NOT NULL,
                    price_per_month DECIMAL(10, 2),
                    is_covered BOOLEAN DEFAULT 0,
                    has_cctv BOOLEAN DEFAULT 0,
                    has_lighting BOOLEAN DEFAULT 0,
                    has_electricity BOOLEAN DEFAULT 0,
                    max_car_size TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    total_bookings INTEGER DEFAULT 0,
                    total_earnings DECIMAL(10, 2) DEFAULT 0,
                    rating DECIMAL(3, 2) DEFAULT 5.0,
                    rating_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(owner_id, spot_number)
                )
            ''')
            
            # Таблица расписания доступности
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS availability (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spot_id INTEGER NOT NULL,
                    day_of_week INTEGER, -- 0-6 (понедельник-воскресенье)
                    start_time TIME,
                    end_time TIME,
                    is_available BOOLEAN DEFAULT 1,
                    FOREIGN KEY (spot_id) REFERENCES parking_spots(id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица исключений в расписании
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS availability_exceptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spot_id INTEGER NOT NULL,
                    exception_date DATE NOT NULL,
                    is_available BOOLEAN DEFAULT 1,
                    reason TEXT,
                    FOREIGN KEY (spot_id) REFERENCES parking_spots(id) ON DELETE CASCADE,
                    UNIQUE(spot_id, exception_date)
                )
            ''')
            
            # Таблица бронирований
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_code TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    spot_id INTEGER NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    total_hours INTEGER NOT NULL,
                    total_price DECIMAL(10, 2) NOT NULL,
                    status TEXT DEFAULT 'pending', -- pending, confirmed, active, completed, cancelled
                    payment_status TEXT DEFAULT 'pending', -- pending, paid, refunded
                    payment_method TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    cancellation_reason TEXT,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (spot_id) REFERENCES parking_spots(id)
                )
            ''')
            
            # Таблица платежей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    payment_method TEXT NOT NULL,
                    transaction_id TEXT UNIQUE,
                    status TEXT DEFAULT 'pending', -- pending, completed, failed, refunded
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read_at TIMESTAMP,
                    data TEXT, -- JSON данные
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица отзывов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER NOT NULL,
                    reviewer_id INTEGER NOT NULL,
                    spot_id INTEGER NOT NULL,
                    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                    comment TEXT,
                    response TEXT,
                    is_approved BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings(id),
                    FOREIGN KEY (reviewer_id) REFERENCES users(id),
                    FOREIGN KEY (spot_id) REFERENCES parking_spots(id)
                )
            ''')
            
            # Таблица жалоб
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id INTEGER NOT NULL,
                    reported_user_id INTEGER,
                    reported_spot_id INTEGER,
                    booking_id INTEGER,
                    report_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'pending', -- pending, investigating, resolved, rejected
                    admin_notes TEXT,
                    resolved_by INTEGER,
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reporter_id) REFERENCES users(id),
                    FOREIGN KEY (reported_user_id) REFERENCES users(id),
                    FOREIGN KEY (reported_spot_id) REFERENCES parking_spots(id),
                    FOREIGN KEY (booking_id) REFERENCES bookings(id),
                    FOREIGN KEY (resolved_by) REFERENCES users(id)
                )
            ''')
            
            # Таблица операций с балансом
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balance_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    transaction_type TEXT NOT NULL, -- deposit, withdrawal, payment, refund, bonus
                    description TEXT,
                    booking_id INTEGER,
                    payment_id INTEGER,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (booking_id) REFERENCES bookings(id),
                    FOREIGN KEY (payment_id) REFERENCES payments(id)
                )
            ''')
            
            # Таблица настроек системы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица логов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица админ-сессий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Создаем индексы для производительности
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
                "CREATE INDEX IF NOT EXISTS idx_spots_owner ON parking_spots(owner_id)",
                "CREATE INDEX IF NOT EXISTS idx_spots_active ON parking_spots(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_bookings_spot ON bookings(spot_id)",
                "CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)",
                "CREATE INDEX IF NOT EXISTS idx_bookings_dates ON bookings(start_time, end_time)",
                "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)",
                "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)",
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_user ON admin_sessions(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(session_token)",
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON admin_sessions(expires_at)",
            ]
            
            for index in indexes:
                cursor.execute(index)
            
            # Вставляем дефолтные настройки
            default_settings = [
                ('system_name', 'Parking Bot', 'Название системы'),
                ('commission_rate', '0', 'Комиссия системы (%)'),
                ('min_booking_hours', '1', 'Минимальное время брони (часы)'),
                ('max_booking_days', '30', 'Максимальное время брони (дни)'),
                ('auto_cancel_hours', '24', 'Автоотмена неоплаченных броней (часы)'),
                ('support_phone', '+79990000000', 'Телефон поддержки'),
                ('support_email', 'support@parkingbot.ru', 'Email поддержки'),
                ('notification_new_booking', '1', 'Уведомлять о новых бронях'),
                ('notification_new_review', '1', 'Уведомлять о новых отзывах'),
                ('notification_new_report', '1', 'Уведомлять о новых жалобах'),
                ('admin_password', 'qwerty123', 'Пароль для входа в админ-панель'),
            ]
            
            cursor.executemany('''
                INSERT OR IGNORE INTO system_settings (key, value, description)
                VALUES (?, ?, ?)
            ''', default_settings)
            
            # Создаем администратора по умолчанию (ваш ID)
            admin_telegram_id = 7884533080
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (admin_telegram_id,))
            admin_exists = cursor.fetchone()
            
            if not admin_exists:
                cursor.execute('''
                    INSERT INTO users (telegram_id, full_name, phone, is_admin)
                    VALUES (?, ?, ?, ?)
                ''', (admin_telegram_id, 'Администратор системы', '+79990000000', 1))
                logger.info("✅ Создан администратор по умолчанию")
            
            self.connection.commit()
            logger.info("✅ База данных инициализирована")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise
    
    # ==================== АДМИН СЕССИИ ====================
    
    def create_admin_session(self, user_id: int, expires_hours: int = 24) -> Optional[str]:
        """Создание админ-сессии для пользователя"""
        try:
            cursor = self.connection.cursor()
            
            # Удаляем старые сессии пользователя
            cursor.execute('''
                DELETE FROM admin_sessions WHERE user_id = ?
            ''', (user_id,))
            
            # Создаем токен сессии
            session_token = secrets.token_hex(32)
            
            # Рассчитываем время истечения
            expires_at = datetime.now() + timedelta(hours=expires_hours)
            
            cursor.execute('''
                INSERT INTO admin_sessions (user_id, session_token, expires_at)
                VALUES (?, ?, ?)
            ''', (user_id, session_token, expires_at))
            
            self.connection.commit()
            logger.info(f"✅ Создана админ-сессия для пользователя {user_id}")
            return session_token
        except Exception as e:
            logger.error(f"❌ Ошибка создания админ-сессии: {e}")
            return None
    
    def get_admin_session(self, user_id: int) -> Optional[Dict]:
        """Получение активной админ-сессии пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT * FROM admin_sessions 
                WHERE user_id = ? AND expires_at > ?
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id, datetime.now()))
            
            session = cursor.fetchone()
            return dict(session) if session else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения админ-сессии: {e}")
            return None
    
    def delete_admin_session(self, user_id: int) -> bool:
        """Удаление админ-сессии пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                DELETE FROM admin_sessions WHERE user_id = ?
            ''', (user_id,))
            
            self.connection.commit()
            logger.info(f"✅ Удалена админ-сессия пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления админ-сессии: {e}")
            return False
    
    def check_admin_password(self, password: str) -> bool:
        """Проверка пароля для входа в админку"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT value FROM system_settings WHERE key = 'admin_password'
            ''')
            
            result = cursor.fetchone()
            if not result:
                # Устанавливаем пароль по умолчанию
                self.set_setting('admin_password', 'qwerty123')
                return password == 'qwerty123'
            
            return password == result['value']
        except Exception as e:
            logger.error(f"❌ Ошибка проверки пароля админа: {e}")
            return False
    
    def is_admin_user(self, telegram_id: int) -> bool:
        """Проверка, является ли пользователь админом (постоянным или по сессии)"""
        try:
            # Получаем пользователя
            user = self.get_user(telegram_id=telegram_id)
            if not user:
                return False
            
            # Проверяем постоянного админа
            if user.get('is_admin'):
                return True
            
            # Проверяем активную админ-сессию
            session = self.get_admin_session(user['id'])
            if session and datetime.fromisoformat(session['expires_at']) > datetime.now():
                return True
            
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки прав админа: {e}")
            return False
    
    def set_admin_password(self, new_password: str) -> bool:
        """Установка нового пароля для админ-панели"""
        try:
            return self.set_setting('admin_password', new_password)
        except Exception as e:
            logger.error(f"❌ Ошибка установки пароля админа: {e}")
            return False
    
    def get_admin_session_info(self, telegram_id: int) -> Optional[Dict]:
        """Получение информации об админ-сессии пользователя"""
        try:
            user = self.get_user(telegram_id=telegram_id)
            if not user:
                return None
            
            session = self.get_admin_session(user['id'])
            if not session:
                return None
            
            session_info = dict(session)
            session_info['is_permanent_admin'] = bool(user.get('is_admin'))
            session_info['expires_at_formatted'] = datetime.fromisoformat(
                session['expires_at']
            ).strftime('%d.%m.%Y %H:%M')
            
            return session_info
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о сессии: {e}")
            return None
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
    def register_user(self, telegram_id: int, full_name: str, phone: str, 
                     username: str = None, email: str = None) -> Optional[int]:
        """Регистрация нового пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO users (telegram_id, username, full_name, phone, email, last_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (telegram_id, username, full_name, phone, email, datetime.now()))
            
            user_id = cursor.lastrowid
            self.connection.commit()
            
            # Логируем регистрацию
            self.add_log(user_id, "registration", f"Зарегистрирован пользователь: {full_name}")
            
            # Отправляем уведомление админам
            self.notify_admins("Новая регистрация", 
                             f"Зарегистрирован новый пользователь: {full_name} (@{username if username else 'нет'})")
            
            return user_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.telegram_id" in str(e):
                # Пользователь уже существует, обновляем данные
                cursor.execute('''
                    UPDATE users SET username = ?, full_name = ?, phone = ?, 
                    email = ?, last_active = ? WHERE telegram_id = ?
                ''', (username, full_name, phone, email, datetime.now(), telegram_id))
                self.connection.commit()
                
                cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
                user = cursor.fetchone()
                return user['id'] if user else None
            elif "UNIQUE constraint failed: users.phone" in str(e):
                raise ValueError("Этот телефон уже зарегистрирован")
            else:
                logger.error(f"Ошибка регистрации: {e}")
                return None
        except Exception as e:
            logger.error(f"Ошибка регистрации: {e}")
            return None
    
    def get_user(self, user_id: int = None, telegram_id: int = None, phone: str = None) -> Optional[Dict]:
        """Получение данных пользователя"""
        try:
            cursor = self.connection.cursor()
            
            if user_id:
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            elif telegram_id:
                cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            elif phone:
                cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
            else:
                return None
            
            user = cursor.fetchone()
            return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """Обновление данных пользователя"""
        try:
            cursor = self.connection.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            
            cursor.execute(f'''
                UPDATE users SET {set_clause}, last_active = ? 
                WHERE id = ?
            ''', values + [datetime.now()])
            
            self.connection.commit()
            
            if kwargs:
                self.add_log(user_id, "profile_update", "Обновление профиля")
            
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя: {e}")
            return False
    
    def update_user_balance(self, user_id: int, amount: float, 
                          transaction_type: str, description: str = None,
                          booking_id: int = None, payment_id: int = None) -> bool:
        """Обновление баланса пользователя"""
        try:
            cursor = self.connection.cursor()
            
            # Обновляем баланс
            cursor.execute('''
                UPDATE users SET balance = balance + ? WHERE id = ?
            ''', (amount, user_id))
            
            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO balance_transactions 
                (user_id, amount, transaction_type, description, booking_id, payment_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, transaction_type, description, booking_id, payment_id))
            
            self.connection.commit()
            self.add_log(user_id, "balance_update", f"{transaction_type}: {amount} руб.")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления баланса: {e}")
            return False
    
    def get_user_balance(self, user_id: int) -> float:
        """Получение баланса пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            return result['balance'] if result else 0.0
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return 0.0
    
    def get_all_users(self, limit: int = 100, offset: int = 0, 
                     is_admin: bool = None, is_blocked: bool = None) -> List[Dict]:
        """Получение списка всех пользователей (для админа)"""
        try:
            cursor = self.connection.cursor()
            query = "SELECT * FROM users WHERE 1=1"
            params = []
            
            if is_admin is not None:
                query += " AND is_admin = ?"
                params.append(1 if is_admin else 0)
            
            if is_blocked is not None:
                query += " AND is_blocked = ?"
                params.append(1 if is_blocked else 0)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return []
    
    def set_admin(self, user_id: int, is_admin: bool = True) -> bool:
        """Назначение/снятие прав администратора"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE users SET is_admin = ? WHERE id = ?
            ''', (is_admin, user_id))
            
            self.connection.commit()
            self.add_log(user_id, "admin_change", 
                        f"Права админа {'выданы' if is_admin else 'сняты'}")
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка изменения прав админа: {e}")
            return False
    
    def block_user(self, user_id: int, is_blocked: bool = True) -> bool:
        """Блокировка/разблокировка пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE users SET is_blocked = ? WHERE id = ?
            ''', (is_blocked, user_id))
            
            self.connection.commit()
            self.add_log(user_id, "block_change", 
                        f"Пользователь {'заблокирован' if is_blocked else 'разблокирован'}")
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка блокировки пользователя: {e}")
            return False
    
    # ==================== ПАРКОВОЧНЫЕ МЕСТА ====================
    
    def add_parking_spot(self, owner_id: int, spot_number: str, address: str,
                        price_per_hour: float, price_per_day: float,
                        description: str = None, latitude: float = None,
                        longitude: float = None, is_covered: bool = False,
                        has_cctv: bool = False, has_lighting: bool = False,
                        has_electricity: bool = False, max_car_size: str = None) -> Optional[int]:
        """Добавление нового парковочного места"""
        try:
            cursor = self.connection.cursor()
            
            # Проверяем, не превышен ли лимит мест
            cursor.execute('''
                SELECT COUNT(*) as count FROM parking_spots 
                WHERE owner_id = ? AND is_active = 1
            ''', (owner_id,))
            count = cursor.fetchone()['count']
            
            if count >= 10:  # Максимум 10 мест на пользователя
                raise ValueError("Превышен лимит парковочных мест (максимум 10)")
            
            cursor.execute('''
                INSERT INTO parking_spots 
                (owner_id, spot_number, address, description, latitude, longitude,
                 price_per_hour, price_per_day, is_covered, has_cctv, has_lighting,
                 has_electricity, max_car_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (owner_id, spot_number, address, description, latitude, longitude,
                 price_per_hour, price_per_day, is_covered, has_cctv, has_lighting,
                 has_electricity, max_car_size))
            
            spot_id = cursor.lastrowid
            
            # Создаем стандартное расписание (все дни, круглосуточно)
            days = list(range(7))  # 0-6 дни недели
            for day in days:
                cursor.execute('''
                    INSERT INTO availability (spot_id, day_of_week, start_time, end_time)
                    VALUES (?, ?, '00:00', '23:59')
                ''', (spot_id, day))
            
            self.connection.commit()
            
            self.add_log(owner_id, "spot_added", f"Добавлено место #{spot_number}")
            self.notify_admins("Новое парковочное место", 
                             f"Пользователь добавил новое место: {address} (#{spot_number})")
            
            return spot_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValueError("Такое место уже существует у этого владельца")
            logger.error(f"Ошибка добавления места: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка добавления места: {e}")
            return None
    
    def get_parking_spot(self, spot_id: int) -> Optional[Dict]:
        """Получение информации о месте"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT ps.*, u.full_name as owner_name, u.phone as owner_phone,
                       u.rating as owner_rating, u.rating_count as owner_rating_count
                FROM parking_spots ps
                JOIN users u ON ps.owner_id = u.id
                WHERE ps.id = ? AND ps.is_active = 1
            ''', (spot_id,))
            
            spot = cursor.fetchone()
            return dict(spot) if spot else None
        except Exception as e:
            logger.error(f"Ошибка получения места: {e}")
            return None
    
    def get_user_spots(self, owner_id: int) -> List[Dict]:
        """Получение мест пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT ps.*, 
                       (SELECT COUNT(*) FROM bookings b 
                        WHERE b.spot_id = ps.id AND b.status IN ('confirmed', 'active')) as active_bookings,
                       (SELECT SUM(total_price) FROM bookings b 
                        WHERE b.spot_id = ps.id AND b.payment_status = 'paid') as total_earnings
                FROM parking_spots ps
                WHERE ps.owner_id = ? AND ps.is_active = 1
                ORDER BY ps.created_at DESC
            ''', (owner_id,))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения мест пользователя: {e}")
            return []
    
    def get_available_spots(self, start_time: datetime, end_time: datetime,
                          limit: int = 50) -> List[Dict]:
        """Поиск доступных мест на указанный период"""
        try:
            cursor = self.connection.cursor()
            
            # Получаем день недели для проверки расписания
            day_of_week = start_time.weekday()  # 0-6
            
            cursor.execute('''
                SELECT ps.*, u.full_name as owner_name, u.rating as owner_rating
                FROM parking_spots ps
                JOIN users u ON ps.owner_id = u.id
                WHERE ps.is_active = 1
                AND ps.id NOT IN (
                    -- Исключаем места с заблокированными на этот день
                    SELECT a.spot_id FROM availability a
                    WHERE a.day_of_week = ? 
                    AND a.is_available = 0
                    AND (
                        (a.start_time IS NULL AND a.end_time IS NULL) OR
                        (TIME(?) >= a.start_time AND TIME(?) <= a.end_time)
                    )
                )
                AND ps.id NOT IN (
                    -- Исключаем места с исключениями на эту дату
                    SELECT ae.spot_id FROM availability_exceptions ae
                    WHERE ae.exception_date = DATE(?)
                    AND ae.is_available = 0
                )
                AND ps.id NOT IN (
                    -- Исключаем места с активными бронированиями в этот период
                    SELECT b.spot_id FROM bookings b
                    WHERE b.status IN ('confirmed', 'active')
                    AND (
                        (b.start_time <= ? AND b.end_time >= ?) OR
                        (b.start_time <= ? AND b.end_time >= ?) OR
                        (b.start_time >= ? AND b.end_time <= ?)
                    )
                )
                ORDER BY ps.price_per_hour
                LIMIT ?
            ''', (day_of_week, start_time.time(), end_time.time(), 
                  start_time.date(), start_time, start_time, end_time, end_time,
                  start_time, end_time, limit))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка поиска доступных мест: {e}")
            return []
    
    def update_spot(self, spot_id: int, **kwargs) -> bool:
        """Обновление информации о месте"""
        try:
            cursor = self.connection.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [spot_id]
            
            cursor.execute(f'''
                UPDATE parking_spots SET {set_clause} WHERE id = ?
            ''', values)
            
            self.connection.commit()
            
            # Получаем владельца для логирования
            cursor.execute("SELECT owner_id FROM parking_spots WHERE id = ?", (spot_id,))
            owner = cursor.fetchone()
            if owner:
                self.add_log(owner['owner_id'], "spot_updated", f"Обновлено место #{spot_id}")
            
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления места: {e}")
            return False
    
    def delete_spot(self, spot_id: int) -> bool:
        """Удаление места (мягкое удаление)"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE parking_spots SET is_active = 0 WHERE id = ?
            ''', (spot_id,))
            
            self.connection.commit()
            
            # Получаем владельца для логирования
            cursor.execute("SELECT owner_id FROM parking_spots WHERE id = ?", (spot_id,))
            owner = cursor.fetchone()
            if owner:
                self.add_log(owner['owner_id'], "spot_deleted", f"Удалено место #{spot_id}")
            
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления места: {e}")
            return False
    
    def get_spot_availability(self, spot_id: int, date: datetime = None) -> List[Dict]:
        """Получение расписания доступности места"""
        try:
            cursor = self.connection.cursor()
            
            if date:
                # Получаем исключения на конкретную дату
                cursor.execute('''
                    SELECT ae.* FROM availability_exceptions ae
                    WHERE ae.spot_id = ? AND ae.exception_date = DATE(?)
                ''', (spot_id, date))
                exceptions = [dict(row) for row in cursor.fetchall()]
                
                # Получаем расписание на день недели
                day_of_week = date.weekday()
                cursor.execute('''
                    SELECT a.* FROM availability a
                    WHERE a.spot_id = ? AND a.day_of_week = ?
                ''', (spot_id, day_of_week))
                schedule = [dict(row) for row in cursor.fetchall()]
                
                return schedule + exceptions
            else:
                # Получаем всё расписание
                cursor.execute('''
                    SELECT a.* FROM availability a
                    WHERE a.spot_id = ?
                    ORDER BY a.day_of_week, a.start_time
                ''', (spot_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения расписания: {e}")
            return []
    
    def set_spot_availability(self, spot_id: int, day_of_week: int, 
                             start_time: str, end_time: str, is_available: bool = True) -> bool:
        """Установка расписания доступности"""
        try:
            cursor = self.connection.cursor()
            
            # Удаляем существующее расписание на этот день
            cursor.execute('''
                DELETE FROM availability 
                WHERE spot_id = ? AND day_of_week = ?
            ''', (spot_id, day_of_week))
            
            # Добавляем новое
            cursor.execute('''
                INSERT INTO availability (spot_id, day_of_week, start_time, end_time, is_available)
                VALUES (?, ?, ?, ?, ?)
            ''', (spot_id, day_of_week, start_time, end_time, is_available))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка установки расписания: {e}")
            return False
    
    def add_availability_exception(self, spot_id: int, exception_date: datetime,
                                 is_available: bool = True, reason: str = None) -> bool:
        """Добавление исключения в расписание"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO availability_exceptions 
                (spot_id, exception_date, is_available, reason)
                VALUES (?, ?, ?, ?)
            ''', (spot_id, exception_date.date(), is_available, reason))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления исключения: {e}")
            return False
    
    # ==================== БРОНИРОВАНИЯ ====================
    
    def create_booking(self, user_id: int, spot_id: int, start_time: datetime,
                      end_time: datetime, notes: str = None) -> Optional[int]:
        """Создание бронирования"""
        try:
            # Проверяем доступность
            if not self.is_spot_available(spot_id, start_time, end_time):
                raise ValueError("Место недоступно на выбранное время")
            
            # Получаем информацию о месте для расчета цены
            spot = self.get_parking_spot(spot_id)
            if not spot:
                raise ValueError("Место не найдено")
            
            # Рассчитываем продолжительность и стоимость
            duration_hours = (end_time - start_time).total_seconds() / 3600
            total_price = duration_hours * spot['price_per_hour']
            
            # Генерируем код бронирования
            import random
            booking_code = f"BK{datetime.now().strftime('%y%m%d')}{random.randint(1000, 9999)}"
            
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO bookings 
                (booking_code, user_id, spot_id, start_time, end_time, 
                 total_hours, total_price, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (booking_code, user_id, spot_id, start_time, end_time,
                 duration_hours, total_price, notes))
            
            booking_id = cursor.lastrowid
            
            self.connection.commit()
            
            # Отправляем уведомления
            self.add_notification(
                user_id,
                "booking_created",
                "Бронирование создано",
                f"Ваше бронирование #{booking_code} создано. Ожидайте подтверждения."
            )
            
            spot_owner = self.get_user(spot['owner_id'])
            if spot_owner:
                self.add_notification(
                    spot_owner['id'],
                    "new_booking_request",
                    "Новый запрос на бронирование",
                    f"Новый запрос на бронирование места #{spot['spot_number']}.\nКод: {booking_code}"
                )
            
            self.add_log(user_id, "booking_created", f"Создано бронирование #{booking_code}")
            
            return booking_id
        except Exception as e:
            logger.error(f"Ошибка создания бронирования: {e}")
            return None
    
    def is_spot_available(self, spot_id: int, start_time: datetime, 
                         end_time: datetime) -> bool:
        """Проверка доступности места на указанный период"""
        try:
            cursor = self.connection.cursor()
            
            # Проверяем активные бронирования
            cursor.execute('''
                SELECT COUNT(*) as count FROM bookings
                WHERE spot_id = ? 
                AND status IN ('confirmed', 'active')
                AND (
                    (start_time < ? AND end_time > ?) OR
                    (start_time < ? AND end_time > ?) OR
                    (start_time >= ? AND end_time <= ?)
                )
            ''', (spot_id, end_time, start_time, end_time, start_time, start_time, end_time))
            
            overlapping_bookings = cursor.fetchone()['count']
            if overlapping_bookings > 0:
                return False
            
            # Проверяем расписание
            day_of_week = start_time.weekday()
            cursor.execute('''
                SELECT COUNT(*) as count FROM availability
                WHERE spot_id = ? AND day_of_week = ? AND is_available = 0
                AND (
                    (start_time IS NULL AND end_time IS NULL) OR
                    (TIME(?) >= start_time AND TIME(?) <= end_time)
                )
            ''', (spot_id, day_of_week, start_time.time(), end_time.time()))
            
            blocked_schedule = cursor.fetchone()['count']
            if blocked_schedule > 0:
                return False
            
            # Проверяем исключения
            cursor.execute('''
                SELECT COUNT(*) as count FROM availability_exceptions
                WHERE spot_id = ? AND exception_date = DATE(?)
                AND is_available = 0
            ''', (spot_id, start_time.date()))
            
            blocked_exceptions = cursor.fetchone()['count']
            if blocked_exceptions > 0:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Ошибка проверки доступности: {e}")
            return False
    
    def get_booking(self, booking_id: int = None, booking_code: str = None) -> Optional[Dict]:
        """Получение информации о бронировании"""
        try:
            cursor = self.connection.cursor()
            
            if booking_id:
                cursor.execute('''
                    SELECT b.*, 
                           ps.spot_number, ps.address, ps.price_per_hour,
                           u1.full_name as user_name, u1.phone as user_phone,
                           u1.car_plate as user_car_plate,
                           u2.full_name as owner_name, u2.phone as owner_phone
                    FROM bookings b
                    JOIN parking_spots ps ON b.spot_id = ps.id
                    JOIN users u1 ON b.user_id = u1.id
                    JOIN users u2 ON ps.owner_id = u2.id
                    WHERE b.id = ?
                ''', (booking_id,))
            elif booking_code:
                cursor.execute('''
                    SELECT b.*, 
                           ps.spot_number, ps.address, ps.price_per_hour,
                           u1.full_name as user_name, u1.phone as user_phone,
                           u1.car_plate as user_car_plate,
                           u2.full_name as owner_name, u2.phone as owner_phone
                    FROM bookings b
                    JOIN parking_spots ps ON b.spot_id = ps.id
                    JOIN users u1 ON b.user_id = u1.id
                    JOIN users u2 ON ps.owner_id = u2.id
                    WHERE b.booking_code = ?
                ''', (booking_code,))
            else:
                return None
            
            booking = cursor.fetchone()
            return dict(booking) if booking else None
        except Exception as e:
            logger.error(f"Ошибка получения бронирования: {e}")
            return None
    
    def get_user_bookings(self, user_id: int, status: str = None, 
                         limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение бронирований пользователя"""
        try:
            cursor = self.connection.cursor()
            query = '''
                SELECT b.*, ps.spot_number, ps.address, u.full_name as owner_name
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON ps.owner_id = u.id
                WHERE b.user_id = ?
            '''
            params = [user_id]
            
            if status:
                query += " AND b.status = ?"
                params.append(status)
            
            query += " ORDER BY b.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения бронирований: {e}")
            return []
    
    def get_owner_bookings(self, owner_id: int, status: str = None,
                          limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение бронирований владельца мест"""
        try:
            cursor = self.connection.cursor()
            query = '''
                SELECT b.*, ps.spot_number, ps.address, u.full_name as user_name,
                       u.phone as user_phone, u.car_plate as user_car_plate
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON b.user_id = u.id
                WHERE ps.owner_id = ?
            '''
            params = [owner_id]
            
            if status:
                query += " AND b.status = ?"
                params.append(status)
            
            query += " ORDER BY b.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения бронирований владельца: {e}")
            return []
    
    def update_booking_status(self, booking_id: int, status: str, 
                             cancelled_by: int = None, reason: str = None) -> bool:
        """Обновление статуса бронирования"""
        try:
            cursor = self.connection.cursor()
            
            if status == 'cancelled':
                cursor.execute('''
                    UPDATE bookings 
                    SET status = ?, cancelled_at = ?, cancellation_reason = ?
                    WHERE id = ?
                ''', (status, datetime.now(), reason, booking_id))
            else:
                cursor.execute('''
                    UPDATE bookings SET status = ? WHERE id = ?
                ''', (status, booking_id))
            
            self.connection.commit()
            
            # Получаем информацию о бронировании для уведомлений
            booking = self.get_booking(booking_id)
            if booking:
                # Уведомляем пользователя
                self.add_notification(
                    booking['user_id'],
                    "booking_status_changed",
                    "Статус бронирования изменен",
                    f"Статус вашего бронирования #{booking['booking_code']} изменен на: {status}"
                )
                
                # Уведомляем владельца
                spot = self.get_parking_spot(booking['spot_id'])
                if spot:
                    self.add_notification(
                        spot['owner_id'],
                        "booking_status_changed",
                        "Статус бронирования изменен",
                        f"Статус бронирования #{booking['booking_code']} изменен на: {status}"
                    )
                
                self.add_log(cancelled_by if cancelled_by else booking['user_id'],
                           "booking_status_changed",
                           f"Бронирование #{booking['booking_code']}: {status}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса брони: {e}")
            return False
    
    def confirm_booking(self, booking_id: int, owner_id: int) -> bool:
        """Подтверждение бронирования владельцем"""
        try:
            # Проверяем, что владелец подтверждает свое место
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT ps.owner_id FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                WHERE b.id = ?
            ''', (booking_id,))
            
            result = cursor.fetchone()
            if not result or result['owner_id'] != owner_id:
                return False
            
            return self.update_booking_status(booking_id, 'confirmed')
        except Exception as e:
            logger.error(f"Ошибка подтверждения брони: {e}")
            return False
    
    def complete_booking(self, booking_id: int) -> bool:
        """Завершение бронирования"""
        try:
            booking = self.get_booking(booking_id)
            if not booking:
                return False
            
            # Проверяем, что время брони истекло
            if datetime.now() < booking['end_time']:
                return False
            
            return self.update_booking_status(booking_id, 'completed')
        except Exception as e:
            logger.error(f"Ошибка завершения брони: {e}")
            return False
    
    def get_active_bookings(self) -> List[Dict]:
        """Получение активных бронирований"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT b.*, ps.spot_number, u.full_name as user_name,
                       u.phone as user_phone
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                JOIN users u ON b.user_id = u.id
                WHERE b.status IN ('confirmed', 'active')
                AND b.end_time > ?
                ORDER BY b.start_time
            ''', (datetime.now(),))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения активных бронирований: {e}")
            return []
    
    # ==================== ПЛАТЕЖИ ====================
    
    def create_payment(self, booking_id: int, user_id: int, amount: float,
                      payment_method: str, description: str = None) -> Optional[int]:
        """Создание платежа"""
        try:
            import random
            transaction_id = f"TXN{datetime.now().strftime('%y%m%d%H%M%S')}{random.randint(100, 999)}"
            
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO payments 
                (booking_id, user_id, amount, payment_method, transaction_id, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (booking_id, user_id, amount, payment_method, transaction_id, description))
            
            payment_id = cursor.lastrowid
            self.connection.commit()
            
            # Обновляем статус бронирования
            cursor.execute('''
                UPDATE bookings SET payment_status = 'paid' WHERE id = ?
            ''', (booking_id,))
            
            self.connection.commit()
            
            self.add_log(user_id, "payment_created", 
                        f"Создан платеж {amount} руб. за бронирование #{booking_id}")
            
            return payment_id
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return None
    
    def get_payment(self, payment_id: int) -> Optional[Dict]:
        """Получение информации о платеже"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT p.*, b.booking_code, u.full_name as user_name
                FROM payments p
                JOIN bookings b ON p.booking_id = b.id
                JOIN users u ON p.user_id = u.id
                WHERE p.id = ?
            ''', (payment_id,))
            
            payment = cursor.fetchone()
            return dict(payment) if payment else None
        except Exception as e:
            logger.error(f"Ошибка получения платежа: {e}")
            return None
    
    def update_payment_status(self, payment_id: int, status: str) -> bool:
        """Обновление статуса платежа"""
        try:
            cursor = self.connection.cursor()
            
            if status == 'completed':
                cursor.execute('''
                    UPDATE payments 
                    SET status = ?, completed_at = ?
                    WHERE id = ?
                ''', (status, datetime.now(), payment_id))
            else:
                cursor.execute('''
                    UPDATE payments SET status = ? WHERE id = ?
                ''', (status, payment_id))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа: {e}")
            return False
    
    # ==================== УВЕДОМЛЕНИЯ ====================
    
    def add_notification(self, user_id: int, notification_type: str,
                        title: str, message: str, data: dict = None) -> Optional[int]:
        """Добавление уведомления"""
        try:
            cursor = self.connection.cursor()
            data_json = json.dumps(data) if data else None
            
            cursor.execute('''
                INSERT INTO notifications 
                (user_id, notification_type, title, message, data)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, notification_type, title, message, data_json))
            
            notification_id = cursor.lastrowid
            self.connection.commit()
            return notification_id
        except Exception as e:
            logger.error(f"Ошибка добавления уведомления: {e}")
            return None
    
    def get_user_notifications(self, user_id: int, unread_only: bool = False,
                              limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение уведомлений пользователя"""
        try:
            cursor = self.connection.cursor()
            query = "SELECT * FROM notifications WHERE user_id = ?"
            params = [user_id]
            
            if unread_only:
                query += " AND is_read = 0"
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            notifications = []
            
            for row in cursor.fetchall():
                notification = dict(row)
                if notification['data']:
                    try:
                        notification['data'] = json.loads(notification['data'])
                    except:
                        notification['data'] = None
                notifications.append(notification)
            
            return notifications
        except Exception as e:
            logger.error(f"Ошибка получения уведомлений: {e}")
            return []
    
    def mark_notification_read(self, notification_id: int) -> bool:
        """Пометить уведомление как прочитанное"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE notifications 
                SET is_read = 1, read_at = ?
                WHERE id = ?
            ''', (datetime.now(), notification_id))
            
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка пометки уведомления: {e}")
            return False
    
    def mark_all_notifications_read(self, user_id: int) -> bool:
        """Пометить все уведомления как прочитанные"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE notifications 
                SET is_read = 1, read_at = ?
                WHERE user_id = ? AND is_read = 0
            ''', (datetime.now(), user_id))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка пометки уведомлений: {e}")
            return False
    
    def count_unread_notifications(self, user_id: int) -> int:
        """Подсчет непрочитанных уведомлений"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM notifications
                WHERE user_id = ? AND is_read = 0
            ''', (user_id,))
            
            result = cursor.fetchone()
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Ошибка подсчета уведомлений: {e}")
            return 0
    
    def notify_admins(self, title: str, message: str) -> int:
        """Отправка уведомления всем администраторам"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT id FROM users WHERE is_admin = 1
            ''')
            
            admins = cursor.fetchall()
            count = 0
            
            for admin in admins:
                self.add_notification(
                    admin['id'],
                    "admin_notification",
                    title,
                    message
                )
                count += 1
            
            return count
        except Exception as e:
            logger.error(f"Ошибка уведомления админов: {e}")
            return 0
    
    # ==================== ОТЗЫВЫ ====================
    
    def add_review(self, booking_id: int, reviewer_id: int, spot_id: int,
                  rating: int, comment: str = None) -> Optional[int]:
        """Добавление отзыва"""
        try:
            # Проверяем, что бронирование завершено
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT status FROM bookings WHERE id = ?
            ''', (booking_id,))
            
            booking = cursor.fetchone()
            if not booking or booking['status'] != 'completed':
                raise ValueError("Можно оставлять отзыв только к завершенным бронированиям")
            
            # Проверяем, что пользователь участвовал в бронировании
            cursor.execute('''
                SELECT user_id FROM bookings WHERE id = ?
            ''', (booking_id,))
            
            booking_user = cursor.fetchone()
            if booking_user['user_id'] != reviewer_id:
                # Проверяем, является ли пользователь владельцем
                cursor.execute('''
                    SELECT owner_id FROM parking_spots WHERE id = ?
                ''', (spot_id,))
                
                spot_owner = cursor.fetchone()
                if not spot_owner or spot_owner['owner_id'] != reviewer_id:
                    raise ValueError("Нельзя оставлять отзыв к чужому бронированию")
            
            cursor.execute('''
                INSERT INTO reviews 
                (booking_id, reviewer_id, spot_id, rating, comment)
                VALUES (?, ?, ?, ?, ?)
            ''', (booking_id, reviewer_id, spot_id, rating, comment))
            
            review_id = cursor.lastrowid
            
            # Обновляем рейтинг места
            self.update_spot_rating(spot_id)
            
            # Обновляем рейтинг владельца
            cursor.execute('''
                SELECT owner_id FROM parking_spots WHERE id = ?
            ''', (spot_id,))
            
            spot = cursor.fetchone()
            if spot:
                self.update_user_rating(spot['owner_id'])
            
            self.connection.commit()
            return review_id
        except Exception as e:
            logger.error(f"Ошибка добавления отзыва: {e}")
            return None
    
    def get_spot_reviews(self, spot_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение отзывов о месте"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT r.*, u.full_name as reviewer_name
                FROM reviews r
                JOIN users u ON r.reviewer_id = u.id
                WHERE r.spot_id = ? AND r.is_approved = 1
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?
            ''', (spot_id, limit, offset))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения отзывов: {e}")
            return []
    
    def get_user_reviews(self, user_id: int, as_reviewer: bool = True,
                        limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение отзывов пользователя"""
        try:
            cursor = self.connection.cursor()
            
            if as_reviewer:
                query = "reviewer_id = ?"
            else:
                # Получаем отзывы о местах пользователя
                query = '''
                    spot_id IN (
                        SELECT id FROM parking_spots WHERE owner_id = ?
                    )
                '''
            
            cursor.execute(f'''
                SELECT r.*, ps.spot_number, u.full_name as counterparty_name
                FROM reviews r
                JOIN parking_spots ps ON r.spot_id = ps.id
                JOIN users u ON {'r.reviewer_id' if not as_reviewer else 'ps.owner_id'} = u.id
                WHERE {query} AND r.is_approved = 1
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения отзывов пользователя: {e}")
            return []
    
    def update_spot_rating(self, spot_id: int) -> bool:
        """Обновление рейтинга места"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT AVG(rating) as avg_rating, COUNT(*) as count
                FROM reviews 
                WHERE spot_id = ? AND is_approved = 1
            ''', (spot_id,))
            
            result = cursor.fetchone()
            if result and result['count'] > 0:
                cursor.execute('''
                    UPDATE parking_spots 
                    SET rating = ?, rating_count = ?
                    WHERE id = ?
                ''', (result['avg_rating'], result['count'], spot_id))
                
                self.connection.commit()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления рейтинга места: {e}")
            return False
    
    def update_user_rating(self, user_id: int) -> bool:
        """Обновление рейтинга пользователя"""
        try:
            cursor = self.connection.cursor()
            
            # Получаем средний рейтинг всех мест пользователя
            cursor.execute('''
                SELECT AVG(ps.rating) as avg_rating
                FROM parking_spots ps
                WHERE ps.owner_id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            if result and result['avg_rating']:
                cursor.execute('''
                    UPDATE users 
                    SET rating = ?
                    WHERE id = ?
                ''', (result['avg_rating'], user_id))
                
                self.connection.commit()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления рейтинга пользователя: {e}")
            return False
    
    # ==================== ЖАЛОБЫ ====================
    
    def add_report(self, reporter_id: int, report_type: str, description: str,
                  reported_user_id: int = None, reported_spot_id: int = None,
                  booking_id: int = None) -> Optional[int]:
        """Добавление жалобы"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO reports 
                (reporter_id, reported_user_id, reported_spot_id, 
                 booking_id, report_type, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (reporter_id, reported_user_id, reported_spot_id,
                 booking_id, report_type, description))
            
            report_id = cursor.lastrowid
            self.connection.commit()
            
            # Уведомляем админов
            self.notify_admins(
                "Новая жалоба",
                f"Поступила новая жалоба #{report_id} типа: {report_type}"
            )
            
            self.add_log(reporter_id, "report_created", f"Создана жалоба #{report_id}")
            
            return report_id
        except Exception as e:
            logger.error(f"Ошибка добавления жалобы: {e}")
            return None
    
    def get_reports(self, status: str = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение списка жалоб (для админа)"""
        try:
            cursor = self.connection.cursor()
            query = '''
                SELECT r.*, 
                       u1.full_name as reporter_name,
                       u2.full_name as reported_user_name,
                       ps.spot_number as reported_spot_number
                FROM reports r
                LEFT JOIN users u1 ON r.reporter_id = u1.id
                LEFT JOIN users u2 ON r.reported_user_id = u2.id
                LEFT JOIN parking_spots ps ON r.reported_spot_id = ps.id
                WHERE 1=1
            '''
            params = []
            
            if status:
                query += " AND r.status = ?"
                params.append(status)
            
            query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения жалоб: {e}")
            return []
    
    def update_report_status(self, report_id: int, status: str, 
                            admin_notes: str = None, resolved_by: int = None) -> bool:
        """Обновление статуса жалобы"""
        try:
            cursor = self.connection.cursor()
            
            if status == 'resolved':
                cursor.execute('''
                    UPDATE reports 
                    SET status = ?, admin_notes = ?, resolved_by = ?, resolved_at = ?
                    WHERE id = ?
                ''', (status, admin_notes, resolved_by, datetime.now(), report_id))
            else:
                cursor.execute('''
                    UPDATE reports 
                    SET status = ?, admin_notes = ?
                    WHERE id = ?
                ''', (status, admin_notes, report_id))
            
            self.connection.commit()
            
            # Уведомляем автора жалобы
            cursor.execute('SELECT reporter_id FROM reports WHERE id = ?', (report_id,))
            report = cursor.fetchone()
            if report:
                self.add_notification(
                    report['reporter_id'],
                    "report_status_changed",
                    "Статус вашей жалобы изменен",
                    f"Статус жалобы #{report_id} изменен на: {status}"
                )
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления жалобы: {e}")
            return False
    
    # ==================== НАСТРОЙКИ СИСТЕМЫ ====================
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Получение значения настройки"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT value FROM system_settings WHERE key = ?
            ''', (key,))
            
            result = cursor.fetchone()
            return result['value'] if result else default
        except Exception as e:
            logger.error(f"Ошибка получения настройки: {e}")
            return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Установка значения настройки"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, str(value), datetime.now()))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка установки настройки: {e}")
            return False
    
    def get_all_settings(self) -> Dict[str, str]:
        """Получение всех настроек"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT key, value FROM system_settings')
            
            return {row['key']: row['value'] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Ошибка получения настроек: {e}")
            return {}
    
    # ==================== ЛОГИРОВАНИЕ ====================
    
    def add_log(self, user_id: int = None, action: str = "", 
               details: str = None, ip_address: str = None,
               user_agent: str = None) -> Optional[int]:
        """Добавление записи в лог"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO logs (user_id, action, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, action, details, ip_address, user_agent))
            
            log_id = cursor.lastrowid
            self.connection.commit()
            return log_id
        except Exception as e:
            logger.error(f"Ошибка добавления лога: {e}")
            return None
    
    def get_logs(self, user_id: int = None, action: str = None,
                limit: int = 100, offset: int = 0) -> List[Dict]:
        """Получение логов"""
        try:
            cursor = self.connection.cursor()
            query = "SELECT * FROM logs WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if action:
                query += " AND action = ?"
                params.append(action)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения логов: {e}")
            return []
    
    # ==================== СТАТИСТИКА ====================
    
    def get_statistics(self, period_days: int = 30) -> Dict[str, Any]:
        """Получение статистики системы"""
        stats = {}
        cutoff_date = datetime.now() - timedelta(days=period_days)
        
        try:
            cursor = self.connection.cursor()
            
            # Общая статистика
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE created_at > ?', (cutoff_date,))
            stats['new_users'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM parking_spots WHERE created_at > ?', (cutoff_date,))
            stats['new_spots'] = cursor.fetchone()['count']
            
            cursor.execute('SELECT COUNT(*) as count FROM bookings WHERE created_at > ?', (cutoff_date,))
            stats['new_bookings'] = cursor.fetchone()['count']
            
            cursor.execute('''
                SELECT COUNT(*) as count, SUM(total_price) as revenue 
                FROM bookings 
                WHERE created_at > ? AND payment_status = 'paid'
            ''', (cutoff_date,))
            bookings_data = cursor.fetchone()
            stats['paid_bookings'] = bookings_data['count']
            stats['revenue'] = bookings_data['revenue'] or 0
            
            # Статистика по статусам бронирований
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM bookings 
                WHERE created_at > ?
                GROUP BY status
            ''', (cutoff_date,))
            stats['booking_statuses'] = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Активные пользователи
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id) as count 
                FROM bookings 
                WHERE created_at > ?
            ''', (cutoff_date,))
            stats['active_users'] = cursor.fetchone()['count']
            
            # Популярные места
            cursor.execute('''
                SELECT ps.spot_number, COUNT(b.id) as bookings_count
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                WHERE b.created_at > ?
                GROUP BY b.spot_id
                ORDER BY bookings_count DESC
                LIMIT 10
            ''', (cutoff_date,))
            stats['top_spots'] = [dict(row) for row in cursor.fetchall()]
            
            # Ежедневная статистика
            cursor.execute('''
                SELECT DATE(created_at) as date, 
                       COUNT(*) as bookings,
                       SUM(total_price) as revenue
                FROM bookings
                WHERE created_at > ?
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (cutoff_date,))
            stats['daily_stats'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    # ==================== УТИЛИТЫ ====================
    
    def check_connection(self) -> bool:
        """Проверка соединения с БД"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            return True
        except:
            return False
    
    def backup_database(self, backup_path: str) -> bool:
        """Создание резервной копии БД"""
        import shutil
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"✅ Резервная копия создана: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии: {e}")
            return False
    
    def cleanup_old_data(self, days: int = 90) -> bool:
        """Очистка старых данных"""
        try:
            cursor = self.connection.cursor()
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Удаляем старые логи
            cursor.execute('DELETE FROM logs WHERE created_at < ?', (cutoff_date,))
            
            # Удаляем старые прочитанные уведомления
            cursor.execute('''
                DELETE FROM notifications 
                WHERE is_read = 1 AND created_at < ?
            ''', (cutoff_date,))
            
            # Удаляем старые админ-сессии
            cursor.execute('DELETE FROM admin_sessions WHERE expires_at < ?', (datetime.now(),))
            
            # Архивируем завершенные бронирования старше N дней
            cursor.execute('''
                UPDATE bookings 
                SET status = 'archived' 
                WHERE status = 'completed' 
                AND end_time < ?
            ''', (cutoff_date,))
            
            self.connection.commit()
            logger.info(f"✅ Очистка данных старше {days} дней выполнена")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки данных: {e}")
            return False
    
    def close(self):
        """Закрытие соединения с БД"""
        if self.connection:
            self.connection.close()
            logger.info("✅ Соединение с БД закрыто")

# Глобальный экземпляр БД

db = Database()
