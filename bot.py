import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from datetime import datetime, timedelta
import re

from config import BOT_TOKEN, ADMIN_CHAT_ID, ADMIN_PASSWORD
from database import Database

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

db = Database()

class UserRegistration(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

class AddParkingSpot(StatesGroup):
    waiting_for_spot_number = State()
    waiting_for_price_hour = State()
    waiting_for_price_day = State()
    waiting_for_date_selection = State()
    waiting_for_custom_date = State()
    waiting_for_time_range = State()

class BookParkingSpot(StatesGroup):
    waiting_for_date_selection = State()
    waiting_for_custom_date = State()
    waiting_for_spot_selection = State()
    waiting_for_time_selection = State()
    waiting_for_confirmation = State()

class AdminPanel(StatesGroup):
    waiting_for_password = State()

def get_next_days(count=4):
    today = datetime.now().date()
    return [today + timedelta(days=i) for i in range(count)]

def format_date(date):
    if isinstance(date, str):
        return date
    return date.strftime("%d.%m.%Y")

def parse_date(date_str):
    try:
        date_str = date_str.strip()
        # Убираем все нецифровые символы, кроме точек
        date_str = re.sub(r'[^\d.]+', '', date_str)
        
        parts = date_str.split('.')
        if len(parts) == 3:
            day = parts[0].zfill(2)
            month = parts[1].zfill(2)
            year = parts[2]
            
            if len(year) == 2:
                year = '20' + year
            
            date_str = f"{day}.{month}.{year}"
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        return None
    except:
        return None

def create_date_keyboard(action_type="book"):
    days = get_next_days(4)
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for day in days:
        markup.insert(types.InlineKeyboardButton(
            format_date(day),
            callback_data=f"{action_type}_date_{day}"
        ))
    
    markup.add(types.InlineKeyboardButton("📅 Выбрать свою дату", callback_data=f"{action_type}_custom_date"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    return markup

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if db.is_admin(user_id):
        markup.add("🚗 Добавить парковочное место", "📅 Забронировать место")
        markup.add("📊 Мои места", "📋 Мои бронирования")
        markup.add("👑 Админ-панель")
    else:
        markup.add("🚗 Добавить парковочное место", "📅 Забронировать место")
        markup.add("📊 Мои места", "📋 Мои бронирования")
    
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👥 Все пользователи", "🅿️ Все места")
    markup.add("📅 Все бронирования", "📊 Статистика")
    markup.add("🔙 Главное меню")
    return markup

# ============ ОБРАБОТЧИКИ ============

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    
    user_id = message.from_user.id
    
    if not db.check_user_exists(user_id):
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""
        
        await message.answer("👋 Добро пожаловать!")
        await message.answer("📝 Введите ваше имя:")
        
        await state.update_data(username=username, first_name=first_name)
        await UserRegistration.waiting_for_name.set()
    else:
        await show_main_menu(message)

async def show_main_menu(message: types.Message):
    markup = get_main_keyboard(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=markup)

@dp.message_handler(state=UserRegistration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Имя не может быть пустым. Введите имя:")
        return
    
    await state.update_data(name=name)
    await message.answer("📱 Введите ваш номер телефона:")
    await UserRegistration.waiting_for_phone.set()

@dp.message_handler(state=UserRegistration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    
    if not phone:
        await message.answer("❌ Введите номер телефона:")
        return
    
    user_data = await state.get_data()
    user = message.from_user
    
    success = db.add_user(
        user_id=user.id,
        username=user_data.get('username', user.username),
        first_name=user_data['name'],
        phone=phone
    )
    
    if success:
        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"👤 Новый пользователь:\n"
                f"Имя: {user_data['name']}\n"
                f"Телефон: {phone}\n"
                f"Username: @{user.username}"
            )
        except:
            pass
        
        await show_main_menu(message)
    else:
        await message.answer("❌ Ошибка при регистрации. Попробуйте /start")
    
    await state.finish()

# ============ ДОБАВЛЕНИЕ МЕСТА ============

@dp.message_handler(lambda message: message.text == "🚗 Добавить парковочное место")
async def cmd_add_spot(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    await message.answer("🚗 Введите номер парковочного места:")
    await AddParkingSpot.waiting_for_spot_number.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_spot_number)
async def process_spot_number(message: types.Message, state: FSMContext):
    spot_number = message.text.strip()
    if not spot_number:
        await message.answer("❌ Номер места не может быть пустым:")
        return
    
    await state.update_data(spot_number=spot_number)
    await message.answer("💰 Введите цену за час (например: 100):")
    await AddParkingSpot.waiting_for_price_hour.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_price_hour)
async def process_price_hour(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0:")
            return
        await state.update_data(price_hour=price)
        await message.answer("💰 Введите цену за сутки (например: 800):")
        await AddParkingSpot.waiting_for_price_day.set()
    except:
        await message.answer("❌ Введите корректную сумму:")

@dp.message_handler(state=AddParkingSpot.waiting_for_price_day)
async def process_price_day(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0:")
            return
        
        await state.update_data(price_day=price)
        
        markup = create_date_keyboard(action_type="add")
        await message.answer("📅 Выберите дату для сдачи места:", reply_markup=markup)
        await AddParkingSpot.waiting_for_date_selection.set()
    except:
        await message.answer("❌ Введите корректную сумму:")

@dp.callback_query_handler(lambda c: c.data.startswith('add_date_'), state=AddParkingSpot.waiting_for_date_selection)
async def process_add_date(callback_query: types.CallbackQuery, state: FSMContext):
    date_str = callback_query.data.replace('add_date_', '')
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        await bot.send_message(callback_query.from_user.id, "❌ Ошибка выбора даты")
        await state.finish()
        return
    
    await state.update_data(selected_date=selected_date)
    await bot.send_message(
        callback_query.from_user.id,
        f"🕐 Введите время для {format_date(selected_date)} в формате ЧЧ.ММ-ЧЧ.ММ (например: 09.00-18.00):"
    )
    await AddParkingSpot.waiting_for_time_range.set()

@dp.callback_query_handler(lambda c: c.data == 'add_custom_date', state=AddParkingSpot.waiting_for_date_selection)
async def process_add_custom_date(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(callback_query.from_user.id, "📅 Введите дату в формате ДД.ММ.ГГГГ:")
    await AddParkingSpot.waiting_for_custom_date.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_custom_date)
async def process_add_custom_date_input(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    selected_date = parse_date(date_str)
    
    if not selected_date:
        await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:")
        return
    
    today = datetime.now().date()
    if selected_date < today:
        await message.answer("❌ Нельзя выбрать прошедшую дату:")
        return
    
    await state.update_data(selected_date=selected_date)
    await message.answer(f"🕐 Введите время для {format_date(selected_date)} в формате ЧЧ.ММ-ЧЧ.ММ:")
    await AddParkingSpot.waiting_for_time_range.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_time_range)
async def process_time_range(message: types.Message, state: FSMContext):
    try:
        time_range = message.text.strip()
        if '-' not in time_range:
            await message.answer("❌ Неверный формат. Используйте ЧЧ.ММ-ЧЧ.ММ:")
            return
        
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        if start_time >= end_time:
            await message.answer("❌ Время окончания должно быть позже:")
            return
        
        user_data = await state.get_data()
        
        spot_id = db.add_parking_spot(
            owner_id=message.from_user.id,
            spot_number=user_data['spot_number'],
            price_per_hour=user_data['price_hour'],
            price_per_day=user_data['price_day']
        )
        
        if spot_id:
            success = db.add_availability(
                spot_id=spot_id,
                date=user_data['selected_date'],
                start_time=start_time,
                end_time=end_time
            )
            
            if success:
                try:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"🅿️ Новое место:\n"
                        f"Место: {user_data['spot_number']}\n"
                        f"Владелец: @{message.from_user.username}\n"
                        f"Дата: {format_date(user_data['selected_date'])}\n"
                        f"Время: {time_range}"
                    )
                except:
                    pass
                
                await message.answer(
                    f"✅ Место добавлено!\n"
                    f"Номер: {user_data['spot_number']}\n"
                    f"Дата: {format_date(user_data['selected_date'])}\n"
                    f"Время: {time_range}"
                )
            else:
                await message.answer("❌ Ошибка при добавлении доступности")
        else:
            await message.answer("❌ Ошибка при добавлении места")
        
        await state.finish()
    except:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ")

# ============ БРОНИРОВАНИЕ ============

@dp.message_handler(lambda message: message.text == "📅 Забронировать место")
async def cmd_book_spot(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    markup = create_date_keyboard(action_type="book")
    await message.answer("📅 Выберите дату бронирования:", reply_markup=markup)
    await BookParkingSpot.waiting_for_date_selection.set()

@dp.callback_query_handler(lambda c: c.data.startswith('book_date_'), state=BookParkingSpot.waiting_for_date_selection)
async def process_book_date(callback_query: types.CallbackQuery, state: FSMContext):
    date_str = callback_query.data.replace('book_date_', '')
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        await bot.send_message(callback_query.from_user.id, "❌ Ошибка выбора даты")
        await state.finish()
        return
    
    await state.update_data(selected_date=selected_date)
    await show_available_spots(callback_query, selected_date)

async def show_available_spots(callback_query: types.CallbackQuery, selected_date):
    spots = db.get_available_spots(selected_date)
    
    if not spots:
        await bot.send_message(
            callback_query.from_user.id,
            f"❌ На {format_date(selected_date)} нет доступных мест."
        )
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for spot in spots:
        owner_info = spot['username'] or spot['first_name']
        markup.add(types.InlineKeyboardButton(
            f"📍 {spot['spot_number']} - {spot['price_per_hour']}₽/час",
            callback_data=f"select_spot_{spot['id']}"
        ))
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🅿️ Доступные места на {format_date(selected_date)}:",
        reply_markup=markup
    )
    await BookParkingSpot.waiting_for_spot_selection.set()

@dp.callback_query_handler(lambda c: c.data == 'book_custom_date', state=BookParkingSpot.waiting_for_date_selection)
async def process_book_custom_date(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(callback_query.from_user.id, "📅 Введите дату в формате ДД.ММ.ГГГГ:")
    await BookParkingSpot.waiting_for_custom_date.set()

@dp.message_handler(state=BookParkingSpot.waiting_for_custom_date)
async def process_book_custom_date_input(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    selected_date = parse_date(date_str)
    
    if not selected_date:
        await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:")
        return
    
    today = datetime.now().date()
    if selected_date < today:
        await message.answer("❌ Нельзя выбрать прошедшую дату:")
        return
    
    await state.update_data(selected_date=selected_date)
    spots = db.get_available_spots(selected_date)
    
    if not spots:
        await message.answer(f"❌ На {format_date(selected_date)} нет доступных мест.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for spot in spots:
        markup.add(types.InlineKeyboardButton(
            f"📍 {spot['spot_number']} - {spot['price_per_hour']}₽/час",
            callback_data=f"select_spot_{spot['id']}"
        ))
    
    await message.answer(f"🅿️ Доступные места на {format_date(selected_date)}:", reply_markup=markup)
    await BookParkingSpot.waiting_for_spot_selection.set()

@dp.callback_query_handler(lambda c: c.data.startswith('select_spot_'), state=BookParkingSpot.waiting_for_spot_selection)
async def process_spot_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        spot_id = int(callback_query.data.replace('select_spot_', ''))
    except:
        await bot.send_message(callback_query.from_user.id, "❌ Ошибка выбора места")
        await state.finish()
        return
    
    await state.update_data(selected_spot_id=spot_id)
    await bot.send_message(callback_query.from_user.id, "🕐 Введите время в формате ЧЧ.ММ-ЧЧ.ММ (например: 14.00-16.00):")
    await BookParkingSpot.waiting_for_time_selection.set()

@dp.message_handler(state=BookParkingSpot.waiting_for_time_selection)
async def process_book_time(message: types.Message, state: FSMContext):
    try:
        time_range = message.text.strip()
        if '-' not in time_range:
            await message.answer("❌ Неверный формат. Используйте ЧЧ.ММ-ЧЧ.ММ:")
            return
        
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        user_data = await state.get_data()
        spots = db.get_available_spots(user_data['selected_date'])
        selected_spot = next((s for s in spots if s['id'] == user_data['selected_spot_id']), None)
        
        if not selected_spot:
            await message.answer("❌ Место больше не доступно")
            await state.finish()
            return
        
        hours = (datetime.combine(datetime.today(), end_time) - 
                 datetime.combine(datetime.today(), start_time)).seconds / 3600
        total_price = round(hours * selected_spot['price_per_hour'], 2)
        
        await state.update_data(
            start_time=start_time,
            end_time=end_time,
            total_price=total_price,
            time_range=time_range,
            spot_number=selected_spot['spot_number']
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_booking"),
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")
        )
        
        await message.answer(
            f"📋 Подтвердите бронирование:\n"
            f"Дата: {format_date(user_data['selected_date'])}\n"
            f"Время: {time_range}\n"
            f"Стоимость: {total_price:.2f} руб.\n\n"
            f"Подтвердить?",
            reply_markup=markup
        )
        await BookParkingSpot.waiting_for_confirmation.set()
    except:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ")

@dp.callback_query_handler(lambda c: c.data == 'confirm_booking', state=BookParkingSpot.waiting_for_confirmation)
async def confirm_booking(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    booking_id = db.create_booking(
        user_id=callback_query.from_user.id,
        spot_id=user_data['selected_spot_id'],
        date=user_data['selected_date'],
        start_time=user_data['start_time'],
        end_time=user_data['end_time'],
        total_price=user_data['total_price']
    )
    
    if booking_id:
        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"📅 Новая бронь:\n"
                f"Пользователь: @{callback_query.from_user.username}\n"
                f"Дата: {format_date(user_data['selected_date'])}\n"
                f"Время: {user_data['time_range']}\n"
                f"Сумма: {user_data['total_price']:.2f} руб."
            )
        except:
            pass
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Бронь подтверждена!\n"
            f"Номер: #{booking_id}\n"
            f"Сумма: {user_data['total_price']:.2f} руб."
        )
    else:
        await bot.send_message(callback_query.from_user.id, "❌ Не удалось создать бронирование")
    
    await state.finish()

# ============ КНОПКИ ОТМЕНЫ ============

@dp.callback_query_handler(lambda c: c.data == 'cancel_action', state="*")
async def cancel_action(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_main_menu(callback_query.message)
    await callback_query.answer("❌ Действие отменено")

# ============ МОИ МЕСТА И БРОНИРОВАНИЯ ============

@dp.message_handler(lambda message: message.text == "📊 Мои места")
async def cmd_my_spots(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    spots = db.get_user_spots(message.from_user.id)
    
    if not spots:
        await message.answer("У вас пока нет добавленных мест.")
        return
    
    response = "📊 Ваши места:\n\n"
    for spot in spots:
        response += (
            f"📍 Место: {spot['spot_number']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "📋 Мои бронирования")
async def cmd_my_bookings(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    bookings = db.get_user_bookings(message.from_user.id)
    
    if not bookings:
        await message.answer("У вас пока нет бронирований.")
        return
    
    response = "📋 Ваши бронирования:\n\n"
    for booking in bookings:
        response += (
            f"Бронь #{booking['id']}\n"
            f"Место: {booking['spot_number']}\n"
            f"Дата: {booking['date']}\n"
            f"Время: {booking['start_time'][:5]} - {booking['end_time'][:5]}\n"
            f"Сумма: {booking['total_price']} руб.\n"
            f"Статус: {booking['status']}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

# ============ АДМИН-ПАНЕЛЬ ============

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    await message.answer("🔐 Введите пароль:")
    await AdminPanel.waiting_for_password.set()

@dp.message_handler(state=AdminPanel.waiting_for_password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        db.set_admin(message.from_user.id)
        markup = get_admin_keyboard()
        await message.answer("✅ Доступ к админ-панели предоставлен!", reply_markup=markup)
    else:
        await message.answer("❌ Неверный пароль!")
    
    await state.finish()

@dp.message_handler(lambda message: message.text == "👑 Админ-панель")
async def cmd_admin_panel(message: types.Message):
    if db.is_admin(message.from_user.id):
        markup = get_admin_keyboard()
        await message.answer("👑 Админ-панель", reply_markup=markup)
    else:
        await message.answer("⛔ У вас нет доступа!")

@dp.message_handler(lambda message: message.text == "👥 Все пользователи")
async def admin_all_users(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    users = db.get_all_users()
    
    if not users:
        await message.answer("Нет пользователей.")
        return
    
    response = "👥 Все пользователи:\n\n"
    for user in users:
        admin_status = "👑 АДМИН" if user['is_admin'] else "👤 ПОЛЬЗОВАТЕЛЬ"
        response += (
            f"{admin_status}\n"
            f"ID: {user['user_id']}\n"
            f"Имя: {user['first_name']}\n"
            f"Телефон: {user['phone']}\n"
            f"Username: @{user['username']}\n"
            f"Мест: {user['total_spots']}\n"
            f"Броней: {user['total_bookings']}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "🅿️ Все места")
async def admin_all_spots(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    spots = db.get_all_spots()
    
    if not spots:
        await message.answer("Нет мест.")
        return
    
    response = "🅿️ Все места:\n\n"
    for spot in spots:
        status = "✅ АКТИВНО" if spot['is_active'] else "❌ НЕАКТИВНО"
        response += (
            f"📍 Место #{spot['id']}\n"
            f"Номер: {spot['spot_number']}\n"
            f"Владелец: @{spot['username']} ({spot['first_name']})\n"
            f"Телефон: {spot['phone']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"Статус: {status}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "📅 Все бронирования")
async def admin_all_bookings(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    bookings = db.get_all_bookings()
    
    if not bookings:
        await message.answer("Нет бронирований.")
        return
    
    response = "📅 Все бронирования:\n\n"
    for booking in bookings:
        response += (
            f"Бронь #{booking['id']}\n"
            f"👤 Пользователь: @{booking['user_username']} ({booking['user_name']})\n"
            f"📞 Телефон: {booking['user_phone']}\n"
            f"📍 Место: {booking['spot_number']}\n"
            f"👤 Владелец: @{booking['owner_username']}\n"
            f"📅 Дата: {booking['date']}\n"
            f"🕐 Время: {booking['start_time'][:5]} - {booking['end_time'][:5]}\n"
            f"💰 Сумма: {booking['total_price']} руб.\n"
            f"📊 Статус: {booking['status']}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def admin_statistics(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    stats = db.get_statistics()
    
    response = (
        f"📊 Статистика:\n\n"
        f"👥 Пользователей: {stats.get('total_users', 0)}\n"
        f"🅿️ Активных мест: {stats.get('active_spots', 0)}\n"
        f"📅 Всего бронирований: {stats.get('total_bookings', 0)}\n"
        f"⏳ Ожидающих броней: {stats.get('pending_bookings', 0)}\n"
        f"💳 Общий доход: {stats.get('total_income', 0):.2f} руб."
    )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "🔙 Главное меню")
async def cmd_main_menu(message: types.Message):
    await show_main_menu(message)

# ============ ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ ============

@dp.message_handler(state="*", content_types=types.ContentTypes.TEXT)
async def handle_all_messages(message: types.Message, state: FSMContext):
    # Если сообщение - это команда меню, обрабатываем ее
    menu_commands = [
        "🚗 Добавить парковочное место", "📅 Забронировать место",
        "📊 Мои места", "📋 Мои бронирования", "👑 Админ-панель",
        "🔙 Главное меню", "👥 Все пользователи", "🅿️ Все места",
        "📅 Все бронирования", "📊 Статистика"
    ]
    
    if message.text in menu_commands:
        await state.finish()  # Сбрасываем текущее состояние
        
        if message.text == "🚗 Добавить парковочное место":
            await cmd_add_spot(message)
        elif message.text == "📅 Забронировать место":
            await cmd_book_spot(message)
        elif message.text == "📊 Мои места":
            await cmd_my_spots(message)
        elif message.text == "📋 Мои бронирования":
            await cmd_my_bookings(message)
        elif message.text == "👑 Админ-панель":
            await cmd_admin_panel(message)
        elif message.text == "👥 Все пользователи":
            await admin_all_users(message)
        elif message.text == "🅿️ Все места":
            await admin_all_spots(message)
        elif message.text == "📅 Все бронирования":
            await admin_all_bookings(message)
        elif message.text == "📊 Статистика":
            await admin_statistics(message)
        elif message.text == "🔙 Главное меню":
            await show_main_menu(message)
        return
    
    # Если не команда меню, проверяем состояние
    current_state = await state.get_state()
    if current_state:
        # Если мы в состоянии ожидания даты, пробуем распарсить
        if current_state in [
            AddParkingSpot.waiting_for_custom_date.state,
            BookParkingSpot.waiting_for_custom_date.state
        ]:
            # Передаем управление соответствующим хендлерам
            return
        else:
            # Для других состояний игнорируем непонятные сообщения
            pass

@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Ошибка: {exception}")
    return True

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
