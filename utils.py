import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import Config
from database import db

logger = logging.getLogger(__name__)

# ==================== ВАЛИДАЦИЯ ====================

def validate_phone(phone: str) -> bool:
    """Валидация номера телефона"""
    # Убираем все нецифровые символы
    cleaned = re.sub(r'\D', '', phone)
    
    # Российские номера: 11 цифр, начинаются с 7 или 8
    if len(cleaned) == 11 and cleaned[0] in ('7', '8'):
        return True
    
    # Международный формат: +7
    if phone.startswith('+7') and len(cleaned) == 11:
        return True
    
    return False

def format_phone(phone: str) -> str:
    """Форматирование телефона в стандартный вид"""
    cleaned = re.sub(r'\D', '', phone)
    
    if len(cleaned) == 11:
        if cleaned[0] == '8':
            cleaned = '7' + cleaned[1:]
        return f'+{cleaned}'
    
    return phone

def validate_email(email: str) -> bool:
    """Валидация email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_car_plate(plate: str) -> bool:
    """Валидация номерного знака"""
    # Российские номера: А123БВ77
    pattern = r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$'
    return bool(re.match(pattern, plate.upper()))

def validate_card_number(card: str) -> Optional[str]:
    """Валидация номера банковской карты"""
    cleaned = re.sub(r'\D', '', card)
    
    if len(cleaned) not in (16, 18, 19):
        return None
    
    # Алгоритм Луна для проверки
    def luhn_check(card_number: str) -> bool:
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        
        return checksum % 10 == 0
    
    if luhn_check(cleaned):
        # Маскируем номер карты
        return f"**** {cleaned[-4:]}"
    
    return None

# ==================== ФОРМАТИРОВАНИЕ ====================

def format_price(price: float) -> str:
    """Форматирование цены"""
    return f"{price:,.2f}".replace(',', ' ').replace('.', ',')

def format_duration(hours: int) -> str:
    """Форматирование продолжительности"""
    if hours < 24:
        return f"{hours} час."
    elif hours < 168:  # 7 дней
        days = hours // 24
        return f"{days} дн."
    else:
        weeks = hours // 168
        return f"{weeks} нед."

def format_datetime(dt: datetime) -> str:
    """Форматирование даты и времени"""
    return dt.strftime("%d.%m.%Y %H:%M")

def format_date(dt: datetime) -> str:
    """Форматирование даты"""
    return dt.strftime("%d.%m.%Y")

def format_time(dt: datetime) -> str:
    """Форматирование времени"""
    return dt.strftime("%H:%M")

def format_timedelta(td: timedelta) -> str:
    """Форматирование временного интервала"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    
    if hours < 24:
        return f"{hours} часов"
    else:
        days = hours // 24
        remaining_hours = hours % 24
        
        if remaining_hours == 0:
            return f"{days} дней"
        else:
            return f"{days} дней {remaining_hours} часов"

def format_user_info(user: Dict[str, Any]) -> str:
    """Форматирование информации о пользователе"""
    info = f"👤 <b>{user['full_name']}</b>\n"
    
    if user.get('username'):
        info += f"📱 @{user['username']}\n"
    
    info += f"📞 {user['phone']}\n"
    
    if user.get('email'):
        info += f"📧 {user['email']}\n"
    
    if user.get('car_plate'):
        car_info = user['car_plate']
        if user.get('car_brand'):
            car_info = f"{user['car_brand']} {user['car_model']} ({car_info})" if user.get('car_model') else f"{user['car_brand']} ({car_info})"
        info += f"🚗 {car_info}\n"
    
    if user.get('balance'):
        info += f"💰 Баланс: {format_price(user['balance'])} ₽\n"
    
    if user.get('rating'):
        info += f"⭐ Рейтинг: {user['rating']}/5 ({user.get('rating_count', 0)} отзывов)\n"
    
    info += f"📅 Регистрация: {format_date(datetime.fromisoformat(user['created_at']))}\n"
    
    if user.get('is_admin'):
        info += "👑 <b>Администратор</b>\n"
    
    if user.get('is_blocked'):
        info += "🚫 <b>Заблокирован</b>\n"
    
    return info

def format_spot_info(spot: Dict[str, Any]) -> str:
    """Форматирование информации о месте"""
    info = f"🏠 <b>Место #{spot['spot_number']}</b>\n"
    info += f"📍 Адрес: {spot['address']}\n"
    
    if spot.get('description'):
        info += f"📝 {spot['description']}\n"
    
    info += f"💰 Цена: {format_price(spot['price_per_hour'])} ₽/час | {format_price(spot.get('price_per_day', spot['price_per_hour'] * 24))} ₽/день\n"
    
    features = []
    if spot.get('is_covered'):
        features.append("🏢 Крытая")
    if spot.get('has_cctv'):
        features.append("🎥 CCTV")
    if spot.get('has_lighting'):
        features.append("💡 Освещение")
    if spot.get('has_electricity'):
        features.append("🔌 Розетка")
    
    if features:
        info += f"✅ Особенности: {', '.join(features)}\n"
    
    if spot.get('max_car_size'):
        info += f"🚗 Макс. размер: {spot['max_car_size']}\n"
    
    if spot.get('owner_name'):
        info += f"👤 Владелец: {spot['owner_name']}\n"
        info += f"📞 Телефон: {spot.get('owner_phone', 'не указан')}\n"
    
    if spot.get('rating'):
        info += f"⭐ Рейтинг: {spot['rating']}/5 ({spot.get('rating_count', 0)} отзывов)\n"
    
    if spot.get('total_bookings'):
        info += f"📊 Бронирований: {spot['total_bookings']}\n"
    
    if spot.get('total_earnings'):
        info += f"💰 Заработано: {format_price(spot['total_earnings'])} ₽\n"
    
    return info

def format_booking_info(booking: Dict[str, Any]) -> str:
    """Форматирование информации о бронировании"""
    info = f"📋 <b>Бронирование #{booking['booking_code']}</b>\n"
    info += f"🏠 Место: #{booking['spot_number']} ({booking.get('address', '')})\n"
    info += f"👤 Клиент: {booking['user_name']} ({booking.get('user_phone', '')})\n"
    
    if booking.get('user_car_plate'):
        info += f"🚗 Автомобиль: {booking['user_car_plate']}\n"
    
    info += f"⏰ Время: {format_datetime(booking['start_time'])} - {format_datetime(booking['end_time'])}\n"
    
    duration = (datetime.fromisoformat(booking['end_time']) - datetime.fromisoformat(booking['start_time'])).total_seconds() / 3600
    info += f"📅 Продолжительность: {format_duration(duration)}\n"
    info += f"💰 Стоимость: {format_price(booking['total_price'])} ₽\n"
    info += f"📊 Статус: {get_booking_status_text(booking['status'])}\n"
    info += f"💳 Оплата: {get_payment_status_text(booking['payment_status'])}\n"
    
    if booking.get('notes'):
        info += f"📝 Примечания: {booking['notes']}\n"
    
    if booking.get('created_at'):
        info += f"📅 Создано: {format_datetime(datetime.fromisoformat(booking['created_at']))}\n"
    
    return info

def format_notification_info(notification: Dict[str, Any]) -> str:
    """Форматирование информации об уведомлении"""
    status = "✅" if notification['is_read'] else "🆕"
    info = f"{status} <b>{notification['title']}</b>\n"
    info += f"{notification['message']}\n"
    info += f"📅 {format_datetime(datetime.fromisoformat(notification['created_at']))}\n"
    
    if notification.get('data'):
        # Можно добавить дополнительные данные
        pass
    
    return info

def format_report_info(report: Dict[str, Any]) -> str:
    """Форматирование информации о жалобе"""
    info = f"⚠️ <b>Жалоба #{report['id']}</b>\n"
    info += f"📋 Тип: {get_report_type_text(report['report_type'])}\n"
    info += f"👤 От: {report['reporter_name']}\n"
    
    if report.get('reported_user_name'):
        info += f"👤 На: {report['reported_user_name']}\n"
    
    if report.get('reported_spot_number'):
        info += f"🏠 Место: #{report['reported_spot_number']}\n"
    
    info += f"📝 Описание: {report['description']}\n"
    info += f"📊 Статус: {get_report_status_text(report['status'])}\n"
    
    if report.get('admin_notes'):
        info += f"💬 Комментарий администратора: {report['admin_notes']}\n"
    
    info += f"📅 Создано: {format_datetime(datetime.fromisoformat(report['created_at']))}\n"
    
    return info

# ==================== ТЕКСТЫ СТАТУСОВ ====================

def get_booking_status_text(status: str) -> str:
    """Текст статуса бронирования"""
    statuses = {
        'pending': '⏳ Ожидание',
        'confirmed': '✅ Подтверждено',
        'active': '🚗 Активно',
        'completed': '✅ Завершено',
        'cancelled': '❌ Отменено',
        'archived': '📁 Архив'
    }
    return statuses.get(status, status)

def get_payment_status_text(status: str) -> str:
    """Текст статуса оплаты"""
    statuses = {
        'pending': '⏳ Ожидает оплаты',
        'paid': '✅ Оплачено',
        'refunded': '↩️ Возвращено',
        'failed': '❌ Ошибка'
    }
    return statuses.get(status, status)

def get_report_status_text(status: str) -> str:
    """Текст статуса жалобы"""
    statuses = {
        'pending': '⏳ Ожидает',
        'investigating': '🔍 В процессе',
        'resolved': '✅ Решено',
        'rejected': '❌ Отклонено'
    }
    return statuses.get(status, status)

def get_report_type_text(report_type: str) -> str:
    """Текст типа жалобы"""
    types = {
        'spot_issue': '🚗 Проблема с местом',
        'user_issue': '👤 Проблема с пользователем',
        'payment_issue': '💳 Проблема с оплатой',
        'booking_issue': '📅 Проблема с бронированием',
        'no_response': '📞 Не отвечает',
        'fraud': '🚫 Мошенничество',
        'other': '⚖️ Другое'
    }
    return types.get(report_type, report_type)

# ==================== РАСЧЕТЫ ====================

def calculate_booking_price(spot: Dict[str, Any], start_time: datetime, end_time: datetime) -> float:
    """Расчет стоимости бронирования"""
    duration_hours = (end_time - start_time).total_seconds() / 3600
    
    # Используем почасовую ставку
    price_per_hour = spot['price_per_hour']
    total_price = price_per_hour * duration_hours
    
    # Округляем до 2 знаков
    return round(total_price, 2)

def calculate_commission(amount: float, commission_rate: float = None) -> float:
    """Расчет комиссии"""
    if commission_rate is None:
        commission_rate = float(Config.COMMISSION_RATE)
    
    commission = amount * (commission_rate / 100)
    return round(commission, 2)

def calculate_net_amount(amount: float, commission_rate: float = None) -> float:
    """Расчет чистой суммы после комиссии"""
    commission = calculate_commission(amount, commission_rate)
    return round(amount - commission, 2)

# ==================== ПРОВЕРКИ ДОСТУПА ====================

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    user = db.get_user(telegram_id=user_id)
    return user and user['is_admin']

def is_blocked(user_id: int) -> bool:
    """Проверка, заблокирован ли пользователь"""
    user = db.get_user(telegram_id=user_id)
    return user and user['is_blocked']

def is_spot_owner(user_id: int, spot_id: int) -> bool:
    """Проверка, является ли пользователь владельцем места"""
    user = db.get_user(telegram_id=user_id)
    if not user:
        return False
    
    spot = db.get_parking_spot(spot_id)
    return spot and spot['owner_id'] == user['id']

def is_booking_owner(user_id: int, booking_id: int) -> bool:
    """Проверка, является ли пользователь владельцем бронирования"""
    user = db.get_user(telegram_id=user_id)
    if not user:
        return False
    
    booking = db.get_booking(booking_id)
    return booking and booking['user_id'] == user['id']

# ==================== УВЕДОМЛЕНИЯ ====================

async def notify_user(telegram_id: int, title: str, message: str, 
                     notification_type: str = "system", data: dict = None):
    """Отправка уведомления пользователю"""
    try:
        user = db.get_user(telegram_id=telegram_id)
        if not user:
            return False
        
        db.add_notification(
            user['id'],
            notification_type,
            title,
            message,
            data
        )
        
        logger.info(f"Уведомление отправлено пользователю {telegram_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        return False

async def notify_spot_owners_new_booking(booking_id: int):
    """Уведомление владельцев мест о новом бронировании"""
    try:
        booking = db.get_booking(booking_id)
        if not booking:
            return False
        
        spot = db.get_parking_spot(booking['spot_id'])
        if not spot:
            return False
        
        await notify_user(
            spot['owner_telegram_id'],
            "Новое бронирование",
            f"Ваше место #{spot['spot_number']} забронировано.\n"
            f"Код брони: {booking['booking_code']}\n"
            f"Время: {format_datetime(booking['start_time'])} - {format_datetime(booking['end_time'])}",
            "new_booking"
        )
        
        return True
    except Exception as e:
        logger.error(f"Ошибка уведомления владельца: {e}")
        return False

async def notify_user_booking_confirmed(booking_id: int):
    """Уведомление пользователя о подтверждении бронирования"""
    try:
        booking = db.get_booking(booking_id)
        if not booking:
            return False
        
        user = db.get_user(user_id=booking['user_id'])
        if not user:
            return False
        
        await notify_user(
            user['telegram_id'],
            "Бронирование подтверждено",
            f"Ваше бронирование #{booking['booking_code']} подтверждено владельцем.\n"
            f"Место: #{booking['spot_number']}\n"
            f"Время: {format_datetime(booking['start_time'])} - {format_datetime(booking['end_time'])}",
            "booking_confirmed"
        )
        
        return True
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
        return False

async def notify_admins_about_event(event_type: str, message: str, data: dict = None):
    """Уведомление всех администраторов о событии"""
    try:
        admins = db.get_all_users(is_admin=True)
        
        for admin in admins:
            await notify_user(
                admin['telegram_id'],
                f"Системное уведомление: {event_type}",
                message,
                "admin_notification",
                data
            )
        
        logger.info(f"Админы уведомлены о событии: {event_type}")
        return len(admins)
    except Exception as e:
        logger.error(f"Ошибка уведомления админов: {e}")
        return 0

# ==================== ВРЕМЕННЫЕ ФУНКЦИИ ====================

def parse_datetime(date_str: str, time_str: str = "00:00") -> Optional[datetime]:
    """Парсинг даты и времени из строк"""
    try:
        # Формат даты: DD.MM.YYYY
        if '.' in date_str:
            date_format = "%d.%m.%Y"
        elif '-' in date_str:
            date_format = "%Y-%m-%d"
        else:
            return None
        
        date_obj = datetime.strptime(date_str, date_format)
        
        if time_str:
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            return datetime.combine(date_obj.date(), time_obj)
        
        return date_obj
    except Exception as e:
        logger.error(f"Ошибка парсинга даты: {e}")
        return None

def parse_duration(duration_str: str) -> Optional[int]:
    """Парсинг продолжительности"""
    try:
        # Форматы: "2 часа", "3ч", "1 день", "24h"
        duration_str = duration_str.lower().strip()
        
        # Убираем нецифровые символы кроме точки
        numbers = re.findall(r'\d+', duration_str)
        if not numbers:
            return None
        
        hours = int(numbers[0])
        
        if 'день' in duration_str or 'ден' in duration_str or 'дн' in duration_str:
            hours *= 24
        elif 'недел' in duration_str or 'нед' in duration_str or 'week' in duration_str:
            hours *= 168
        elif 'месяц' in duration_str or 'мес' in duration_str or 'month' in duration_str:
            hours *= 720  # 30 дней
        
        return hours
    except Exception as e:
        logger.error(f"Ошибка парсинга продолжительности: {e}")
        return None

def get_available_time_slots(spot_id: int, date: datetime) -> List[Dict[str, datetime]]:
    """Получение доступных временных слотов для места на указанную дату"""
    try:
        # Начало и конец дня
        start_of_day = datetime.combine(date.date(), datetime.min.time())
        end_of_day = datetime.combine(date.date(), datetime.max.time())
        
        # Получаем бронирования на этот день
        cursor = db.connection.cursor()
        cursor.execute('''
            SELECT start_time, end_time 
            FROM bookings 
            WHERE spot_id = ? 
            AND status IN ('confirmed', 'active')
            AND DATE(start_time) = DATE(?)
            ORDER BY start_time
        ''', (spot_id, date))
        
        bookings = cursor.fetchall()
        
        # Начинаем с начала дня
        current_time = start_of_day
        slots = []
        
        for booking in bookings:
            booking_start = datetime.fromisoformat(booking['start_time'])
            booking_end = datetime.fromisoformat(booking['end_time'])
            
            # Если есть промежуток до бронирования
            if current_time < booking_start:
                slots.append({
                    'start': current_time,
                    'end': booking_start
                })
            
            current_time = booking_end
        
        # Добавляем слот от последнего бронирования до конца дня
        if current_time < end_of_day:
            slots.append({
                'start': current_time,
                'end': end_of_day
            })
        
        # Фильтруем слоты по минимальной продолжительности
        min_duration = timedelta(hours=Config.MIN_BOOKING_HOURS)
        slots = [slot for slot in slots if (slot['end'] - slot['start']) >= min_duration]
        
        return slots
    except Exception as e:
        logger.error(f"Ошибка получения временных слотов: {e}")
        return []

# ==================== КЭШИРОВАНИЕ ====================

class Cache:
    """Простой кэш"""
    _cache = {}
    
    @classmethod
    def get(cls, key: str, default=None):
        return cls._cache.get(key, default)
    
    @classmethod
    def set(cls, key: str, value, ttl: int = 300):
        """Установка значения с временем жизни (секунды)"""
        expire_time = datetime.now() + timedelta(seconds=ttl)
        cls._cache[key] = {
            'value': value,
            'expire': expire_time
        }
    
    @classmethod
    def delete(cls, key: str):
        cls._cache.pop(key, None)
    
    @classmethod
    def clear_expired(cls):
        """Очистка просроченных записей"""
        now = datetime.now()
        expired_keys = [
            key for key, data in cls._cache.items()
            if data['expire'] < now
        ]
        
        for key in expired_keys:
            cls.delete(key)

# ==================== ЛОГГИРОВАНИЕ ====================

def setup_logging():
    """Настройка логирования"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Создаем директорию для логов
    import os
    os.makedirs('logs', exist_ok=True)

def log_user_action(user_id: int, action: str, details: str = None):
    """Логирование действий пользователя"""
    try:
        db.add_log(user_id, action, details)
        logger.info(f"Действие пользователя {user_id}: {action} - {details}")
    except Exception as e:
        logger.error(f"Ошибка логирования действия: {e}")

# ==================== ОЧИСТКА ДАННЫХ ====================

async def cleanup_old_data():
    """Очистка старых данных"""
    try:
        # Очищаем старые бронирования
        cutoff_date = datetime.now() - timedelta(days=90)
        
        cursor = db.connection.cursor()
        cursor.execute('''
            UPDATE bookings 
            SET status = 'archived' 
            WHERE status = 'completed' 
            AND end_time < ?
        ''', (cutoff_date,))
        
        # Очищаем старые уведомления
        cursor.execute('''
            DELETE FROM notifications 
            WHERE is_read = 1 
            AND created_at < ?
        ''', (cutoff_date,))
        
        db.connection.commit()
        
        # Очищаем кэш
        Cache.clear_expired()
        
        logger.info("Очистка старых данных выполнена")
        return True
    except Exception as e:
        logger.error(f"Ошибка очистки данных: {e}")
        return False

# ==================== СТАТИСТИКА ====================

def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Получение статистики пользователя"""
    stats = {}
    
    try:
        user = db.get_user(telegram_id=user_id)
        if not user:
            return stats
        
        cursor = db.connection.cursor()
        
        # Бронирования
        cursor.execute('''
            SELECT 
                COUNT(*) as total_bookings,
                SUM(total_price) as total_spent,
                AVG(total_price) as avg_booking_price,
                SUM(total_hours) as total_hours
            FROM bookings 
            WHERE user_id = ?
        ''', (user['id'],))
        
        booking_stats = cursor.fetchone()
        if booking_stats:
            stats['total_bookings'] = booking_stats['total_bookings'] or 0
            stats['total_spent'] = booking_stats['total_spent'] or 0
            stats['avg_booking_price'] = booking_stats['avg_booking_price'] or 0
            stats['total_hours'] = booking_stats['total_hours'] or 0
        
        # Места
        cursor.execute('''
            SELECT 
                COUNT(*) as total_spots,
                SUM(total_earnings) as total_earnings,
                AVG(rating) as avg_spot_rating
            FROM parking_spots 
            WHERE owner_id = ? AND is_active = 1
        ''', (user['id'],))
        
        spot_stats = cursor.fetchone()
        if spot_stats:
            stats['total_spots'] = spot_stats['total_spots'] or 0
            stats['total_earnings'] = spot_stats['total_earnings'] or 0
            stats['avg_spot_rating'] = spot_stats['avg_spot_rating'] or 0
        
        # Отзывы
        cursor.execute('''
            SELECT 
                COUNT(*) as total_reviews,
                AVG(rating) as avg_review_rating
            FROM reviews 
            WHERE reviewee_id = ?
        ''', (user['id'],))
        
        review_stats = cursor.fetchone()
        if review_stats:
            stats['total_reviews'] = review_stats['total_reviews'] or 0
            stats['avg_review_rating'] = review_stats['avg_review_rating'] or 0
        
        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователя: {e}")
        return stats

def format_stats(stats: Dict[str, Any]) -> str:
    """Форматирование статистики"""
    if not stats:
        return "Статистика недоступна"
    
    formatted = "📊 <b>Статистика:</b>\n\n"
    
    if 'total_bookings' in stats:
        formatted += f"📋 Бронирований: {stats['total_bookings']}\n"
    
    if 'total_spent' in stats:
        formatted += f"💰 Потрачено: {format_price(stats['total_spent'])} ₽\n"
    
    if 'total_earnings' in stats:
        formatted += f"💵 Заработано: {format_price(stats['total_earnings'])} ₽\n"
    
    if 'total_spots' in stats:
        formatted += f"🏠 Мест: {stats['total_spots']}\n"
    
    if 'total_hours' in stats:
        formatted += f"⏰ Всего часов: {stats['total_hours']}\n"
    
    if 'avg_booking_price' in stats and stats['avg_booking_price']:
        formatted += f"📈 Средний чек: {format_price(stats['avg_booking_price'])} ₽\n"
    
    if 'avg_spot_rating' in stats and stats['avg_spot_rating']:
        formatted += f"⭐ Средний рейтинг мест: {stats['avg_spot_rating']:.1f}/5\n"
    
    if 'avg_review_rating' in stats and stats['avg_review_rating']:
        formatted += f"🌟 Средний рейтинг: {stats['avg_review_rating']:.1f}/5\n"
    
    if 'total_reviews' in stats:
        formatted += f"📝 Отзывов: {stats['total_reviews']}\n"
    
    return formatted