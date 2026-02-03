import pymysql
import logging
from config import DB_CONFIG
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        try:
            self.connection = pymysql.connect(**DB_CONFIG)
            logging.info("Database connection established")
        except Exception as e:
            logging.error(f"Database connection error: {e}")
    
    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                phone VARCHAR(20),
                is_admin BOOLEAN DEFAULT FALSE,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS parking_spots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id BIGINT,
                spot_number VARCHAR(50),
                price_per_hour DECIMAL(10, 2),
                price_per_day DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS availability (
                id INT AUTO_INCREMENT PRIMARY KEY,
                spot_id INT,
                date DATE,
                start_time TIME,
                end_time TIME,
                is_available BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                spot_id INT,
                date DATE,
                start_time TIME,
                end_time TIME,
                total_price DECIMAL(10, 2),
                status ENUM('pending', 'confirmed', 'cancelled') DEFAULT 'pending',
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (spot_id) REFERENCES parking_spots(id)
            )
            """
        ]
        
        try:
            with self.connection.cursor() as cursor:
                for query in queries:
                    cursor.execute(query)
            self.connection.commit()
            logging.info("Tables created successfully")
        except Exception as e:
            logging.error(f"Error creating tables: {e}")
    
    def add_user(self, user_id, username, first_name, phone):
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO users (user_id, username, first_name, phone) 
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                username = VALUES(username), 
                first_name = VALUES(first_name), 
                phone = VALUES(phone)
                """
                cursor.execute(sql, (user_id, username, first_name, phone))
            self.connection.commit()
            return True
        except Exception as e:
            logging.error(f"Error adding user: {e}")
            return False
    
    def add_parking_spot(self, owner_id, spot_number, price_per_hour, price_per_day):
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO parking_spots (owner_id, spot_number, price_per_hour, price_per_day)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (owner_id, spot_number, price_per_hour, price_per_day))
                self.connection.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Error adding parking spot: {e}")
            return None
    
    def add_availability(self, spot_id, date, start_time, end_time):
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO availability (spot_id, date, start_time, end_time)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (spot_id, date, start_time, end_time))
            self.connection.commit()
            return True
        except Exception as e:
            logging.error(f"Error adding availability: {e}")
            return False
    
    def get_available_spots(self, date):
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                SELECT ps.*, a.date, a.start_time, a.end_time
                FROM parking_spots ps
                JOIN availability a ON ps.id = a.spot_id
                WHERE a.date = %s AND a.is_available = TRUE
                """
                cursor.execute(sql, (date,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting available spots: {e}")
            return []
    
    def create_booking(self, user_id, spot_id, date, start_time, end_time, total_price):
        try:
            with self.connection.cursor() as cursor:
                # Check if spot is available
                check_sql = """
                SELECT id FROM availability 
                WHERE spot_id = %s AND date = %s 
                AND start_time <= %s AND end_time >= %s
                AND is_available = TRUE
                """
                cursor.execute(check_sql, (spot_id, date, start_time, end_time))
                if not cursor.fetchone():
                    return None
                
                # Create booking
                booking_sql = """
                INSERT INTO bookings (user_id, spot_id, date, start_time, end_time, total_price)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(booking_sql, (user_id, spot_id, date, start_time, end_time, total_price))
                
                # Mark as unavailable
                update_sql = """
                UPDATE availability SET is_available = FALSE
                WHERE spot_id = %s AND date = %s
                AND start_time <= %s AND end_time >= %s
                """
                cursor.execute(update_sql, (spot_id, date, start_time, end_time))
                
                self.connection.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Error creating booking: {e}")
            return None
    
    def get_user_spots(self, owner_id):
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                SELECT ps.*, 
                       (SELECT COUNT(*) FROM availability a WHERE a.spot_id = ps.id) as total_days,
                       (SELECT COUNT(*) FROM bookings b WHERE b.spot_id = ps.id AND b.status = 'confirmed') as total_bookings
                FROM parking_spots ps
                WHERE ps.owner_id = %s
                """
                cursor.execute(sql, (owner_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting user spots: {e}")
            return []
    
    def get_user_bookings(self, user_id):
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = """
                SELECT b.*, ps.spot_number, ps.price_per_hour, ps.price_per_day
                FROM bookings b
                JOIN parking_spots ps ON b.spot_id = ps.id
                WHERE b.user_id = %s
                ORDER BY b.date DESC, b.start_time DESC
                """
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting user bookings: {e}")
            return []
    
    def set_admin(self, user_id):
        try:
            with self.connection.cursor() as cursor:
                sql = "UPDATE users SET is_admin = TRUE WHERE user_id = %s"
                cursor.execute(sql, (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logging.error(f"Error setting admin: {e}")
            return False
    
    def is_admin(self, user_id):
        try:
            with self.connection.cursor() as cursor:
                sql = "SELECT is_admin FROM users WHERE user_id = %s"
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()
                return result[0] if result else False
        except Exception as e:
            logging.error(f"Error checking admin: {e}")
            return False