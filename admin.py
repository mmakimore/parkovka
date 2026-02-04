"""
Обработчики для админ-панели с новой системой прав (пароль qwerty123)
"""

import logging
import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from config import Config
from database import db
from keyboards import main as kb_main
from keyboards import inline as kb_inline
from handlers.utils import (
    log_user_action, format_user_info,
    format_spot_info, format_booking_info,
    format_report_info, format_price,
    notify_user
)

logger = logging.getLogger(__name__)
router = Router()

# ==================== СОСТОЯНИЯ АДМИНА ====================

class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    searching_user = State()
    messaging_user = State()
    system_settings = State()
    managing_reports = State()
    viewing_stats = State()
    changing_password = State()
    broadcasting_message = State()

# ==================== ПРОВЕРКА ДОСТУПА ====================

def check_admin_access(user_id: int) -> bool:
    """Проверка доступа пользователя к админ-панели"""
    return db.is_admin_user(user_id)

async def require_admin(message: Message = None, callback: CallbackQuery = None):
    """Декоратор для проверки прав администратора"""
    user_id = message.from_user.id if message else callback.from_user.id
    
    if not check_admin_access(user_id):
        if message:
            await message.answer(
                "❌ <b>Доступ запрещен!</b>\n\n"
                "У вас нет прав администратора.\n\n"
                "Используйте команду /admin для входа в админ-панель.",
                reply_markup=kb_main.get_main_menu(telegram_id=user_id, db_instance=db)
            )
        else:
            await callback.answer("❌ Нет доступа к админ-панели")
        return False
    return True

# ==================== АДМИН ПАНЕЛЬ ====================

@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    """Главное меню админ-панели"""
    if not await require_admin(message):
        return
    
    # Получаем статистику
    stats = db.get_system_stats()
    
    # Получаем информацию о пользователе
    user = db.get_user(telegram_id=message.from_user.id)
    
    # Форматируем приветствие
    admin_type = "👑 Постоянный администратор" if user.get('is_admin') else "🔐 Временная админ-сессия"
    
    # Проверяем сессию
    session_info = ""
    if not user.get('is_admin'):
        session = db.get_admin_session(user['id'])
        if session:
            expires_at = datetime.fromisoformat(session['expires_at'])
            time_left = expires_at - datetime.now()
            hours_left = max(0, time_left.total_seconds() / 3600)
            session_info = f"\n⏰ Осталось времени: {hours_left:.1f} часов"
    
    welcome_text = (
        f"{admin_type}\n\n"
        f"📊 <b>Статистика системы:</b>\n"
        f"👥 Пользователей: {stats.get('total_users', 0)}\n"
        f"🏠 Мест: {stats.get('total_spots', 0)}\n"
        f"📋 Бронирований: {stats.get('total_bookings', 0)}\n"
        f"💰 Выручка: {format_price(stats.get('total_revenue', 0))} ₽\n"
        f"{session_info}\n\n"
        f"👇 <b>Выберите раздел:</b>"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=kb_main.get_admin_menu()
    )

# ==================== СТАТИСТИКА ====================

@router.message(F.text == "📊 Статистика")
async def admin_statistics(message: Message):
    """Детальная статистика системы"""
    if not await require_admin(message):
        return
    
    # Получаем статистику
    stats = db.get_system_stats()
    period_stats = db.get_statistics(period_days=30)
    
    # Форматируем детальную статистику
    text = (
        f"📊 <b>Детальная статистика системы</b>\n\n"
        
        f"<b>👥 Пользователи:</b>\n"
        f"• Всего: {stats.get('total_users', 0)}\n"
        f"• Администраторов: {len([u for u in db.get_all_users(is_admin=True)])}\n"
        f"• Заблокированных: {len([u for u in db.get_all_users(is_blocked=True)])}\n"
        f"• Новых за месяц: {period_stats.get('new_users', 0)}\n\n"
        
        f"<b>🏠 Парковочные места:</b>\n"
        f"• Всего: {stats.get('total_spots', 0)}\n"
        f"• Активных: {stats.get('active_spots', stats.get('total_spots', 0))}\n"
        f"• Новых за месяц: {period_stats.get('new_spots', 0)}\n"
        f"• Средняя цена: {format_price(stats.get('avg_hourly_price', 0))} ₽/час\n"
        f"• Средний рейтинг: {stats.get('avg_spot_rating', 0):.1f}/5\n\n"
        
        f"<b>📋 Бронирования:</b>\n"
        f"• Всего: {stats.get('total_bookings', 0)}\n"
        f"• Активных: {stats.get('active_bookings', 0)}\n"
        f"• Завершенных: {stats.get('completed_bookings', 0)}\n"
        f"• Отмененных: {stats.get('cancelled_bookings', 0)}\n"
        f"• Новых за месяц: {period_stats.get('new_bookings', 0)}\n"
        f"• Средний чек: {format_price(stats.get('avg_booking_price', 0))} ₽\n"
        f"• Общая выручка: {format_price(stats.get('total_revenue', 0))} ₽\n\n"
        
        f"<b>💳 Финансы:</b>\n"
        f"• Выручка за месяц: {format_price(period_stats.get('revenue', 0))} ₽\n"
        f"• Оплаченных бронирований: {period_stats.get('paid_bookings', 0)}\n"
        f"• Средняя сумма оплаты: {format_price(period_stats.get('avg_amount', 0))} ₽\n\n"
        
        f"<b>⚠️ Модерация:</b>\n"
        f"• Активных жалоб: {len([r for r in db.get_reports(status='pending')])}\n"
        f"• Всего жалоб: {len(db.get_reports())}\n"
        f"• Отзывов на модерации: {len([r for r in db.get_user_reviews(0, limit=1000) if not r.get('is_approved', True)])}\n\n"
        
        f"<b>📈 Активность за 30 дней:</b>\n"
        f"• Активных пользователей: {stats.get('active_users', 0)}\n"
        f"• Всего часов бронирования: {period_stats.get('total_hours_booked', 0)}\n"
        f"• Среднее время бронирования: {period_stats.get('avg_duration', 0):.1f} часов\n"
    )
    
    # Добавляем графики или дополнительные данные, если есть
    if period_stats.get('daily_stats'):
        text += f"\n<b>📅 Ежедневная статистика (последние 7 дней):</b>\n"
        for day in period_stats['daily_stats'][-7:]:
            date = datetime.strptime(day['date'], '%Y-%m-%d').strftime('%d.%m')
            bookings = day.get('bookings', 0)
            revenue = day.get('revenue', 0)
            text += f"• {date}: {bookings} броней, {format_price(revenue)} ₽\n"
    
    # Кнопки для обновления и экспорта
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="refresh_stats"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📊 Графики",
        callback_data="show_charts"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📁 Экспорт данных",
        callback_data="export_stats"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_admin"
    ))
    keyboard.adjust(2, 1, 1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

# ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================

@router.message(F.text == "👥 Пользователи")
async def admin_users(message: Message):
    """Управление пользователями"""
    if not await require_admin(message):
        return
    
    await message.answer(
        "👥 <b>Управление пользователями</b>\n\n"
        "Выберите действие:",
        reply_markup=kb_main.get_admin_users_keyboard()
    )

@router.message(F.text == "👥 Все пользователи")
async def all_users(message: Message):
    """Список всех пользователей"""
    if not await require_admin(message):
        return
    
    users = db.get_all_users(limit=20)
    
    if not users:
        await message.answer("📭 Нет пользователей")
        return
    
    text = "👥 <b>Все пользователи</b>\n\n"
    
    for i, user in enumerate(users, 1):
        status = "👑" if user['is_admin'] else "✅" if not user['is_blocked'] else "🚫"
        text += f"{status} <b>{i}. {user['full_name']}</b>\n"
        text += f"   📱 @{user['username'] or 'нет'}\n" if user['username'] else ""
        text += f"   📞 {user['phone']}\n"
        text += f"   📅 {datetime.fromisoformat(user['created_at']).strftime('%d.%m.%Y')}\n"
        text += f"   💰 Баланс: {format_price(user['balance'])} ₽\n\n"
    
    # Кнопки пагинации
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔍 Поиск пользователя",
        callback_data="search_user"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📋 Экспорт списка",
        callback_data="export_users"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_users"
    ))
    keyboard.adjust(1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

@router.message(F.text == "🔍 Поиск пользователя")
async def search_user_start(message: Message, state: FSMContext):
    """Поиск пользователя"""
    if not await require_admin(message):
        return
    
    await state.set_state(AdminStates.searching_user)
    await message.answer(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите:\n"
        "• ID пользователя\n"
        "• Номер телефона\n"
        "• Имя пользователя\n"
        "• Email\n\n"
        "Или отправьте /cancel для отмены",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(AdminStates.searching_user)
async def search_user_process(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    try:
        search_term = message.text.strip()
        
        # Пытаемся найти пользователя разными способами
        user = None
        
        # По ID
        if search_term.isdigit():
            user = db.get_user(user_id=int(search_term))
            if not user:
                user = db.get_user(telegram_id=int(search_term))
        
        # По телефону
        if not user:
            user = db.get_user_by_phone(search_term)
        
        # По username (без @)
        if not user and search_term.startswith('@'):
            search_term = search_term[1:]
        
        # Ищем в базе по имени или email
        if not user:
            # Ищем по имени
            all_users = db.get_all_users(limit=1000)
            for u in all_users:
                if (search_term.lower() in u['full_name'].lower() or 
                    (u['email'] and search_term.lower() in u['email'].lower()) or
                    (u['username'] and search_term.lower() in u['username'].lower())):
                    user = u
                    break
        
        if not user:
            await message.answer(
                "❌ <b>Пользователь не найден</b>\n\n"
                "Попробуйте другой поисковый запрос.",
                reply_markup=kb_main.get_admin_users_keyboard()
            )
            await state.clear()
            return
        
        # Показываем информацию о пользователе
        user_info = format_user_info(user)
        
        # Получаем статистику пользователя
        cursor = db.connection.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total_bookings,
                SUM(total_price) as total_spent
            FROM bookings 
            WHERE user_id = ?
        ''', (user['id'],))
        
        booking_stats = cursor.fetchone()
        
        stats_text = "📊 <b>Статистика пользователя:</b>\n"
        if booking_stats:
            stats_text += f"• Бронирований: {booking_stats['total_bookings'] or 0}\n"
            stats_text += f"• Потрачено: {format_price(booking_stats['total_spent'] or 0)} ₽\n"
        
        # Кнопки управления
        keyboard = kb_inline.InlineKeyboardBuilder()
        
        if user['is_admin']:
            keyboard.add(kb_inline.InlineKeyboardButton(
                text="👑 Снять админа",
                callback_data=f"remove_admin_{user['id']}"
            ))
        else:
            keyboard.add(kb_inline.InlineKeyboardButton(
                text="👑 Назначить админом",
                callback_data=f"make_admin_{user['id']}"
            ))
        
        if user['is_blocked']:
            keyboard.add(kb_inline.InlineKeyboardButton(
                text="✅ Разблокировать",
                callback_data=f"unblock_user_{user['id']}"
            ))
        else:
            keyboard.add(kb_inline.InlineKeyboardButton(
                text="🚫 Заблокировать",
                callback_data=f"block_user_{user['id']}"
            ))
        
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="✉️ Написать сообщение",
            callback_data=f"message_user_{user['id']}"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="📊 Подробная статистика",
            callback_data=f"user_stats_{user['id']}"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_users_list"
        ))
        keyboard.adjust(2, 2, 1, 1)
        
        await message.answer(
            f"{user_info}\n\n{stats_text}",
            reply_markup=keyboard.as_markup()
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка поиска пользователя: {e}")
        await message.answer(
            "❌ Произошла ошибка при поиске",
            reply_markup=kb_main.get_admin_users_keyboard()
        )
        await state.clear()

# ==================== УПРАВЛЕНИЕ МЕСТАМИ ====================

@router.message(F.text == "🏠 Места")
async def admin_spots(message: Message):
    """Управление местами"""
    if not await require_admin(message):
        return
    
    # Статистика по местам
    spots = db.get_all_spots(limit=10)
    
    text = "🏠 <b>Управление парковочными местами</b>\n\n"
    
    if spots:
        text += "<b>Последние добавленные места:</b>\n\n"
        for spot in spots:
            owner = db.get_user(user_id=spot['owner_id'])
            owner_name = owner['full_name'] if owner else "Неизвестно"
            
            text += f"📍 <b>#{spot['spot_number']}</b>\n"
            text += f"   👤 Владелец: {owner_name}\n"
            text += f"   📍 {spot['address'][:50]}...\n"
            text += f"   💰 {format_price(spot['price_per_hour'])} ₽/час\n"
            text += f"   📊 {spot['total_bookings']} бронирований\n"
            text += f"   💵 {format_price(spot['total_earnings'])} ₽\n\n"
    else:
        text += "📭 Нет добавленных мест\n\n"
    
    # Общая статистика
    total_spots = db.count_spots()
    active_spots = db.count_spots(is_active=True)
    
    text += f"<b>Общая статистика:</b>\n"
    text += f"• Всего мест: {total_spots}\n"
    text += f"• Активных: {active_spots}\n"
    text += f"• Неактивных: {total_spots - active_spots}\n\n"
    
    text += "👇 <b>Выберите действие:</b>"
    
    # Клавиатура
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔍 Поиск мест",
        callback_data="search_spots"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📋 Список всех мест",
        callback_data="list_all_spots"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="⚠️ Проблемные места",
        callback_data="problem_spots"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📊 Статистика по местам",
        callback_data="spots_stats"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_admin"
    ))
    keyboard.adjust(2, 2, 1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

# ==================== УПРАВЛЕНИЕ БРОНИРОВАНИЯМИ ====================

@router.message(F.text == "📋 Бронирования")
async def admin_bookings(message: Message):
    """Управление бронированиями"""
    if not await require_admin(message):
        return
    
    # Активные бронирования
    active_bookings = db.get_active_bookings()
    
    text = "📋 <b>Управление бронированиями</b>\n\n"
    
    if active_bookings:
        text += "<b>Активные бронирования:</b>\n\n"
        for booking in active_bookings[:5]:  # Ограничиваем 5
            time_left = datetime.fromisoformat(booking['end_time']) - datetime.now()
            hours_left = max(0, time_left.total_seconds() / 3600)
            
            text += f"📅 <b>#{booking['booking_code']}</b>\n"
            text += f"   🏠 Место: #{booking['spot_number']}\n"
            text += f"   👤 Клиент: {booking['user_name']}\n"
            text += f"   ⏰ Осталось: {hours_left:.1f} часов\n"
            text += f"   💰 Сумма: {format_price(booking['total_price'])} ₽\n\n"
    else:
        text += "✅ Нет активных бронирований\n\n"
    
    # Статистика
    total_bookings = db.count_bookings()
    active_bookings_count = db.count_bookings(status='active')
    completed_bookings = db.count_bookings(status='completed')
    cancelled_bookings = db.count_bookings(status='cancelled')
    
    text += f"<b>Общая статистика:</b>\n"
    text += f"• Всего бронирований: {total_bookings}\n"
    text += f"• Активных: {active_bookings_count}\n"
    text += f"• Завершенных: {completed_bookings}\n"
    text += f"• Отмененных: {cancelled_bookings}\n\n"
    
    text += "👇 <b>Выберите действие:</b>"
    
    # Клавиатура
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔍 Поиск бронирований",
        callback_data="search_bookings"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📋 Все бронирования",
        callback_data="list_all_bookings"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="⚠️ Проблемные брони",
        callback_data="problem_bookings"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📊 Финансовая статистика",
        callback_data="finance_stats_bookings"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_admin"
    ))
    keyboard.adjust(2, 2, 1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

# ==================== УПРАВЛЕНИЕ ЖАЛОБАМИ ====================

@router.message(F.text == "⚠️ Жалобы")
async def admin_reports(message: Message):
    """Управление жалобами"""
    if not await require_admin(message):
        return
    
    # Новые жалобы
    new_reports = db.get_reports(status='pending', limit=5)
    
    text = "⚠️ <b>Управление жалобами</b>\n\n"
    
    if new_reports:
        text += f"<b>Новые жалобы ({len(new_reports)}):</b>\n\n"
        for report in new_reports:
            text += f"🚨 <b>Жалоба #{report['id']}</b>\n"
            text += f"   👤 От: {report['reporter_name']}\n"
            text += f"   📋 Тип: {report['report_type']}\n"
            text += f"   📅 {datetime.fromisoformat(report['created_at']).strftime('%d.%m %H:%M')}\n\n"
    else:
        text += "✅ Нет новых жалоб\n\n"
    
    # Статистика
    pending_reports = len(db.get_reports(status='pending'))
    investigating_reports = len(db.get_reports(status='investigating'))
    resolved_reports = len(db.get_reports(status='resolved'))
    rejected_reports = len(db.get_reports(status='rejected'))
    
    text += f"<b>Статистика жалоб:</b>\n"
    text += f"• Ожидают: {pending_reports}\n"
    text += f"• В процессе: {investigating_reports}\n"
    text += f"• Решено: {resolved_reports}\n"
    text += f"• Отклонено: {rejected_reports}\n"
    text += f"• Всего: {pending_reports + investigating_reports + resolved_reports + rejected_reports}\n\n"
    
    text += "👇 <b>Выберите действие:</b>"
    
    await message.answer(
        text,
        reply_markup=kb_main.get_admin_reports_keyboard()
    )

@router.message(F.text == "⚠️ Новые жалобы")
async def new_reports_list(message: Message):
    """Список новых жалоб"""
    if not await require_admin(message):
        return
    
    reports = db.get_reports(status='pending', limit=20)
    
    if not reports:
        await message.answer(
            "✅ <b>Нет новых жалоб</b>\n\n"
            "Все жалобы обработаны.",
            reply_markup=kb_main.get_admin_reports_keyboard()
        )
        return
    
    text = "⚠️ <b>Новые жалобы</b>\n\n"
    
    for i, report in enumerate(reports, 1):
        text += f"<b>{i}. Жалоба #{report['id']}</b>\n"
        text += f"👤 От: {report['reporter_name']}\n"
        
        if report['reported_user_name']:
            text += f"👤 На: {report['reported_user_name']}\n"
        
        if report['reported_spot_number']:
            text += f"🏠 Место: #{report['reported_spot_number']}\n"
        
        text += f"📋 Тип: {report['report_type']}\n"
        text += f"📅 {datetime.fromisoformat(report['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
    
    # Кнопки пагинации и действий
    keyboard = kb_inline.InlineKeyboardBuilder()
    
    if len(reports) > 0:
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="📝 Обработать первую",
            callback_data=f"view_report_{reports[0]['id']}"
        ))
    
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📋 Все жалобы",
        callback_data="list_all_reports"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_reports"
    ))
    keyboard.adjust(1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

@router.callback_query(F.data.startswith("view_report_"))
async def view_report_detail(callback: CallbackQuery):
    """Просмотр деталей жалобы"""
    if not await require_admin(callback=callback):
        return
    
    report_id = int(callback.data.split("_")[2])
    
    # Ищем отчет по ID
    all_reports = db.get_reports(limit=1000)
    report = None
    for r in all_reports:
        if r['id'] == report_id:
            report = r
            break
    
    if not report:
        await callback.answer("❌ Жалоба не найдена")
        return
    
    # Форматируем информацию о жалобе
    report_info = format_report_info(report)
    
    # Кнопки действий
    keyboard = kb_inline.InlineKeyboardBuilder()
    
    if report['status'] == 'pending':
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="🔍 Взять в работу",
            callback_data=f"investigate_report_{report_id}"
        ))
    
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="✅ Решено",
        callback_data=f"resolve_report_{report_id}"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="❌ Отклонено",
        callback_data=f"reject_report_{report_id}"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="✉️ Ответить автору",
        callback_data=f"reply_report_{report_id}"
    ))
    
    if report['reported_user_id']:
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="👤 Просмотреть пользователя",
            callback_data=f"view_user_{report['reported_user_id']}"
        ))
    
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад к списку",
        callback_data="back_to_reports_list"
    ))
    keyboard.adjust(2, 2, 1, 1)
    
    await callback.message.edit_text(
        report_info,
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("resolve_report_"))
async def resolve_report(callback: CallbackQuery):
    """Решение жалобы"""
    if not await require_admin(callback=callback):
        return
    
    report_id = int(callback.data.split("_")[2])
    
    # Обновляем статус
    success = db.update_report_status(
        report_id,
        status='resolved',
        admin_notes=f"Решено администратором {callback.from_user.username or callback.from_user.id}",
        resolved_by=db.get_user(telegram_id=callback.from_user.id)['id']
    )
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Жалоба #{report_id} отмечена как решенная</b>\n\n"
            f"Статус жалобы изменен. Автор уведомлен.",
            reply_markup=kb_inline.InlineKeyboardBuilder()
                .add(kb_inline.InlineKeyboardButton(
                    text="🔙 Назад к жалобам",
                    callback_data="back_to_reports"
                ))
                .adjust(1)
                .as_markup()
        )
        
        # Логируем действие
        log_user_action(
            db.get_user(telegram_id=callback.from_user.id)['id'],
            "report_resolved",
            f"Жалоба #{report_id} решена"
        )
    else:
        await callback.answer("❌ Ошибка обновления статуса")
    
    await callback.answer()

# ==================== ФИНАНСЫ ====================

@router.message(F.text == "💰 Финансы")
async def admin_finance(message: Message):
    """Финансовая статистика"""
    if not await require_admin(message):
        return
    
    # Получаем финансовую статистику
    cursor = db.connection.cursor()
    cursor.execute('''
        SELECT 
            COUNT(*) as total_payments,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount,
            SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) as completed_amount,
            SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as pending_amount
        FROM payments
        WHERE created_at > ?
    ''', (datetime.now() - timedelta(days=30),))
    
    payment_stats = cursor.fetchone()
    
    text = "💰 <b>Финансовая статистика</b>\n\n"
    
    text += f"<b>За последние 30 дней:</b>\n"
    text += f"• Всего платежей: {payment_stats.get('total_payments', 0)}\n"
    text += f"• Общая сумма: {format_price(payment_stats.get('total_amount', 0))} ₽\n"
    text += f"• Средний платеж: {format_price(payment_stats.get('avg_amount', 0))} ₽\n"
    text += f"• Завершенных платежей: {format_price(payment_stats.get('completed_amount', 0))} ₽\n"
    text += f"• Ожидающих платежей: {format_price(payment_stats.get('pending_amount', 0))} ₽\n\n"
    
    # Получаем последние платежи
    cursor.execute('''
        SELECT p.*, u.full_name as user_name, b.booking_code
        FROM payments p
        LEFT JOIN users u ON p.user_id = u.id
        LEFT JOIN bookings b ON p.booking_id = b.id
        ORDER BY p.created_at DESC
        LIMIT 5
    ''')
    recent_payments = [dict(row) for row in cursor.fetchall()]
    
    if recent_payments:
        text += "<b>Последние платежи:</b>\n\n"
        for payment in recent_payments:
            text += f"💳 <b>{payment['transaction_id']}</b>\n"
            text += f"   👤 {payment['user_name']}\n"
            text += f"   💰 {format_price(payment['amount'])} ₽\n"
            text += f"   📅 {datetime.fromisoformat(payment['created_at']).strftime('%d.%m %H:%M')}\n"
            text += f"   📊 Статус: {payment['status']}\n\n"
    
    text += "👇 <b>Выберите действие:</b>"
    
    await message.answer(
        text,
        reply_markup=kb_main.get_admin_finance_keyboard()
    )

# ==================== НАСТРОЙКИ СИСТЕМЫ ====================

@router.message(F.text == "⚙️ Настройки системы")
async def system_settings(message: Message):
    """Настройки системы"""
    if not await require_admin(message):
        return
    
    # Получаем текущие настройки
    settings = db.get_all_settings()
    
    text = "⚙️ <b>Настройки системы</b>\n\n"
    
    text += "<b>Текущие настройки:</b>\n"
    text += f"• Комиссия системы: {settings.get('commission_rate', '0')}%\n"
    text += f"• Минимальное время брони: {settings.get('min_booking_hours', '1')} час.\n"
    text += f"• Максимальное время брони: {settings.get('max_booking_days', '30')} дн.\n"
    text += f"• Автоотмена брони: {settings.get('auto_cancel_hours', '24')} час.\n"
    text += f"• Телефон поддержки: {settings.get('support_phone', '+79990000000')}\n"
    text += f"• Email поддержки: {settings.get('support_email', 'support@parkingbot.ru')}\n\n"
    
    text += "<b>Уведомления:</b>\n"
    text += f"• Новые бронирования: {'✅' if settings.get('notification_new_booking', '1') == '1' else '❌'}\n"
    text += f"• Новые отзывы: {'✅' if settings.get('notification_new_review', '1') == '1' else '❌'}\n"
    text += f"• Новые жалобы: {'✅' if settings.get('notification_new_report', '1') == '1' else '❌'}\n\n"
    
    # Информация о пароле админки
    current_user = db.get_user(telegram_id=message.from_user.id)
    if current_user and current_user.get('is_admin'):
        text += "<b>🔐 Управление доступом:</b>\n"
        text += "• Пароль для входа в админку: *******\n"
        text += f"• Постоянных админов: {len(db.get_all_users(is_admin=True))}\n\n"
    
    text += "👇 <b>Выберите настройку для изменения:</b>"
    
    await message.answer(
        text,
        reply_markup=kb_main.get_admin_settings_keyboard()
    )

@router.message(F.text == "💰 Комиссия")
async def commission_settings(message: Message, state: FSMContext):
    """Настройка комиссии"""
    if not await require_admin(message):
        return
    
    current_commission = db.get_setting('commission_rate', '0')
    
    await state.set_state(AdminStates.system_settings)
    await state.update_data(setting_key='commission_rate')
    
    await message.answer(
        f"💰 <b>Настройка комиссии системы</b>\n\n"
        f"Текущая комиссия: <b>{current_commission}%</b>\n\n"
        f"Введите новое значение комиссии (0-100%):\n\n"
        f"<i>Примеры:</i>\n"
        f"• 0 - без комиссии\n"
        f"• 5 - 5% комиссия\n"
        f"• 10 - 10% комиссия\n\n"
        f"<b>Важно:</b> Комиссия взимается с каждой успешной транзакции.",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(F.text == "🔐 Сменить пароль админки")
async def change_admin_password_start(message: Message, state: FSMContext):
    """Смена пароля для входа в админку"""
    if not await require_admin(message):
        return
    
    # Проверяем, является ли пользователь постоянным админом
    user = db.get_user(telegram_id=message.from_user.id)
    if not user or not user.get('is_admin'):
        await message.answer(
            "❌ <b>Недостаточно прав!</b>\n\n"
            "Только постоянные администраторы могут менять пароль для входа в админку.",
            reply_markup=kb_main.get_admin_settings_keyboard()
        )
        return
    
    await state.set_state(AdminStates.changing_password)
    
    await message.answer(
        "🔐 <b>Смена пароля для входа в админку</b>\n\n"
        "Введите новый пароль:\n\n"
        "<i>Требования:</i>\n"
        "• Минимум 6 символов\n"
        "• Рекомендуется использовать буквы, цифры и специальные символы\n\n"
        "Отправьте /cancel для отмены",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(AdminStates.changing_password)
async def change_admin_password_process(message: Message, state: FSMContext):
    """Обработка нового пароля"""
    try:
        new_password = message.text.strip()
        
        # Проверяем длину пароля
        if len(new_password) < 6:
            await message.answer(
                "❌ <b>Пароль слишком короткий!</b>\n\n"
                "Пароль должен содержать минимум 6 символов.\n"
                "Введите новый пароль:",
                reply_markup=kb_main.get_cancel_keyboard()
            )
            return
        
        # Сохраняем пароль
        success = db.set_admin_password(new_password)
        
        if success:
            await message.answer(
                f"✅ <b>Пароль успешно изменен!</b>\n\n"
                f"Новый пароль для входа в админку установлен.\n\n"
                f"<b>Используйте команду:</b>\n"
                f"/admin - для входа с новым паролем\n\n"
                f"<i>Сообщите новый пароль другим администраторам</i>",
                reply_markup=kb_main.get_admin_settings_keyboard()
            )
            
            # Логируем смену пароля
            log_user_action(
                db.get_user(telegram_id=message.from_user.id)['id'],
                "admin_password_changed",
                "Пароль для входа в админку изменен"
            )
        else:
            await message.answer(
                "❌ <b>Ошибка изменения пароля!</b>\n\n"
                "Попробуйте позже.",
                reply_markup=kb_main.get_admin_settings_keyboard()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка смены пароля админки: {e}")
        await message.answer(
            "❌ Произошла ошибка",
            reply_markup=kb_main.get_admin_settings_keyboard()
        )
        await state.clear()

@router.message(AdminStates.system_settings)
async def process_system_setting(message: Message, state: FSMContext):
    """Обработка изменения настройки"""
    try:
        data = await state.get_data()
        setting_key = data.get('setting_key')
        
        if not setting_key:
            await message.answer(
                "❌ Ошибка: не указана настройка",
                reply_markup=kb_main.get_admin_settings_keyboard()
            )
            await state.clear()
            return
        
        new_value = message.text.strip()
        
        # Валидация в зависимости от настройки
        if setting_key == 'commission_rate':
            try:
                commission = float(new_value)
                if commission < 0 or commission > 100:
                    await message.answer(
                        "❌ Комиссия должна быть от 0 до 100%\n"
                        "Введите корректное значение:",
                        reply_markup=kb_main.get_cancel_keyboard()
                    )
                    return
            except ValueError:
                await message.answer(
                    "❌ Неверный формат числа\n"
                    "Введите число (например: 5 или 10.5):",
                    reply_markup=kb_main.get_cancel_keyboard()
                )
                return
        
        # Сохраняем настройку
        success = db.set_setting(setting_key, new_value)
        
        if success:
            setting_names = {
                'commission_rate': 'комиссии системы',
                'min_booking_hours': 'минимального времени брони',
                'max_booking_days': 'максимального времени брони',
                'auto_cancel_hours': 'времени автоотмены',
                'support_phone': 'телефона поддержки',
                'support_email': 'email поддержки'
            }
            
            setting_name = setting_names.get(setting_key, setting_key)
            
            await message.answer(
                f"✅ <b>Настройка {setting_name} изменена!</b>\n\n"
                f"Новое значение: <b>{new_value}</b>\n\n"
                f"Изменение вступит в силу немедленно.",
                reply_markup=kb_main.get_admin_settings_keyboard()
            )
            
            # Логируем действие
            log_user_action(
                db.get_user(telegram_id=message.from_user.id)['id'],
                "system_setting_changed",
                f"{setting_key} изменено на: {new_value}"
            )
        else:
            await message.answer(
                "❌ <b>Ошибка сохранения настройки!</b>\n\n"
                "Попробуйте позже.",
                reply_markup=kb_main.get_admin_settings_keyboard()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка изменения настройки: {e}")
        await message.answer(
            "❌ Произошла ошибка",
            reply_markup=kb_main.get_admin_settings_keyboard()
        )
        await state.clear()

# ==================== РЕЗЕРВНОЕ КОПИРОВАНИЕ ====================

@router.message(F.text == "📊 Резервная копия")
async def backup_database(message: Message):
    """Резервное копирование базы данных"""
    if not await require_admin(message):
        return
    
    import os
    from datetime import datetime
    
    # Создаем имя файла с датой
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Создаем резервную копию
    success = db.backup_database(backup_path)
    
    if success:
        # Получаем размер файла
        file_size = os.path.getsize(backup_path) / 1024 / 1024  # в MB
        
        await message.answer(
            f"✅ <b>Резервная копия создана!</b>\n\n"
            f"📁 Файл: {backup_filename}\n"
            f"📦 Размер: {file_size:.2f} MB\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"<i>Файл сохранен в директории /backups</i>",
            reply_markup=kb_main.get_admin_settings_keyboard()
        )
        
        # Логируем действие
        log_user_action(
            db.get_user(telegram_id=message.from_user.id)['id'],
            "backup_created",
            f"Создана резервная копия: {backup_filename}"
        )
    else:
        await message.answer(
            "❌ <b>Ошибка создания резервной копии!</b>\n\n"
            "Проверьте права доступа к директории.",
            reply_markup=kb_main.get_admin_settings_keyboard()
        )

# ==================== РАССЫЛКА СООБЩЕНИЙ ====================

@router.message(F.text == "📢 Рассылка")
async def broadcast_message_start(message: Message, state: FSMContext):
    """Начало рассылки сообщений"""
    if not await require_admin(message):
        return
    
    await state.set_state(AdminStates.broadcasting_message)
    
    await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Введите сообщение для рассылки:\n\n"
        "<i>Поддерживается HTML-разметка</i>\n"
        "<i>Отправьте /cancel для отмены</i>",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(AdminStates.broadcasting_message)
async def broadcast_message_process(message: Message, state: FSMContext):
    """Обработка рассылки"""
    try:
        broadcast_text = message.text
        users = db.get_all_users(limit=1000)  # Получаем всех пользователей
        
        if not users:
            await message.answer("❌ Нет пользователей для рассылки")
            await state.clear()
            return
        
        # Подтверждение рассылки
        keyboard = kb_inline.InlineKeyboardBuilder()
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="✅ Начать рассылку",
            callback_data=f"confirm_broadcast_{len(users)}"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_broadcast"
        ))
        keyboard.adjust(2)
        
        # Сохраняем текст рассылки
        await state.update_data(broadcast_text=broadcast_text)
        
        await message.answer(
            f"📢 <b>Подтверждение рассылки</b>\n\n"
            f"<b>Сообщение:</b>\n"
            f"{broadcast_text[:500]}...\n\n"
            f"<b>Получатели:</b> {len(users)} пользователей\n\n"
            f"<i>Нажмите 'Начать рассылку' для подтверждения</i>",
            reply_markup=keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")
        await message.answer("❌ Ошибка при подготовке рассылки")
        await state.clear()

# ==================== ОБРАБОТКА КОЛБЭКОВ ====================

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin_panel(callback: CallbackQuery):
    """Вернуться в админ-панель"""
    if not await require_admin(callback=callback):
        return
    
    await admin_panel(callback.message)
    await callback.answer()

@router.callback_query(F.data == "back_to_users")
async def back_to_users_menu(callback: CallbackQuery):
    """Вернуться к меню пользователей"""
    if not await require_admin(callback=callback):
        return
    
    await admin_users(callback.message)
    await callback.answer()

@router.callback_query(F.data == "back_to_reports")
async def back_to_reports_menu(callback: CallbackQuery):
    """Вернуться к меню жалоб"""
    if not await require_admin(callback=callback):
        return
    
    await admin_reports(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("make_admin_"))
async def make_user_admin(callback: CallbackQuery):
    """Назначить пользователя администратором"""
    if not await require_admin(callback=callback):
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Проверяем, является ли текущий пользователь постоянным админом
    current_user = db.get_user(telegram_id=callback.from_user.id)
    if not current_user or not current_user.get('is_admin'):
        await callback.answer("❌ Только постоянные администраторы могут назначать других админов")
        return
    
    success = db.set_admin(user_id, is_admin=True)
    
    if success:
        user = db.get_user(user_id=user_id)
        
        await callback.message.edit_text(
            f"✅ <b>Пользователь назначен администратором!</b>\n\n"
            f"👤 {user['full_name']}\n"
            f"📱 {user['phone']}\n\n"
            f"Теперь пользователь имеет постоянный доступ к админ-панели.",
            reply_markup=kb_inline.InlineKeyboardBuilder()
                .add(kb_inline.InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"view_user_{user_id}"
                ))
                .adjust(1)
                .as_markup()
        )
        
        # Уведомляем пользователя
        await notify_user(
            user['telegram_id'],
            "🎉 Вы стали администратором!",
            "Вам были предоставлены постоянные права администратора системы.\n"
            "Теперь у вас есть доступ к админ-панели без ввода пароля."
        )
        
        log_user_action(
            current_user['id'],
            "user_made_admin",
            f"Пользователь {user['full_name']} назначен постоянным админом"
        )
    else:
        await callback.answer("❌ Ошибка назначения администратора")
    
    await callback.answer()

# ==================== КОМАНДА /ADMIN_INFO ====================

@router.message(Command("admin_info"))
async def cmd_admin_info(message: Message):
    """Информация о текущей админ-сессии"""
    try:
        user = db.get_user(telegram_id=message.from_user.id)
        if not user:
            await message.answer("❌ Вы не зарегистрированы.")
            return
        
        if user.get('is_admin'):
            await message.answer(
                "👑 <b>Вы постоянный администратор!</b>\n\n"
                "У вас есть постоянный доступ ко всем функциям админ-панели.\n\n"
                "<b>Ваши привилегии:</b>\n"
                "• Доступ ко всем разделам админ-панели\n"
                "• Можете назначать других администраторов\n"
                "• Можете менять пароль для входа в админку\n"
                "• Ваши права не ограничены по времени",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
            )
        else:
            # Проверяем активную сессию
            session = db.get_admin_session(user['id'])
            if session and datetime.fromisoformat(session['expires_at']) > datetime.now():
                expires_at = datetime.fromisoformat(session['expires_at'])
                time_left = expires_at - datetime.now()
                hours_left = max(0, time_left.total_seconds() / 3600)
                
                await message.answer(
                    f"🔐 <b>У вас активная админ-сессия</b>\n\n"
                    f"Сессия действует до: {expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Осталось времени: {hours_left:.1f} часов\n\n"
                    f"<b>Ограничения временной сессии:</b>\n"
                    "• Нельзя назначать других администраторов\n"
                    "• Нельзя менять пароль для входа\n"
                    "• Доступ прекратится после истечения времени",
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
                )
            else:
                await message.answer(
                    "ℹ️ <b>У вас нет активной админ-сессии</b>\n\n"
                    "Используйте команду /admin для входа в админ-панель.",
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
                )
        
    except Exception as e:
        logger.error(f"Ошибка команды /admin_info: {e}")
        await message.answer(
            "❌ Произошла ошибка.",
            reply_markup=kb_main.get_main_menu()
        )

# ==================== ОБРАБОТКА ОШИБОК ====================

@router.callback_query()
async def admin_callback_fallback(callback: CallbackQuery):
    """Обработка неизвестных колбэков в админ-панели"""
    if not await require_admin(callback=callback):
        return
    
    await callback.answer("⚠️ Функция в разработке")