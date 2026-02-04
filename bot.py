#!/usr/bin/env python3
"""
Главный файл для запуска Telegram бота парковки
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

# Импорт конфигурации и базы данных
from config import Config
from database import db

# Импорт всех обработчиков
from handlers.start import router as start_router
from handlers.spots import router as spots_router
from handlers.booking import router as booking_router
from handlers.profile import router as profile_router
from handlers.admin import router as admin_router
from handlers.utils import router as utils_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Создаем необходимые директории
def create_directories():
    """Создание необходимых директорий"""
    directories = ["logs", "backups", "data"]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"📁 Создана директория: {directory}")

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("🤖 Бот запущен и готов к работе!")
    
    # Очищаем истекшие админ-сессии при запуске
    try:
        cursor = db.connection.cursor()
        cursor.execute('DELETE FROM admin_sessions WHERE expires_at < ?', (datetime.now(),))
        db.connection.commit()
        logger.info("🧹 Очищены истекшие админ-сессии")
    except Exception as e:
        logger.error(f"Ошибка очистки админ-сессий: {e}")
    
    # Отправляем уведомление админу
    try:
        await bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"✅ <b>Бот запущен!</b>\n\n"
                 f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                 f"Версия: 1.0.0\n"
                 f"Пользователей в базе: {db.count_users()}"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление админу: {e}")
    
    logger.info("🎉 Бот успешно запущен!")

async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("🛑 Остановка бота...")
    
    # Отправляем уведомление админу
    try:
        await bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"🛑 <b>Бот остановлен!</b>\n\n"
                 f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление админу: {e}")
    
    # Закрываем соединение с базой данных
    db.close()
    logger.info("✅ Соединение с БД закрыто")

async def check_expired_bookings():
    """Проверка и завершение истекших бронирований"""
    try:
        cursor = db.connection.cursor()
        cursor.execute('''
            SELECT b.*, ps.spot_number, u.full_name as user_name
            FROM bookings b
            JOIN parking_spots ps ON b.spot_id = ps.id
            JOIN users u ON b.user_id = u.id
            WHERE b.status = 'active'
            AND b.end_time < ?
        ''', (datetime.now(),))
        
        expired_bookings = cursor.fetchall()
        
        for booking in expired_bookings:
            # Завершаем бронирование
            success = db.update_booking_status(booking['id'], 'completed')
            
            if success:
                logger.info(f"✅ Бронирование #{booking['booking_code']} завершено (время истекло)")
                
                # Отправляем уведомление пользователю
                try:
                    user = db.get_user(user_id=booking['user_id'])
                    if user:
                        db.add_notification(
                            user['id'],
                            "booking_completed",
                            "Бронирование завершено",
                            f"Ваше бронирование #{booking['booking_code']} завершено.\n"
                            f"Место: #{booking['spot_number']}\n"
                            f"Время истекло: {datetime.fromisoformat(booking['end_time']).strftime('%d.%m.%Y %H:%M')}",
                        )
                except Exception as e:
                    logger.error(f"Ошибка уведомления пользователя: {e}")
        
        if expired_bookings:
            logger.info(f"📊 Завершено {len(expired_bookings)} истекших бронирований")
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки истекших бронирований: {e}")

async def auto_cancel_unpaid_bookings():
    """Автоматическая отмена неоплаченных бронирований"""
    try:
        auto_cancel_hours = int(Config.AUTO_CANCEL_HOURS)
        cutoff_time = datetime.now() - timedelta(hours=auto_cancel_hours)
        
        cursor = db.connection.cursor()
        cursor.execute('''
            SELECT b.*, ps.spot_number, u.full_name as user_name
            FROM bookings b
            JOIN parking_spots ps ON b.spot_id = ps.id
            JOIN users u ON b.user_id = u.id
            WHERE b.status = 'pending'
            AND b.payment_status = 'pending'
            AND b.created_at < ?
        ''', (cutoff_time,))
        
        unpaid_bookings = cursor.fetchall()
        
        for booking in unpaid_bookings:
            # Отменяем бронирование
            success = db.update_booking_status(
                booking['id'],
                'cancelled',
                cancelled_by=None,
                reason=f"Автоматическая отмена: не оплачено в течение {auto_cancel_hours} часов"
            )
            
            if success:
                logger.info(f"❌ Бронирование #{booking['booking_code']} отменено (не оплачено)")
                
                # Освобождаем период
                if booking['period_id']:
                    db.release_period(booking['period_id'])
                
                # Отправляем уведомление пользователю
                try:
                    user = db.get_user(user_id=booking['user_id'])
                    if user:
                        db.add_notification(
                            user['id'],
                            "booking_cancelled",
                            "Бронирование отменено",
                            f"Ваше бронирование #{booking['booking_code']} отменено.\n"
                            f"Причина: не было оплачено в течение {auto_cancel_hours} часов.",
                        )
                except Exception as e:
                    logger.error(f"Ошибка уведомления пользователя: {e}")
        
        if unpaid_bookings:
            logger.info(f"📊 Отменено {len(unpaid_bookings)} неоплаченных бронирований")
            
    except Exception as e:
        logger.error(f"❌ Ошибка автоматической отмены бронирований: {e}")

async def background_tasks():
    """Фоновые задачи бота"""
    logger.info("🔄 Запуск фоновых задач...")
    
    while True:
        try:
            # Выполняем задачи каждые 5 минут
            await asyncio.sleep(300)  # 5 минут
            
            # 1. Очистка старых данных (раз в день)
            now = datetime.now()
            if now.hour == 3 and now.minute < 5:  # Каждый день в 3:00
                logger.info("🧹 Запуск очистки старых данных...")
                success = db.cleanup_old_data(days=90)
                if success:
                    logger.info("✅ Очистка старых данных выполнена")
                else:
                    logger.error("❌ Ошибка очистки старых данных")
            
            # 2. Проверка истекших бронирований
            await check_expired_bookings()
            
            # 3. Автоотмена неоплаченных бронирований
            await auto_cancel_unpaid_bookings()
            
            # 4. Проверка системного здоровья
            await check_system_health()
            
        except Exception as e:
            logger.error(f"❌ Ошибка в фоновой задаче: {e}")

async def check_system_health():
    """Проверка здоровья системы"""
    try:
        # Проверка базы данных
        if not db.check_connection():
            logger.error("❌ Потеряно соединение с базой данных!")
            
            # Пытаемся переподключиться
            db.connect()
            
            if db.check_connection():
                logger.info("✅ Соединение с базой данных восстановлено")
            else:
                logger.critical("❌ Не удалось восстановить соединение с базой данных!")
                return
        
        # Проверка количества пользователей
        user_count = db.count_users()
        logger.info(f"👥 Пользователей в системе: {user_count}")
        
        # Проверка активных бронирований
        active_bookings = db.count_bookings(status='active')
        logger.info(f"📋 Активных бронирований: {active_bookings}")
        
        # Проверка свободного места (если возможно)
        try:
            import shutil
            
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            
            if free_gb < 1:  # Меньше 1 ГБ свободного места
                logger.warning(f"⚠️ Мало свободного места: {free_gb} ГБ")
            
            logger.debug(f"💾 Свободное место: {free_gb} ГБ")
        except:
            pass
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья системы: {e}")

async def error_handler(exception: Exception, bot: Bot, message: Message = None):
    """Глобальный обработчик ошибок"""
    logger.error(f"❌ Необработанное исключение: {exception}")
    
    try:
        # Отправляем уведомление админу об ошибке
        await bot.send_message(
            chat_id=Config.ADMIN_ID,
            text=f"⚠️ <b>Произошла ошибка в боте!</b>\n\n"
                 f"<code>{str(exception)[:1000]}</code>\n\n"
                 f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
    except Exception as e:
        logger.error(f"❌ Не удалось отправить уведомление об ошибке: {e}")
    
    return True

async def main():
    """Основная функция запуска бота"""
    
    logger.info("=" * 50)
    logger.info("🚀 Запуск Parking Bot")
    logger.info(f"Время запуска: {datetime.now()}")
    logger.info("=" * 50)
    
    try:
        # Создаем необходимые директории
        create_directories()
        
        # Проверка токена бота
        if not Config.BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return
        
        # Проверка соединения с базой данных
        if not db.check_connection():
            logger.error("❌ Ошибка подключения к базе данных!")
            return
        
        logger.info("✅ База данных подключена")
        
        # Инициализация бота и диспетчера
        bot = Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Используем MemoryStorage для состояний
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Регистрация всех роутеров
        routers = [
            start_router,
            spots_router,
            booking_router,
            profile_router,
            admin_router,
            utils_router
        ]
        
        for router in routers:
            dp.include_router(router)
        
        logger.info("✅ Все обработчики зарегистрированы")
        
        # Регистрация обработчиков ошибок
        dp.errors.register(error_handler)
        
        # Установка обработчиков запуска и остановки
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Запускаем фоновые задачи
        asyncio.create_task(background_tasks())
        
        # Запуск поллинга
        logger.info("🔄 Запуск поллинга...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        raise

def run_bot():
    """Запуск бота с обработкой KeyboardInterrupt"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")

if __name__ == "__main__":

    run_bot()
