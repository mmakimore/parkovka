"""
Обработчики для работы с парковочными местами
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards import main as kb_main
from keyboards import inline as kb_inline
from handlers.utils import (
    format_spot_info, format_price, log_user_action,
    is_spot_owner, calculate_booking_price
)

logger = logging.getLogger(__name__)
router = Router()

# ==================== СОСТОЯНИЯ ДЛЯ МЕСТ ====================

class SpotStates(StatesGroup):
    """Состояния для добавления/редактирования мест"""
    waiting_for_spot_number = State()
    waiting_for_address = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_features = State()
    
    # Для редактирования
    editing_spot = State()

# ==================== МЕНЮ МЕСТ ====================

@router.message(F.text == "🏠 Мои места")
@router.message(F.text == "📋 Мои места")
async def my_spots(message: Message, state: FSMContext):
    """Показать меню мест пользователя"""
    await state.clear()
    
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Нажмите /start")
        return
    
    # Получаем места пользователя
    spots = db.get_user_spots(user['id'])
    
    if not spots:
        await message.answer(
            "📭 <b>У вас еще нет парковочных мест</b>\n\n"
            "Вы можете добавить свое место и начать зарабатывать!\n\n"
            "Нажмите <b>➕ Добавить место</b>, чтобы создать первое место.",
            reply_markup=kb_main.get_spots_menu()
        )
        return
    
    # Формируем список мест
    text = "🏠 <b>Ваши парковочные места:</b>\n\n"
    
    for i, spot in enumerate(spots, 1):
        active_bookings = spot.get('active_bookings', 0)
        earnings = spot.get('total_earnings', 0)
        
        text += f"<b>{i}. Место #{spot['spot_number']}</b>\n"
        text += f"📍 {spot['address'][:50]}{'...' if len(spot['address']) > 50 else ''}\n"
        text += f"💰 {format_price(spot['price_per_hour'])} ₽/час\n"
        
        if active_bookings > 0:
            text += f"📊 Активных броней: {active_bookings}\n"
        
        if earnings > 0:
            text += f"💵 Заработано: {format_price(earnings)} ₽\n"
        
        text += f"⭐ Рейтинг: {spot.get('rating', 'Нет')}/5\n\n"
    
    text += "👇 <b>Выберите действие:</b>"
    
    await message.answer(
        text,
        reply_markup=kb_main.get_spots_menu()
    )

# ==================== ДОБАВЛЕНИЕ МЕСТА ====================

@router.message(F.text == "➕ Добавить место")
async def add_spot_start(message: Message, state: FSMContext):
    """Начало добавления нового места"""
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Нажмите /start")
        return
    
    # Проверяем лимит мест
    spots_count = db.count_spots(owner_id=user['id'], is_active=True)
    if spots_count >= 10:
        await message.answer(
            "❌ <b>Достигнут лимит мест!</b>\n\n"
            "Вы можете иметь не более 10 активных мест.\n"
            "Удалите одно из существующих мест, чтобы добавить новое.",
            reply_markup=kb_main.get_spots_menu()
        )
        return
    
    await state.set_state(SpotStates.waiting_for_spot_number)
    
    await message.answer(
        "🏠 <b>Добавление нового парковочного места</b>\n\n"
        "Шаг 1 из 5\n\n"
        "📝 <b>Введите номер места:</b>\n\n"
        "<i>Примеры:</i>\n"
        "• A1\n"
        "• 101\n"
        "• Парковка-2\n"
        "• Гостевой 3\n\n"
        "<i>Этот номер будет отображаться при поиске</i>",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(SpotStates.waiting_for_spot_number)
async def process_spot_number(message: Message, state: FSMContext):
    """Обработка номера места"""
    spot_number = message.text.strip()
    
    if len(spot_number) > 20:
        await message.answer(
            "❌ <b>Номер места слишком длинный!</b>\n\n"
            "Максимум 20 символов. Введите снова:",
            reply_markup=kb_main.get_cancel_keyboard()
        )
        return
    
    await state.update_data(spot_number=spot_number)
    await state.set_state(SpotStates.waiting_for_address)
    
    await message.answer(
        "🏠 <b>Добавление нового парковочного места</b>\n\n"
        "Шаг 2 из 5\n\n"
        "📍 <b>Введите адрес места:</b>\n\n"
        "<i>Примеры:</i>\n"
        "• Москва, ул. Тверская, д. 10\n"
        "• СПб, Невский пр., 25\n"
        "• ТЦ Мега, парковка этаж 3\n\n"
        "<i>Чем точнее адрес, тем проще клиентам найти место</i>",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(SpotStates.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """Обработка адреса"""
    address = message.text.strip()
    
    if len(address) < 5:
        await message.answer(
            "❌ <b>Адрес слишком короткий!</b>\n\n"
            "Введите полный адрес (минимум 5 символов):",
            reply_markup=kb_main.get_cancel_keyboard()
        )
        return
    
    await state.update_data(address=address)
    await state.set_state(SpotStates.waiting_for_price)
    
    await message.answer(
        "🏠 <b>Добавление нового парковочного места</b>\n\n"
        "Шаг 3 из 5\n\n"
        "💰 <b>Введите цену за час:</b>\n\n"
        "<i>Примеры:</i>\n"
        "• 100\n"
        "• 150.50\n"
        "• 200\n\n"
        "<i>Цена указывается в рублях</i>\n"
        "<i>Цена за день будет рассчитана автоматически (час × 24)</i>",
        reply_markup=kb_main.get_cancel_keyboard()
    )

@router.message(SpotStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    """Обработка цены"""
    try:
        price_per_hour = float(message.text.strip().replace(',', '.'))
        
        if price_per_hour <= 0:
            await message.answer(
                "❌ <b>Цена должна быть больше 0!</b>\n\n"
                "Введите цену еще раз:",
                reply_markup=kb_main.get_cancel_keyboard()
            )
            return
        
        if price_per_hour > 10000:
            await message.answer(
                "❌ <b>Цена слишком высокая!</b>\n\n"
                "Максимальная цена - 10 000 ₽/час\n"
                "Введите корректную цену:",
                reply_markup=kb_main.get_cancel_keyboard()
            )
            return
        
        await state.update_data(price_per_hour=price_per_hour)
        await state.set_state(SpotStates.waiting_for_description)
        
        await message.answer(
            "🏠 <b>Добавление нового парковочного места</b>\n\n"
            "Шаг 4 из 5\n\n"
            "📝 <b>Введите описание места (необязательно):</b>\n\n"
            "<i>Примеры:</i>\n"
            "• Крытая парковка, видеонаблюдение\n"
            "• Рядом с входом в ТЦ\n"
            "• Освещенное место, навигация\n\n"
            "<i>Можно пропустить, отправив \"-\"</i>",
            reply_markup=kb_main.get_cancel_keyboard()
        )
        
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат цены!</b>\n\n"
            "Введите число (например: 150 или 200.50):",
            reply_markup=kb_main.get_cancel_keyboard()
        )

@router.message(SpotStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания"""
    description = message.text.strip()
    if description == '-':
        description = None
    
    await state.update_data(description=description)
    await state.set_state(SpotStates.waiting_for_features)
    
    # Создаем инлайн-клавиатуру для выбора особенностей
    features_keyboard = kb_inline.InlineKeyboardBuilder()
    
    features = [
        ("🏢 Крытая", "covered"),
        ("🎥 CCTV", "cctv"),
        ("💡 Освещение", "lighting"),
        ("🔌 Розетка", "electricity")
    ]
    
    for feature_text, feature_key in features:
        features_keyboard.add(kb_inline.InlineKeyboardButton(
            text=f"⬜ {feature_text}",
            callback_data=f"toggle_feature_{feature_key}"
        ))
    
    features_keyboard.add(kb_inline.InlineKeyboardButton(
        text="✅ Продолжить",
        callback_data="continue_without_features"
    ))
    
    features_keyboard.adjust(2)
    
    await message.answer(
        "🏠 <b>Добавление нового парковочного места</b>\n\n"
        "Шаг 5 из 5\n\n"
        "✅ <b>Выберите особенности места:</b>\n\n"
        "<i>Отметьте галочками соответствующие особенности</i>\n"
        "<i>Можно не выбирать</i>",
        reply_markup=features_keyboard.as_markup()
    )

@router.callback_query(F.data.startswith("toggle_feature_"))
async def toggle_feature(callback: CallbackQuery, state: FSMContext):
    """Переключение особенности места"""
    feature_key = callback.data.split("_")[2]
    
    # Получаем текущие данные
    data = await state.get_data()
    selected_features = data.get('features', [])
    
    if feature_key in selected_features:
        selected_features.remove(feature_key)
    else:
        selected_features.append(feature_key)
    
    await state.update_data(features=selected_features)
    
    # Обновляем клавиатуру
    features_keyboard = kb_inline.InlineKeyboardBuilder()
    
    features_mapping = [
        ("🏢 Крытая", "covered"),
        ("🎥 CCTV", "cctv"),
        ("💡 Освещение", "lighting"),
        ("🔌 Розетка", "electricity")
    ]
    
    for feature_text, f_key in features_mapping:
        prefix = "✅" if f_key in selected_features else "⬜"
        features_keyboard.add(kb_inline.InlineKeyboardButton(
            text=f"{prefix} {feature_text}",
            callback_data=f"toggle_feature_{f_key}"
        ))
    
    features_keyboard.add(kb_inline.InlineKeyboardButton(
        text="✅ Продолжить",
        callback_data="continue_with_features"
    ))
    
    features_keyboard.adjust(2)
    
    await callback.message.edit_reply_markup(
        reply_markup=features_keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.in_(["continue_without_features", "continue_with_features"]))
async def finish_spot_creation(callback: CallbackQuery, state: FSMContext):
    """Завершение создания места"""
    try:
        user = db.get_user(telegram_id=callback.from_user.id)
        if not user:
            await callback.answer("❌ Ошибка: пользователь не найден")
            return
        
        # Получаем все данные
        data = await state.get_data()
        
        # Извлекаем особенности
        selected_features = data.get('features', [])
        is_covered = 'covered' in selected_features
        has_cctv = 'cctv' in selected_features
        has_lighting = 'lighting' in selected_features
        has_electricity = 'electricity' in selected_features
        
        # Рассчитываем цену за день
        price_per_hour = data['price_per_hour']
        price_per_day = price_per_hour * 24
        
        # Добавляем место в базу
        spot_id = db.add_parking_spot(
            owner_id=user['id'],
            spot_number=data['spot_number'],
            address=data['address'],
            price_per_hour=price_per_hour,
            price_per_day=price_per_day,
            description=data.get('description'),
            is_covered=is_covered,
            has_cctv=has_cctv,
            has_lighting=has_lighting,
            has_electricity=has_electricity
        )
        
        if spot_id:
            # Успешно создано
            await callback.message.edit_text(
                f"✅ <b>Парковочное место создано!</b>\n\n"
                f"🏠 <b>Место #{data['spot_number']}</b>\n"
                f"📍 Адрес: {data['address']}\n"
                f"💰 Цена: {format_price(price_per_hour)} ₽/час\n"
                f"📅 Цена за день: {format_price(price_per_day)} ₽\n\n"
                f"Теперь вы можете:\n"
                f"• Управлять расписанием доступности\n"
                f"• Принимать бронирования\n"
                f"• Получать оплату\n\n"
                f"<i>Используйте меню для управления местом</i>",
                reply_markup=None
            )
            
            # Логируем действие
            log_user_action(user['id'], "spot_created", f"Создано место #{data['spot_number']}")
            
            # Показываем меню мест
            await callback.message.answer(
                "👇 <b>Выберите действие:</b>",
                reply_markup=kb_main.get_spots_menu()
            )
            
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка при создании места!</b>\n\n"
                "Возможно, место с таким номером уже существует.\n"
                "Попробуйте еще раз.",
                reply_markup=None
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка создания места: {e}")
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка!</b>\n\n"
            "Не удалось создать место. Попробуйте позже.",
            reply_markup=None
        )
        await state.clear()

# ==================== ПРОСМОТР И УПРАВЛЕНИЕ МЕСТОМ ====================

@router.callback_query(F.data.startswith("view_spot_"))
async def view_spot(callback: CallbackQuery):
    """Просмотр детальной информации о месте"""
    try:
        spot_id = int(callback.data.split("_")[2])
        spot = db.get_parking_spot(spot_id)
        
        if not spot:
            await callback.answer("❌ Место не найдено")
            return
        
        # Проверяем, владелец ли это места
        user = db.get_user(telegram_id=callback.from_user.id)
        is_owner = user and spot['owner_id'] == user['id']
        
        if not is_owner:
            await callback.answer("❌ У вас нет доступа к этому месту")
            return
        
        # Форматируем информацию о месте
        spot_info = format_spot_info(spot)
        
        # Добавляем статистику
        spot_info += f"\n📊 <b>Статистика:</b>\n"
        spot_info += f"• Всего бронирований: {spot.get('total_bookings', 0)}\n"
        spot_info += f"• Заработано: {format_price(spot.get('total_earnings', 0))} ₽\n"
        spot_info += f"• Активных броней: {spot.get('active_bookings', 0)}\n"
        
        await callback.message.edit_text(
            spot_info,
            reply_markup=kb_main.get_spot_management_keyboard(spot_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка просмотра места: {e}")
        await callback.answer("❌ Произошла ошибка")

# ==================== УПРАВЛЕНИЕ РАСПИСАНИЕМ ====================

@router.message(F.text == "📅 Управление расписанием")
async def manage_schedule_menu(message: Message):
    """Меню управления расписанием"""
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы")
        return
    
    spots = db.get_user_spots(user['id'])
    
    if not spots:
        await message.answer(
            "❌ У вас нет мест для управления расписанием",
            reply_markup=kb_main.get_spots_menu()
        )
        return
    
    # Создаем инлайн-клавиатуру с местами
    keyboard = kb_inline.InlineKeyboardBuilder()
    
    for spot in spots[:10]:  # Ограничиваем 10 местами
        keyboard.add(kb_inline.InlineKeyboardButton(
            text=f"🏠 #{spot['spot_number']} - {spot['address'][:30]}...",
            callback_data=f"spot_schedule_{spot['id']}"
        ))
    
    keyboard.adjust(1)
    
    await message.answer(
        "📅 <b>Управление расписанием</b>\n\n"
        "Выберите место для настройки расписания:",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data.startswith("spot_schedule_"))
async def spot_schedule(callback: CallbackQuery):
    """Расписание конкретного места"""
    spot_id = int(callback.data.split("_")[2])
    
    spot = db.get_parking_spot(spot_id)
    if not spot:
        await callback.answer("❌ Место не найдено")
        return
    
    # Проверяем права доступа
    user = db.get_user(telegram_id=callback.from_user.id)
    if not user or spot['owner_id'] != user['id']:
        await callback.answer("❌ Нет доступа")
        return
    
    # Получаем расписание
    schedule = db.get_spot_availability(spot_id)
    
    # Создаем клавиатуру для управления расписанием
    keyboard = kb_inline.InlineKeyboardBuilder()
    
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day_num in range(7):
        # Ищем расписание на этот день
        day_schedule = [s for s in schedule if s['day_of_week'] == day_num]
        
        if day_schedule and not day_schedule[0]['is_available']:
            status = "❌"
        elif day_schedule:
            status = "✅"
        else:
            status = "❓"
        
        keyboard.add(kb_inline.InlineKeyboardButton(
            text=f"{status} {days[day_num]}",
            callback_data=f"edit_day_{spot_id}_{day_num}"
        ))
    
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="➕ Добавить исключение",
        callback_data=f"add_exception_{spot_id}"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📋 Список исключений",
        callback_data=f"list_exceptions_{spot_id}"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=f"back_to_spot_{spot_id}"
    ))
    
    keyboard.adjust(7, 2, 1)
    
    await callback.message.edit_text(
        f"📅 <b>Расписание места #{spot['spot_number']}</b>\n\n"
        f"📍 {spot['address']}\n\n"
        f"<b>Статусы:</b>\n"
        f"✅ - Доступно\n"
        f"❌ - Недоступно\n"
        f"❓ - Не настроено\n\n"
        f"Нажмите на день недели для изменения:",
        reply_markup=keyboard.as_markup()
    )

# ==================== СТАТИСТИКА ДОХОДОВ ====================

@router.message(F.text == "💰 Статистика доходов")
async def income_stats(message: Message):
    """Статистика доходов от всех мест"""
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы")
        return
    
    spots = db.get_user_spots(user['id'])
    
    if not spots:
        await message.answer(
            "📭 <b>Нет статистики</b>\n\n"
            "У вас еще нет мест или по ним нет доходов.",
            reply_markup=kb_main.get_spots_menu()
        )
        return
    
    # Считаем общую статистику
    total_spots = len(spots)
    total_earnings = sum(spot.get('total_earnings', 0) for spot in spots)
    total_bookings = sum(spot.get('total_bookings', 0) for spot in spots)
    
    # Формируем отчет
    text = f"💰 <b>Статистика доходов</b>\n\n"
    text += f"👤 Владелец: {user['full_name']}\n"
    text += f"🏠 Всего мест: {total_spots}\n"
    text += f"📊 Всего бронирований: {total_bookings}\n"
    text += f"💵 Общий доход: {format_price(total_earnings)} ₽\n\n"
    
    # Добавляем статистику по каждому месту
    text += "<b>📈 По местам:</b>\n\n"
    
    for spot in spots[:10]:  # Ограничиваем 10 местами
        earnings = spot.get('total_earnings', 0)
        if earnings > 0:
            text += f"🏠 <b>#{spot['spot_number']}</b>\n"
            text += f"   📍 {spot['address'][:40]}...\n"
            text += f"   💰 {format_price(earnings)} ₽\n"
            text += f"   📊 {spot.get('total_bookings', 0)} бронирований\n\n"
    
    if total_spots > 10:
        text += f"\n<i>... и еще {total_spots - 10} мест</i>\n"
    
    await message.answer(
        text,
        reply_markup=kb_main.get_spots_menu()
    )

# ==================== УДАЛЕНИЕ МЕСТА ====================

@router.callback_query(F.data.startswith("delete_spot_"))
async def delete_spot_confirm(callback: CallbackQuery):
    """Подтверждение удаления места"""
    spot_id = int(callback.data.split("_")[2])
    
    spot = db.get_parking_spot(spot_id)
    if not spot:
        await callback.answer("❌ Место не найдено")
        return
    
    # Проверяем права доступа
    user = db.get_user(telegram_id=callback.from_user.id)
    if not user or spot['owner_id'] != user['id']:
        await callback.answer("❌ Нет доступа")
        return
    
    # Создаем клавиатуру подтверждения
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="✅ Да, удалить",
        callback_data=f"confirm_delete_{spot_id}"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="❌ Нет, отмена",
        callback_data=f"back_to_spot_{spot_id}"
    ))
    keyboard.adjust(2)
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить место?\n\n"
        f"🏠 <b>Место #{spot['spot_number']}</b>\n"
        f"📍 {spot['address']}\n\n"
        f"<b>Это действие нельзя отменить!</b>\n"
        f"Все данные о месте будут удалены.\n"
        f"Активные бронирования будут отменены.",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_spot(callback: CallbackQuery):
    """Подтвержденное удаление места"""
    spot_id = int(callback.data.split("_")[2])
    
    spot = db.get_parking_spot(spot_id)
    if not spot:
        await callback.answer("❌ Место не найдено")
        return
    
    # Проверяем права доступа
    user = db.get_user(telegram_id=callback.from_user.id)
    if not user or spot['owner_id'] != user['id']:
        await callback.answer("❌ Нет доступа")
        return
    
    # Удаляем место (мягкое удаление)
    success = db.delete_spot(spot_id)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Место удалено</b>\n\n"
            f"Место #{spot['spot_number']} было успешно удалено.",
            reply_markup=None
        )
        
        # Логируем действие
        log_user_action(user['id'], "spot_deleted", f"Удалено место #{spot['spot_number']}")
        
        # Показываем меню мест
        await callback.message.answer(
            "👇 <b>Выберите действие:</b>",
            reply_markup=kb_main.get_spots_menu()
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка удаления</b>\n\n"
            "Не удалось удалить место. Попробуйте позже.",
            reply_markup=kb_inline.get_confirmation_keyboard("delete", spot_id)
        )

# ==================== НАЗАД К МЕСТУ ====================

@router.callback_query(F.data.startswith("back_to_spot_"))
async def back_to_spot(callback: CallbackQuery):
    """Вернуться к просмотру места"""
    spot_id = int(callback.data.split("_")[3])
    
    # Используем уже существующий обработчик
    await view_spot(callback)

# ==================== НАЗАД К СПИСКУ МЕСТ ====================

@router.callback_query(F.data == "back_to_spots")
async def back_to_spots(callback: CallbackQuery):
    """Вернуться к списку мест"""
    await my_spots(callback.message, None)