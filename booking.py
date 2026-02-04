from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from database import Database
from keyboards.main import get_main_menu, get_cancel_keyboard
from keyboards.inline import get_date_keyboard, get_time_keyboard, get_spot_keyboard
from handlers.utils import *
from config import ADMIN_USER_ID

db = Database()

class Booking(StatesGroup):
    start_date = State()
    start_time = State()
    end_date = State()
    end_time = State()
    select_spot = State()
    confirm = State()

async def cmd_book(message: types.Message):
    """Начать бронирование"""
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь!")
        return
    
    await message.answer(
        "📅 <b>Выберите дату начала:</b>",
        reply_markup=get_date_keyboard("book_start")
    )
    await Booking.start_date.set()

async def callback_date(callback: types.CallbackQuery, state: FSMContext, callback_data: dict):
    """Обработка выбора даты"""
    action = callback_data.get("action")
    date_str = callback_data.get("date")
    
    if action == "book_start_date":
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        await state.update_data(start_date=date)
        
        await callback.message.edit_text(
            f"📅 Дата начала: {format_date(date)}\n\n"
            f"🕐 <b>Выберите время начала:</b>",
            reply_markup=get_time_keyboard()
        )
        await Booking.start_time.set()
    
    await callback.answer()

async def callback_time(callback: types.CallbackQuery, state: FSMContext, callback_data: dict):
    """Обработка выбора времени"""
    time_str = callback_data.get("time")
    time_obj = parse_time(time_str)
    
    data = await state.get_data()
    current_state = await state.get_state()
    
    if current_state == "Booking:start_time":
        await state.update_data(start_time=time_str)
        
        await callback.message.edit_text(
            f"📅 Начало: {format_date(data['start_date'])} {time_str}\n\n"
            f"📅 <b>Выберите дату окончания:</b>",
            reply_markup=get_date_keyboard("book_end")
        )
        await Booking.end_date.set()
    
    elif current_state == "Booking:end_time":
        await state.update_data(end_time=time_str)
        
        # Ищем доступные места
        start_date = data['start_date']
        start_time = data['start_time']
        end_date = data['end_date']
        
        start_dt = datetime.combine(start_date, parse_time(start_time))
        end_dt = datetime.combine(end_date, time_obj)
        
        spots = db.get_available_spots_by_period(
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        if not spots:
            await callback.message.edit_text(
                "❌ <b>Нет доступных мест на этот период</b>\n\n"
                "Попробуйте выбрать другой период.",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search"),
                    types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                )
            )
            await state.finish()
            return
        
        await state.update_data(
            start_datetime=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_datetime=end_dt.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        await callback.message.edit_text(
            f"📅 <b>Доступные места:</b>\n"
            f"Период: {format_datetime(start_dt)} - {format_datetime(end_dt)}\n\n"
            f"Выберите место:",
            reply_markup=get_spot_keyboard(spots, "select")
        )
        await Booking.select_spot.set()
    
    await callback.answer()

async def callback_select_spot(callback: types.CallbackQuery, state: FSMContext, callback_data: dict):
    """Обработка выбора места"""
    spot_id = int(callback_data.get("spot_id"))
    
    spot = db.get_spot(spot_id)
    if not spot:
        await callback.answer("❌ Место не найдено")
        return
    
    data = await state.get_data()
    start_dt = datetime.strptime(data['start_datetime'], "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(data['end_datetime'], "%Y-%m-%d %H:%M:%S")
    
    # Находим свободный период
    periods = db.get_spot_periods(
        spot_id,
        data['start_datetime'],
        data['end_datetime']
    )
    
    if not periods:
        await callback.answer("❌ Период уже занят")
        return
    
    period = periods[0]
    total_price, duration = calculate_price(
        spot['price_hour'],
        spot['price_day'],
        start_dt,
        end_dt
    )
    
    # Получаем данные арендатора
    renter = db.get_user_by_telegram_id(callback.from_user.id)
    
    await state.update_data(
        spot_id=spot_id,
        period_id=period['id'],
        spot_number=spot['spot_number'],
        total_price=total_price,
        duration=duration
    )
    
    text = (
        f"✅ <b>Подтверждение бронирования</b>\n\n"
        f"📍 <b>Место:</b> {spot['spot_number']}\n"
        f"👤 <b>Владелец:</b> {spot['owner_name']}\n"
        f"📞 <b>Телефон владельца:</b> {spot['owner_phone']}\n"
        f"📅 <b>Период:</b> {format_datetime(start_dt)} - {format_datetime(end_dt)}\n"
        f"⏱️ <b>Длительность:</b> {duration:.1f} ч.\n"
        f"💰 <b>Стоимость:</b> {total_price} руб.\n\n"
        f"💳 <b>Реквизиты для оплаты:</b>\n"
        f"Карта: {format_card(spot['owner_card'])}\n"
        f"Банк: {spot['owner_bank']}\n\n"
        f"<b>Ваши данные для владельца:</b>\n"
        f"• ФИО: {renter['full_name']}\n"
        f"• Телефон: {renter['phone']}\n"
        f"• Авто: {renter['car_brand']} {renter['car_model']} {renter['car_plate']}\n\n"
        f"Подтвердить бронирование?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_booking"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_booking")
    )
    markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    await callback.message.edit_text(text, reply_markup=markup)
    await Booking.confirm.set()
    await callback.answer()

async def callback_confirm_booking(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение бронирования"""
    data = await state.get_data()
    user = db.get_user_by_telegram_id(callback.from_user.id)
    spot = db.get_spot(data['spot_id'])
    
    # Создаем бронирование
    booking_id = db.create_booking(
        user_id=user['id'],
        spot_id=data['spot_id'],
        period_id=data['period_id'],
        total_price=data['total_price']
    )
    
    if booking_id:
        # Отправляем уведомление админу
        await callback.bot.send_message(
            ADMIN_USER_ID,
            f"📅 <b>НОВОЕ БРОНИРОВАНИЕ #{booking_id}</b>\n\n"
            f"<b>📍 Место:</b> {data['spot_number']}\n"
            f"<b>💰 Сумма:</b> {data['total_price']} руб.\n\n"
            f"<b>👤 АРЕНДАТОР:</b>\n"
            f"• ID: {callback.from_user.id}\n"
            f"• Имя: {user['full_name']}\n"
            f"• Телефон: {user['phone']}\n"
            f"• Карта: {user['card_number']}\n"
            f"• Банк: {user['bank']}\n"
            f"• Авто: {user['car_brand']} {user['car_model']} {user['car_plate']}\n\n"
            f"<b>👤 ВЛАДЕЛЕЦ:</b>\n"
            f"• Имя: {spot['owner_name']}\n"
            f"• Телефон: {spot['owner_phone']}\n"
            f"• Карта: {format_card(spot['owner_card'])}\n"
            f"• Банк: {spot['owner_bank']}"
        )
        
        # Отправляем уведомление владельцу
        owner = db.get_user(spot['owner_id'])
        if owner and owner['telegram_id']:
            await callback.bot.send_message(
                owner['telegram_id'],
                f"🔔 <b>Новое бронирование!</b>\n\n"
                f"📍 Место: {data['spot_number']}\n"
                f"👤 Арендатор: {user['full_name']}\n"
                f"📞 Телефон: {user['phone']}\n"
                f"🚗 Авто: {user['car_brand']} {user['car_model']} {user['car_plate']}\n"
                f"💰 Сумма: {data['total_price']} руб.\n\n"
                f"💳 <b>Оплата на карту:</b>\n"
                f"{format_card(spot['owner_card'])}\n"
                f"🏦 {spot['owner_bank']}"
            )
        
        await callback.message.edit_text(
            f"✅ <b>Бронирование #{booking_id} подтверждено!</b>\n\n"
            f"📍 Место: {data['spot_number']}\n"
            f"💰 Сумма: {data['total_price']} руб.\n\n"
            f"💳 <b>Реквизиты для оплаты:</b>\n"
            f"Карта: {format_card(spot['owner_card'])}\n"
            f"Банк: {spot['owner_bank']}\n\n"
            f"📞 <b>Контакты владельца:</b>\n"
            f"Телефон: {spot['owner_phone']}"
        )
        
        db.add_notification(user['id'], f"✅ Бронирование #{booking_id} подтверждено!")
    else:
        await callback.message.edit_text("❌ Ошибка бронирования")
    
    await state.finish()
    await callback.answer()

async def my_bookings(message: types.Message):
    """Мои бронирования"""
    user = db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйтесь!")
        return
    
    bookings = db.get_user_bookings(user['id'])
    
    if not bookings:
        await message.answer("📋 У вас нет активных бронирований")
        return
    
    text = "📋 <b>Ваши бронирования:</b>\n\n"
    
    for booking in bookings[:10]:
        text += f"<b>Бронь #{booking['id']}</b>\n"
        text += f"📍 Место: {booking['spot_number']}\n"
        text += f"📅 Период: {format_datetime(booking['start_time'])} - {format_datetime(booking['end_time'])}\n"
        text += f"💰 Стоимость: {booking['total_price']} руб.\n"
        text += f"💳 Карта владельца: {format_card(booking['owner_card'])}\n"
        text += f"🏦 Банк: {booking['owner_bank']}\n"
        text += f"📞 Телефон: {booking['owner_phone']}\n"
        text += "────────────────────\n"
    
    await message.answer(text)

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.register_message_handler(cmd_book, lambda m: m.text == "📅 Забронировать")
    dp.register_message_handler(my_bookings, lambda m: m.text == "📋 Мои брони")
    
    # Callback handlers
    dp.register_callback_query_handler(
        lambda c, s: callback_date(c, s, {"action": "book_start_date", "date": c.data.split("_")[-1]}),
        lambda c: c.data.startswith("book_start_date_"),
        state=Booking.start_date
    )
    
    dp.register_callback_query_handler(
        lambda c, s: callback_time(c, s, {"time": c.data.split("_")[-1]}),
        lambda c: c.data.startswith("time_"),
        state=[Booking.start_time, Booking.end_time]
    )
    
    dp.register_callback_query_handler(
        lambda c, s: callback_select_spot(c, s, {"spot_id": int(c.data.split("_")[-1])}),
        lambda c: c.data.startswith("select_spot_"),
        state=Booking.select_spot
    )
    
    dp.register_callback_query_handler(
        callback_confirm_booking,
        lambda c: c.data == "confirm_booking",
        state=Booking.confirm
    )