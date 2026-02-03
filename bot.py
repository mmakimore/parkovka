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

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализация базы данных
db = Database()

# Состояния бота
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

class ManageBooking(StatesGroup):
    waiting_for_booking_id = State()
    waiting_for_action = State()
    waiting_for_new_date = State()
    waiting_for_new_time = State()
    waiting_for_new_price = State()

class ManageSpot(StatesGroup):
    waiting_for_spot_id = State()
    waiting_for_action = State()
    waiting_for_new_spot_number = State()
    waiting_for_new_price_hour = State()
    waiting_for_new_price_day = State()

# Вспомогательные функции
def get_next_days(count=4):
    """Получение ближайших дней"""
    today = datetime.now().date()
    return [today + timedelta(days=i) for i in range(count)]

def format_date(date):
    """Форматирование даты в строку"""
    if isinstance(date, str):
        return date
    return date.strftime("%d.%m.%Y")

def parse_date(date_str):
    """Парсинг даты из строки"""
    try:
        date_str = date_str.strip()
        # Убираем все нецифровые символы, кроме точек
        date_str = re.sub(r'[^\d.]+', '', date_str)
        
        # Разбиваем по точкам
        parts = date_str.split('.')
        if len(parts) == 3:
            day = parts[0].zfill(2)
            month = parts[1].zfill(2)
            year = parts[2]
            
            # Обработка года
            if len(year) == 2:
                year = '20' + year
            
            # Формируем дату
            date_str = f"{day}.{month}.{year}"
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        return None
    except:
        return None

def create_date_keyboard(is_custom_allowed=True, action_type="book"):
    """Создание клавиатуры выбора даты"""
    days = get_next_days(4)
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for day in days:
        btn_text = format_date(day)
        callback_data = f"{action_type}_date_{day}"
        markup.insert(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    if is_custom_allowed:
        markup.add(types.InlineKeyboardButton("📅 Выбрать свою дату", callback_data=f"{action_type}_custom_date"))
    
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_all"))
    
    return markup

def get_main_keyboard(user_id):
    """Получение основной клавиатуры в зависимости от роли"""
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
    """Клавиатура админ-панели"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👥 Все пользователи", "🅿️ Все места")
    markup.add("📅 Все бронирования", "📊 Статистика")
    markup.add("⚙️ Управление бронированием", "🔧 Управление местом")
    markup.add("🔙 Главное меню")
    return markup

# Обработчик отмены
@dp.callback_query_handler(lambda c: c.data == "cancel_all", state="*")
async def cancel_all(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_main_menu(callback_query.message)
    await callback_query.answer("❌ Действие отменено")

# Сброс состояния при командах меню
async def reset_state_and_show_menu(message: types.Message, state: FSMContext):
    await state.finish()
    await show_main_menu(message)

# Команда /start
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    
    user_id = message.from_user.id
    
    if not db.check_user_exists(user_id):
        username = message.from_user.username or "Не указан"
        first_name = message.from_user.first_name or "Не указано"
        
        await message.answer("👋 Добро пожаловать в систему бронирования парковочных мест!")
        await message.answer("📝 Введите ваше полное имя:")
        
        await state.update_data(username=username, first_name=first_name)
        await UserRegistration.waiting_for_name.set()
    else:
        await show_main_menu(message)

async def show_main_menu(message: types.Message):
    """Показывает главное меню"""
    markup = get_main_keyboard(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=markup)

# Регистрация пользователя
@dp.message_handler(state=UserRegistration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) < 2:
        await message.answer("❌ Имя должно содержать минимум 2 символа. Введите ваше имя:")
        return
    
    await state.update_data(name=name)
    await message.answer("📱 Введите ваш номер телефона:")
    await UserRegistration.waiting_for_phone.set()

@dp.message_handler(state=UserRegistration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    
    if not phone or len(phone) < 5:
        await message.answer("❌ Введите корректный номер телефона:")
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
        await show_main_menu(message)
        
        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"👤 НОВЫЙ ПОЛЬЗОВАТЕЛЬ:\n"
                f"ID: {user.id}\n"
                f"Имя: {user_data['name']}\n"
                f"Телефон: {phone}\n"
                f"Username: @{user.username}"
            )
        except:
            pass
        
        logging.info(f"Пользователь {user.id} успешно зарегистрирован")
    else:
        await message.answer("❌ Ошибка при регистрации. Попробуйте еще раз /start")
    
    await state.finish()

# Добавление парковочного места
@dp.message_handler(lambda message: message.text == "🚗 Добавить парковочное место")
async def cmd_add_spot(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    await message.answer("🚗 Введите номер парковочного места (например, A-15 или 25B):")
    await AddParkingSpot.waiting_for_spot_number.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_spot_number)
async def process_spot_number(message: types.Message, state: FSMContext):
    spot_number = message.text.strip()
    if not spot_number:
        await message.answer("❌ Номер места не может быть пустым. Введите номер:")
        return
    
    await state.update_data(spot_number=spot_number)
    await message.answer("💰 Введите цену за час в рублях (например: 100):")
    await AddParkingSpot.waiting_for_price_hour.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_price_hour)
async def process_price_hour(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Введите цену:")
            return
        await state.update_data(price_hour=price)
        await message.answer("💰 Введите цену за сутки в рублях (например: 800):")
        await AddParkingSpot.waiting_for_price_day.set()
    except:
        await message.answer("❌ Введите корректную сумму (только цифры):")

@dp.message_handler(state=AddParkingSpot.waiting_for_price_day)
async def process_price_day(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Введите цену:")
            return
        
        await state.update_data(price_day=price)
        
        markup = create_date_keyboard(action_type="add")
        await message.answer("📅 Выберите дату для сдачи места:", reply_markup=markup)
        await AddParkingSpot.waiting_for_date_selection.set()
    except:
        await message.answer("❌ Введите корректную сумму (только цифры):")

@dp.callback_query_handler(lambda c: c.data.startswith('add_date_'), state=AddParkingSpot.waiting_for_date_selection)
async def process_add_date_selection(callback_query: types.CallbackQuery, state: FSMContext):
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
        f"🕐 Введите время доступности для {format_date(selected_date)} в формате ЧЧ.ММ-ЧЧ.ММ\n"
        f"Например: 09.00-18.00"
    )
    await AddParkingSpot.waiting_for_time_range.set()

@dp.callback_query_handler(lambda c: c.data == 'add_custom_date', state=AddParkingSpot.waiting_for_date_selection)
async def process_add_custom_date(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(
        callback_query.from_user.id,
        "📅 Введите дату в формате ДД.ММ.ГГГГ (например: 15.02.2024):"
    )
    await AddParkingSpot.waiting_for_custom_date.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_custom_date)
async def process_add_custom_date_input(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    selected_date = parse_date(date_str)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    
    today = datetime.now().date()
    if selected_date < today:
        await message.answer("❌ Нельзя выбрать прошедшую дату. Введите будущую дату:")
        return
    
    await state.update_data(selected_date=selected_date)
    await message.answer(
        f"🕐 Введите время доступности для {format_date(selected_date)} в формате ЧЧ.ММ-ЧЧ.ММ\n"
        f"Например: 09.00-18.00"
    )
    await AddParkingSpot.waiting_for_time_range.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_time_range)
async def process_time_range(message: types.Message, state: FSMContext):
    try:
        time_range = message.text.strip()
        if '-' not in time_range:
            await message.answer("❌ Неверный формат. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 09.00-18.00)")
            return
        
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        if start_time >= end_time:
            await message.answer("❌ Время окончания должно быть позже времени начала")
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
                        f"🅿️ НОВОЕ МЕСТО ДОБАВЛЕНО!\n"
                        f"ID места: {spot_id}\n"
                        f"Место: {user_data['spot_number']}\n"
                        f"Владелец: @{message.from_user.username}\n"
                        f"Цена/час: {user_data['price_hour']} руб.\n"
                        f"Цена/сутки: {user_data['price_day']} руб.\n"
                        f"Дата: {format_date(user_data['selected_date'])}\n"
                        f"Время: {time_range}"
                    )
                except:
                    pass
                
                await message.answer(
                    f"✅ Парковочное место успешно добавлено!\n\n"
                    f"📌 ID места: #{spot_id}\n"
                    f"📍 Номер места: {user_data['spot_number']}\n"
                    f"📅 Дата: {format_date(user_data['selected_date'])}\n"
                    f"🕐 Время: {time_range}\n"
                    f"💰 Цена/час: {user_data['price_hour']} руб.\n"
                    f"💰 Цена/сутки: {user_data['price_day']} руб."
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Добавить еще одну дату", callback_data=f"add_another_date_{spot_id}"),
                    types.InlineKeyboardButton("❌ Завершить", callback_data="cancel_all")
                )
                await message.answer("Хотите добавить еще одну дату для этого места?", reply_markup=markup)
            else:
                await message.answer("❌ Ошибка при добавлении доступности места.")
        else:
            await message.answer("❌ Ошибка при добавлении места.")
        
        await state.finish()
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 09.00-18.00)")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")

# Бронирование места
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
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📅 Выбрать другую дату", callback_data="choose_another_date"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_all"))
        
        await bot.send_message(
            callback_query.from_user.id,
            f"❌ На {format_date(selected_date)} нет доступных мест.",
            reply_markup=markup
        )
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for spot in spots:
        owner_info = f"@{spot['username']}" if spot['username'] else spot['first_name']
        markup.add(types.InlineKeyboardButton(
            f"📍 {spot['spot_number']} - {spot['price_per_hour']}₽/час (Владелец: {owner_info})",
            callback_data=f"select_spot_{spot['id']}"
        ))
    
    markup.add(types.InlineKeyboardButton("📅 Выбрать другую дату", callback_data="choose_another_date"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_all"))
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🅿️ Доступные места на {format_date(selected_date)}:",
        reply_markup=markup
    )
    await BookParkingSpot.waiting_for_spot_selection.set()

@dp.callback_query_handler(lambda c: c.data == 'book_custom_date', state=BookParkingSpot.waiting_for_date_selection)
async def process_book_custom_date(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(
        callback_query.from_user.id,
        "📅 Введите дату в формате ДД.ММ.ГГГГ (например: 15.02.2024):"
    )
    await BookParkingSpot.waiting_for_custom_date.set()

@dp.message_handler(state=BookParkingSpot.waiting_for_custom_date)
async def process_book_custom_date_input(message: types.Message, state: FSMContext):
    date_str = message.text.strip()
    selected_date = parse_date(date_str)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    
    today = datetime.now().date()
    if selected_date < today:
        await message.answer("❌ Нельзя выбрать прошедшую дату. Введите будущую дату:")
        return
    
    await state.update_data(selected_date=selected_date)
    await show_available_spots(
        types.CallbackQuery(
            id="custom",
            from_user=message.from_user,
            chat_instance="custom",
            message=message,
            data="custom"
        ),
        selected_date
    )

@dp.callback_query_handler(lambda c: c.data == 'choose_another_date')
async def choose_another_date(callback_query: types.CallbackQuery):
    markup = create_date_keyboard(action_type="book")
    await bot.send_message(callback_query.from_user.id, "📅 Выберите другую дату:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('select_spot_'), state=BookParkingSpot.waiting_for_spot_selection)
async def process_spot_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        spot_id = int(callback_query.data.replace('select_spot_', ''))
    except:
        await bot.send_message(callback_query.from_user.id, "❌ Ошибка выбора места")
        await state.finish()
        return
    
    await state.update_data(selected_spot_id=spot_id)
    
    await bot.send_message(
        callback_query.from_user.id,
        "🕐 Введите время бронирования в формате ЧЧ.ММ-ЧЧ.ММ\n"
        "Например: 14.00-16.00\n\n"
        "ℹ️ Минимальное бронирование - 1 час"
    )
    await BookParkingSpot.waiting_for_time_selection.set()

@dp.message_handler(state=BookParkingSpot.waiting_for_time_selection)
async def process_book_time(message: types.Message, state: FSMContext):
    try:
        time_range = message.text.strip()
        if '-' not in time_range:
            await message.answer("❌ Неверный формат. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 14.00-16.00)")
            return
        
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        if (datetime.combine(datetime.today(), end_time) - 
            datetime.combine(datetime.today(), start_time)).seconds < 3600:
            await message.answer("❌ Минимальное время бронирования - 1 час")
            return
        
        user_data = await state.get_data()
        
        spots = db.get_available_spots(user_data['selected_date'])
        selected_spot = next((s for s in spots if s['id'] == user_data['selected_spot_id']), None)
        
        if not selected_spot:
            await message.answer("❌ Место больше не доступно.")
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
            spot_number=selected_spot['spot_number'],
            price_per_hour=selected_spot['price_per_hour'],
            owner_info=selected_spot['username'] or selected_spot['first_name']
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_booking"),
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_all")
        )
        
        await message.answer(
            f"📋 ПОДТВЕРЖДЕНИЕ БРОНИРОВАНИЯ:\n\n"
            f"📍 Место: {selected_spot['spot_number']}\n"
            f"👤 Владелец: {selected_spot['username'] or selected_spot['first_name']}\n"
            f"📅 Дата: {format_date(user_data['selected_date'])}\n"
            f"🕐 Время: {time_range}\n"
            f"⏱️ Часов: {hours:.1f}\n"
            f"💰 Цена/час: {selected_spot['price_per_hour']} руб.\n"
            f"💳 Стоимость: {total_price:.2f} руб.\n\n"
            f"Подтвердить бронирование?",
            reply_markup=markup
        )
        await BookParkingSpot.waiting_for_confirmation.set()
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 14.00-16.00)")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")

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
                f"📅 НОВАЯ БРОНЬ #{booking_id}!\n\n"
                f"👤 Пользователь: @{callback_query.from_user.username}\n"
                f"📍 Место: {user_data['spot_number']}\n"
                f"📅 Дата: {format_date(user_data['selected_date'])}\n"
                f"🕐 Время: {user_data['time_range']}\n"
                f"💰 Сумма: {user_data['total_price']:.2f} руб."
            )
        except:
            pass
        
        spot_info = db.get_parking_spot(user_data['selected_spot_id'])
        if spot_info and spot_info['username']:
            try:
                await bot.send_message(
                    spot_info['owner_id'],
                    f"📍 Ваше место забронировано!\n\n"
                    f"ID брони: #{booking_id}\n"
                    f"Место: {user_data['spot_number']}\n"
                    f"Дата: {format_date(user_data['selected_date'])}\n"
                    f"Время: {user_data['time_range']}\n"
                    f"Сумма: {user_data['total_price']:.2f} руб."
                )
            except:
                pass
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ БРОНЬ ПОДТВЕРЖДЕНА!\n\n"
            f"📌 Номер брони: #{booking_id}\n"
            f"📍 Место: {user_data['spot_number']}\n"
            f"📅 Дата: {format_date(user_data['selected_date'])}\n"
            f"🕐 Время: {user_data['time_range']}\n"
            f"💰 Сумма к оплате: {user_data['total_price']:.2f} руб.\n\n"
            f"👤 Контакты владельца: {user_data['owner_info']}"
        )
    else:
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Не удалось создать бронирование. Место может быть уже занято."
        )
    
    await state.finish()

# Мои места
@dp.message_handler(lambda message: message.text == "📊 Мои места")
async def cmd_my_spots(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    spots = db.get_user_spots(message.from_user.id)
    
    if not spots:
        await message.answer("У вас пока нет добавленных парковочных мест.")
        return
    
    response = "📊 ВАШИ ПАРКОВОЧНЫЕ МЕСТА:\n\n"
    for spot in spots:
        income = spot['total_income'] or 0
        response += (
            f"📍 Место: {spot['spot_number']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"📅 Доступных дней: {spot['total_days']}\n"
            f"📊 Броней: {spot['total_bookings']}\n"
            f"💳 Доход: {income:.2f} руб.\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

# Мои бронирования
@dp.message_handler(lambda message: message.text == "📋 Мои бронирования")
async def cmd_my_bookings(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    bookings = db.get_user_bookings(message.from_user.id)
    
    if not bookings:
        await message.answer("У вас пока нет бронирований.")
        return
    
    response = "📋 ВАШИ БРОНИРОВАНИЯ:\n\n"
    for booking in bookings:
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌'
        }.get(booking['status'], '❓')
        
        response += (
            f"{status_emoji} Бронь #{booking['id']}\n"
            f"📍 Место: {booking['spot_number']}\n"
            f"👤 Владелец: {booking['owner_name']}\n"
            f"📅 Дата: {booking['date']}\n"
            f"🕐 Время: {booking['start_time'][:5]} - {booking['end_time'][:5]}\n"
            f"💰 Сумма: {booking['total_price']} руб.\n"
            f"📊 Статус: {booking['status']}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

# Админ панель
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    await message.answer("🔐 Введите пароль для доступа к админ-панели:")
    await AdminPanel.waiting_for_password.set()

@dp.message_handler(state=AdminPanel.waiting_for_password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        db.set_admin(message.from_user.id)
        
        markup = get_admin_keyboard()
        await message.answer("✅ Доступ к админ-панели предоставлен!", reply_markup=markup)
        await state.finish()
    else:
        await message.answer("❌ Неверный пароль!")
        await state.finish()

# Все пользователи
@dp.message_handler(lambda message: message.text == "👥 Все пользователи")
async def admin_all_users(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    users = db.get_all_users()
    
    if not users:
        await message.answer("Нет зарегистрированных пользователей.")
        return
    
    response = "👥 ВСЕ ПОЛЬЗОВАТЕЛИ:\n\n"
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
            f"Активных: {user['active_bookings']}\n"
            f"Регистрация: {user['registered_at'][:10]}\n"
            f"────────────────────\n"
        )
    
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(response)

# Все места
@dp.message_handler(lambda message: message.text == "🅿️ Все места")
async def admin_all_spots(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    spots = db.get_all_spots()
    
    if not spots:
        await message.answer("Нет добавленных парковочных мест.")
        return
    
    response = "🅿️ ВСЕ ПАРКОВОЧНЫЕ МЕСТА:\n\n"
    for spot in spots:
        status = "✅ АКТИВНО" if spot['is_active'] else "❌ НЕАКТИВНО"
        response += (
            f"📍 Место #{spot['id']}\n"
            f"Номер: {spot['spot_number']}\n"
            f"Владелец: @{spot['username']} ({spot['first_name']})\n"
            f"Телефон: {spot['phone']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"📅 Доступных дней: {spot['total_availability']}\n"
            f"📊 Броней: {spot['total_bookings']}\n"
            f"💳 Доход: {spot['total_income'] or 0:.2f} руб.\n"
            f"Статус: {status}\n"
            f"────────────────────\n"
        )
    
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(response)

# Все бронирования
@dp.message_handler(lambda message: message.text == "📅 Все бронирования")
async def admin_all_bookings(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    bookings = db.get_all_bookings(limit=30)
    
    if not bookings:
        await message.answer("Нет бронирований.")
        return
    
    response = "📅 ПОСЛЕДНИЕ 30 БРОНИРОВАНИЙ:\n\n"
    for booking in bookings:
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌'
        }.get(booking['status'], '❓')
        
        response += (
            f"{status_emoji} Бронь #{booking['id']}\n"
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
    
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(response)

# Статистика
@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def admin_statistics(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    stats = db.get_statistics()
    
    response = (
        f"📊 СТАТИСТИКА СИСТЕМЫ:\n\n"
        f"👥 Пользователей: {stats.get('total_users', 0)}\n"
        f"🅿️ Активных мест: {stats.get('active_spots', 0)}\n"
        f"📅 Всего бронирований: {stats.get('total_bookings', 0)}\n"
        f"⏳ Ожидающих броней: {stats.get('pending_bookings', 0)}\n"
        f"💳 Общий доход: {stats.get('total_income', 0):.2f} руб.\n\n"
        f"📈 Статистика за последние 7 дней:\n"
    )
    
    last_7_days = stats.get('last_7_days', [])
    if last_7_days:
        for day in last_7_days:
            response += f"  {day['date']}: {day['bookings']} броней, {day['income'] or 0:.2f} руб.\n"
    else:
        response += "  Нет данных за последние 7 дней\n"
    
    await message.answer(response)

# Главное меню
@dp.message_handler(lambda message: message.text == "🔙 Главное меню")
async def cmd_main_menu(message: types.Message):
    await show_main_menu(message)

@dp.message_handler(lambda message: message.text == "👑 Админ-панель")
async def cmd_admin_panel(message: types.Message):
    if db.is_admin(message.from_user.id):
        markup = get_admin_keyboard()
        await message.answer("👑 Админ-панель", reply_markup=markup)
    else:
        await message.answer("⛔ У вас нет доступа к админ-панели!")

# Обработчик команд меню в состояниях
@dp.message_handler(state="*", content_types=types.ContentTypes.TEXT)
async def handle_menu_in_state(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state and message.text in ["🚗 Добавить парковочное место", "📅 Забронировать место", 
                                          "📊 Мои места", "📋 Мои бронирования", "👑 Админ-панель",
                                          "🔙 Главное меню", "👥 Все пользователи", "🅿️ Все места",
                                          "📅 Все бронирования", "📊 Статистика"]:
        await state.finish()
        
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
    
    # Если не команда меню и мы в состоянии, просим завершить действие
    if current_state:
        await message.answer("⚠️ Завершите текущее действие или нажмите /start")

# Обработчик ошибок
@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Update {update} caused error {exception}")
    return True

# Запуск бота
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
