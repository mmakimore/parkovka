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

# ============ СОСТОЯНИЯ БОТА ============
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
    waiting_for_new_status = State()

class ManageSpot(StatesGroup):
    waiting_for_spot_id = State()
    waiting_for_action = State()
    waiting_for_new_spot_number = State()
    waiting_for_new_price_hour = State()
    waiting_for_new_price_day = State()
    waiting_for_spot_status = State()

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
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
    """Парсинг даты из строки дд.мм.гггг"""
    try:
        # Пробуем разные форматы дат
        formats = ["%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue
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
        markup.add(types.InlineKeyboardButton("📅 Показать свободные даты", callback_data=f"{action_type}_show_available"))
    
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{action_type}"))
    
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

def get_manage_booking_keyboard():
    """Клавиатура управления бронированием"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("✏️ Изменить статус", "📅 Изменить дату")
    markup.add("🕐 Изменить время", "💰 Изменить цену")
    markup.add("❌ Отменить бронь", "🔙 Назад")
    return markup

def get_manage_spot_keyboard():
    """Клавиатура управления местом"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🏷️ Изменить номер", "💰 Изменить цену/час")
    markup.add("💵 Изменить цену/сутки", "✅ Активировать")
    markup.add("❌ Деактивировать", "🗑️ Удалить")
    markup.add("🔙 Назад")
    return markup

# ============ ОБРАБОТЧИКИ КОМАНД ============

# Обработчик /start
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()  # Сбрасываем все состояния
    
    user_id = message.from_user.id
    
    # Проверяем существование пользователя
    if not db.check_user_exists(user_id):
        # Сохраняем пользователя сразу с username
        username = message.from_user.username or "Не указан"
        first_name = message.from_user.first_name or "Не указано"
        
        await message.answer("👋 Добро пожаловать в систему бронирования парковочных мест!")
        await message.answer("📝 Введите ваше полное имя:")
        
        await state.update_data(username=username, first_name=first_name)
        await UserRegistration.waiting_for_name.set()
    else:
        # Показываем главное меню
        await show_main_menu(message)

async def show_main_menu(message: types.Message):
    """Показывает главное меню"""
    markup = get_main_keyboard(message.from_user.id)
    await message.answer("🏠 Главное меню", reply_markup=markup)

# ============ РЕГИСТРАЦИЯ ============
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
    
    # Простая валидация телефона
    if not phone or len(phone) < 5:
        await message.answer("❌ Введите корректный номер телефона:")
        return
    
    user_data = await state.get_data()
    user = message.from_user
    
    # Сохраняем пользователя в БД
    success = db.add_user(
        user_id=user.id,
        username=user_data.get('username', user.username),
        first_name=user_data['name'],
        phone=phone
    )
    
    if success:
        await show_main_menu(message)
        
        # Уведомление админу
        try:
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"👤 НОВЫЙ ПОЛЬЗОВАТЕЛЬ:\n"
                f"ID: {user.id}\n"
                f"Имя: {user_data['name']}\n"
                f"Телефон: {phone}\n"
                f"Username: @{user.username}"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу: {e}")
        
        logging.info(f"Пользователь {user.id} успешно зарегистрирован")
    else:
        await message.answer("❌ Ошибка при регистрации. Попробуйте еще раз /start")
    
    await state.finish()

# ============ ДОБАВЛЕНИЕ ПАРКОВОЧНОГО МЕСТА ============
@dp.message_handler(lambda message: message.text == "🚗 Добавить парковочное место", state="*")
async def cmd_add_spot(message: types.Message, state: FSMContext):
    await state.finish()
    
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
    except ValueError:
        await message.answer("❌ Введите корректную сумму (только цифры):")

@dp.message_handler(state=AddParkingSpot.waiting_for_price_day)
async def process_price_day(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Введите цену:")
            return
        
        await state.update_data(price_day=price)
        
        # Показываем клавиатуру выбора даты
        markup = create_date_keyboard(action_type="add")
        await message.answer("📅 Выберите дату для сдачи места:", reply_markup=markup)
        await AddParkingSpot.waiting_for_date_selection.set()
    except ValueError:
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
        f"Например: 09.00-18.00\n\n"
        f"❌ Для отмены нажмите /start"
    )
    await AddParkingSpot.waiting_for_time_range.set()

@dp.callback_query_handler(lambda c: c.data == 'add_custom_date', state=AddParkingSpot.waiting_for_date_selection)
async def process_add_custom_date(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(
        callback_query.from_user.id,
        "📅 Введите дату в формате ДД.ММ.ГГГГ (например: 15.02.2024):\n\n"
        f"❌ Для отмены нажмите /start"
    )
    await AddParkingSpot.waiting_for_custom_date.set()

@dp.callback_query_handler(lambda c: c.data == 'add_show_available', state=AddParkingSpot.waiting_for_date_selection)
async def process_add_show_available(callback_query: types.CallbackQuery, state: FSMContext):
    """Показывает даты, на которые уже есть свободные места"""
    dates = db.get_dates_with_availability()
    
    if not dates:
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Нет свободных мест на ближайшие 30 дней."
        )
        return
    
    response = "📅 Даты с доступными местами (ближайшие 30 дней):\n\n"
    for date in dates[:15]:  # Показываем первые 15 дат
        response += f"• {format_date(date)}\n"
    
    if len(dates) > 15:
        response += f"\n... и еще {len(dates) - 15} дат\n"
    
    await bot.send_message(callback_query.from_user.id, response)
    
    # Предлагаем ввести дату
    await bot.send_message(
        callback_query.from_user.id,
        "📅 Введите дату в формате ДД.ММ.ГГГГ:"
    )
    await AddParkingSpot.waiting_for_custom_date.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_custom_date)
async def process_add_custom_date_input(message: types.Message, state: FSMContext):
    # Проверяем, не является ли сообщение командой
    if message.text.startswith('/'):
        await state.finish()
        await cmd_start(message, state)
        return
    
    date_str = message.text.strip()
    selected_date = parse_date(date_str)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    
    # Проверяем, что дата не в прошлом
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
    # Проверяем, не является ли сообщение командой
    if message.text.startswith('/'):
        await state.finish()
        await cmd_start(message, state)
        return
    
    try:
        time_range = message.text.strip()
        if '-' not in time_range:
            await message.answer("❌ Неверный формат. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 09.00-18.00)")
            return
        
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        # Проверяем, что время корректно
        if start_time >= end_time:
            await message.answer("❌ Время окончания должно быть позже времени начала")
            return
        
        user_data = await state.get_data()
        
        # Добавляем парковочное место
        spot_id = db.add_parking_spot(
            owner_id=message.from_user.id,
            spot_number=user_data['spot_number'],
            price_per_hour=user_data['price_hour'],
            price_per_day=user_data['price_day']
        )
        
        if spot_id:
            # Добавляем доступность
            success = db.add_availability(
                spot_id=spot_id,
                date=user_data['selected_date'],
                start_time=start_time,
                end_time=end_time
            )
            
            if success:
                # Уведомление админу
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
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление админу: {e}")
                
                await message.answer(
                    f"✅ Парковочное место успешно добавлено!\n\n"
                    f"📌 ID места: #{spot_id}\n"
                    f"📍 Номер места: {user_data['spot_number']}\n"
                    f"📅 Дата: {format_date(user_data['selected_date'])}\n"
                    f"🕐 Время: {time_range}\n"
                    f"💰 Цена/час: {user_data['price_hour']} руб.\n"
                    f"💰 Цена/сутки: {user_data['price_day']} руб."
                )
                
                # Предлагаем добавить еще одну дату
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Добавить еще одну дату", callback_data=f"add_another_date_{spot_id}"),
                    types.InlineKeyboardButton("❌ Завершить", callback_data="finish_adding")
                )
                await message.answer("Хотите добавить еще одну дату для этого места?", reply_markup=markup)
            else:
                await message.answer("❌ Ошибка при добавлении доступности места.")
        else:
            await message.answer("❌ Ошибка при добавлении места.")
        
        await state.finish()
    except ValueError as e:
        logging.error(f"Ошибка формата времени: {e}")
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 09.00-18.00)")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз /start")

# ============ БРОНИРОВАНИЕ МЕСТА ============
@dp.message_handler(lambda message: message.text == "📅 Забронировать место", state="*")
async def cmd_book_spot(message: types.Message, state: FSMContext):
    await state.finish()
    
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
    """Показывает доступные места на выбранную дату"""
    spots = db.get_available_spots(selected_date)
    
    if not spots:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📅 Выбрать другую дату", callback_data="choose_another_date"))
        markup.add(types.InlineKeyboardButton("📅 Показать свободные даты", callback_data="book_show_available"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_book"))
        
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
    markup.add(types.InlineKeyboardButton("📅 Показать свободные даты", callback_data="book_show_available"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_book"))
    
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
        "📅 Введите дату в формате ДД.ММ.ГГГГ (например: 15.02.2024):\n\n"
        f"❌ Для отмены нажмите /start"
    )
    await BookParkingSpot.waiting_for_custom_date.set()

@dp.callback_query_handler(lambda c: c.data == 'book_show_available', state=BookParkingSpot.waiting_for_date_selection)
async def process_book_show_available(callback_query: types.CallbackQuery, state: FSMContext):
    """Показывает даты, на которые есть свободные места"""
    dates = db.get_dates_with_availability()
    
    if not dates:
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Нет свободных мест на ближайшие 30 дней."
        )
        return
    
    response = "📅 Даты с доступными местами (ближайшие 30 дней):\n\n"
    for date in dates[:10]:  # Показываем первые 10 дат
        response += f"• {format_date(date)}\n"
    
    if len(dates) > 10:
        response += f"\n... и еще {len(dates) - 10} дат\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📅 Выбрать из списка", callback_data="book_from_available_list"))
    markup.add(types.InlineKeyboardButton("📅 Ввести свою дату", callback_data="book_custom_date"))
    
    await bot.send_message(callback_query.from_user.id, response, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'book_from_available_list', state=BookParkingSpot.waiting_for_date_selection)
async def process_book_from_available_list(callback_query: types.CallbackQuery, state: FSMContext):
    """Показывает клавиатуру с доступными датами"""
    dates = db.get_dates_with_availability()
    
    if not dates:
        await bot.send_message(callback_query.from_user.id, "❌ Нет доступных дат")
        return
    
    # Берем первые 8 дат
    dates_to_show = dates[:8]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for date in dates_to_show:
        markup.insert(types.InlineKeyboardButton(
            format_date(date),
            callback_data=f"book_date_{date}"
        ))
    
    if len(dates) > 8:
        markup.add(types.InlineKeyboardButton("📅 Показать еще даты", callback_data="book_show_more_dates"))
    
    markup.add(types.InlineKeyboardButton("📅 Ввести свою дату", callback_data="book_custom_date"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_book"))
    
    await bot.send_message(
        callback_query.from_user.id,
        "📅 Выберите дату из доступных:",
        reply_markup=markup
    )

@dp.message_handler(state=BookParkingSpot.waiting_for_custom_date)
async def process_book_custom_date_input(message: types.Message, state: FSMContext):
    # Проверяем, не является ли сообщение командой
    if message.text.startswith('/'):
        await state.finish()
        await cmd_start(message, state)
        return
    
    date_str = message.text.strip()
    selected_date = parse_date(date_str)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    
    # Проверяем, что дата не в прошлом
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

@dp.callback_query_handler(lambda c: c.data == 'choose_another_date', state=[BookParkingSpot.waiting_for_spot_selection, BookParkingSpot.waiting_for_date_selection])
async def choose_another_date(callback_query: types.CallbackQuery, state: FSMContext):
    markup = create_date_keyboard(action_type="book")
    await bot.send_message(callback_query.from_user.id, "📅 Выберите другую дату:", reply_markup=markup)
    await BookParkingSpot.waiting_for_date_selection.set()

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
        "ℹ️ Минимальное бронирование - 1 час\n"
        f"❌ Для отмены нажмите /start"
    )
    await BookParkingSpot.waiting_for_time_selection.set()

@dp.message_handler(state=BookParkingSpot.waiting_for_time_selection)
async def process_book_time(message: types.Message, state: FSMContext):
    # Проверяем, не является ли сообщение командой
    if message.text.startswith('/'):
        await state.finish()
        await cmd_start(message, state)
        return
    
    try:
        time_range = message.text.strip()
        if '-' not in time_range:
            await message.answer("❌ Неверный формат. Используйте ЧЧ.ММ-ЧЧ.ММ (например: 14.00-16.00)")
            return
        
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        # Проверяем минимальное время
        if (datetime.combine(datetime.today(), end_time) - 
            datetime.combine(datetime.today(), start_time)).seconds < 3600:
            await message.answer("❌ Минимальное время бронирования - 1 час")
            return
        
        user_data = await state.get_data()
        
        # Получаем информацию о месте
        spots = db.get_available_spots(user_data['selected_date'])
        selected_spot = next((s for s in spots if s['id'] == user_data['selected_spot_id']), None)
        
        if not selected_spot:
            await message.answer("❌ Место больше не доступно.")
            await state.finish()
            return
        
        # Расчет стоимости
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
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_booking")
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
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз /start")

@dp.callback_query_handler(lambda c: c.data == 'confirm_booking', state=BookParkingSpot.waiting_for_confirmation)
async def confirm_booking(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    # Создаем бронирование
    booking_id = db.create_booking(
        user_id=callback_query.from_user.id,
        spot_id=user_data['selected_spot_id'],
        date=user_data['selected_date'],
        start_time=user_data['start_time'],
        end_time=user_data['end_time'],
        total_price=user_data['total_price']
    )
    
    if booking_id:
        # Уведомление админу
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
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу: {e}")
        
        # Уведомление владельцу места (если у него есть username)
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

# ============ ОБЩИЕ ОБРАБОТЧИКИ ОТМЕНЫ ============
@dp.callback_query_handler(lambda c: c.data.startswith('cancel_'), state="*")
async def cancel_action(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_main_menu(callback_query.message)
    await callback_query.answer("❌ Действие отменено")

@dp.callback_query_handler(lambda c: c.data == 'finish_adding', state="*")
async def finish_adding(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_main_menu(callback_query.message)
    await callback_query.answer("✅ Добавление завершено")

@dp.callback_query_handler(lambda c: c.data.startswith('add_another_date_'), state="*")
async def add_another_date(callback_query: types.CallbackQuery, state: FSMContext):
    spot_id = int(callback_query.data.replace('add_another_date_', ''))
    
    # Сохраняем spot_id в состоянии
    await state.set_state(AddParkingSpot.waiting_for_date_selection)
    await state.update_data(spot_id=spot_id)
    
    # Получаем информацию о месте
    spot = db.get_parking_spot(spot_id)
    if spot:
        await bot.send_message(
            callback_query.from_user.id,
            f"📍 Место: {spot['spot_number']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n\n"
            f"Выберите дополнительную дату для этого места:"
        )
    
    markup = create_date_keyboard(action_type="add")
    await bot.send_message(callback_query.from_user.id, "📅 Выберите дату:", reply_markup=markup)

# ============ МОИ МЕСТА И БРОНИРОВАНИЯ ============
@dp.message_handler(lambda message: message.text == "📊 Мои места", state="*")
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
        status = "✅ АКТИВНО" if spot['is_active'] else "❌ НЕАКТИВНО"
        response += (
            f"📍 Место #{spot['id']}\n"
            f"Номер: {spot['spot_number']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"📅 Доступных дней: {spot['total_days']}\n"
            f"📊 Броней: {spot['total_bookings']}\n"
            f"💳 Доход: {income:.2f} руб.\n"
            f"Статус: {status}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "📋 Мои бронирования", state="*")
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

# ============ АДМИН-ПАНЕЛЬ ============
@dp.message_handler(commands=['admin'], state="*")
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

@dp.message_handler(lambda message: message.text == "👑 Админ-панель", state="*")
async def cmd_admin_panel(message: types.Message):
    if db.is_admin(message.from_user.id):
        markup = get_admin_keyboard()
        await message.answer("👑 Админ-панель", reply_markup=markup)
    else:
        await message.answer("⛔ У вас нет доступа к админ-панели!")

@dp.message_handler(lambda message: message.text == "👥 Все пользователи", state="*")
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
    
    # Разбиваем на части, если слишком длинное сообщение
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(response)

@dp.message_handler(lambda message: message.text == "🅿️ Все места", state="*")
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

@dp.message_handler(lambda message: message.text == "📅 Все бронирования", state="*")
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

@dp.message_handler(lambda message: message.text == "📊 Статистика", state="*")
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
        f"✅ Подтвержденных: {stats.get('confirmed_bookings', 0)}\n"
        f"❌ Отмененных: {stats.get('cancelled_bookings', 0)}\n"
        f"💳 Общий доход: {stats.get('total_income', 0):.2f} руб.\n\n"
        f"📈 Статистика за последние 7 дней:\n"
    )
    
    last_7_days = stats.get('last_7_days', [])
    if last_7_days:
        for day in last_7_days:
            response += f"  {day['date']}: {day['bookings']} броней, {day['income'] or 0:.2f} руб.\n"
    else:
        response += "  Нет данных за последние 7 дней\n"
    
    response += "\n🏆 Популярные места:\n"
    top_spots = stats.get('top_spots', [])
    if top_spots:
        for spot in top_spots:
            response += f"  {spot['spot_number']}: {spot['bookings_count']} броней\n"
    else:
        response += "  Нет данных\n"
    
    await message.answer(response)

# ============ УПРАВЛЕНИЕ БРОНИРОВАНИЯМИ ============
@dp.message_handler(lambda message: message.text == "⚙️ Управление бронированием", state="*")
async def manage_booking_start(message: types.Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    await message.answer("Введите ID бронирования для управления:")
    await ManageBooking.waiting_for_booking_id.set()

@dp.message_handler(state=ManageBooking.waiting_for_booking_id)
async def manage_booking_id(message: types.Message, state: FSMContext):
    try:
        booking_id = int(message.text)
    except:
        await message.answer("❌ Неверный формат ID. Введите число:")
        return
    
    booking = db.get_booking(booking_id)
    if not booking:
        await message.answer("❌ Бронирование не найдено.")
        await state.finish()
        return
    
    await state.update_data(booking_id=booking_id, booking_data=booking)
    
    markup = get_manage_booking_keyboard()
    
    booking_info = (
        f"📋 ИНФОРМАЦИЯ О БРОНИ #{booking_id}:\n\n"
        f"👤 Пользователь: @{booking['user_username']} ({booking['user_name']})\n"
        f"📞 Телефон: {booking['user_phone']}\n"
        f"📍 Место: {booking['spot_number']}\n"
        f"👤 Владелец: @{booking['owner_username']}\n"
        f"📞 Телефон владельца: {booking['owner_phone']}\n"
        f"📅 Дата: {booking['date']}\n"
        f"🕐 Время: {booking['start_time'][:5]} - {booking['end_time'][:5]}\n"
        f"💰 Сумма: {booking['total_price']} руб.\n"
        f"📊 Статус: {booking['status']}\n"
    )
    
    await message.answer(booking_info, reply_markup=markup)
    await ManageBooking.waiting_for_action.set()

@dp.message_handler(state=ManageBooking.waiting_for_action)
async def manage_booking_action(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    booking_id = user_data['booking_id']
    
    if message.text == "✏️ Изменить статус":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("✅ Подтвердить", "⏳ В ожидании")
        markup.add("❌ Отменить", "🔙 Назад")
        await message.answer("Выберите новый статус:", reply_markup=markup)
        await state.update_data(action='change_status')
    
    elif message.text == "📅 Изменить дату":
        await message.answer("Введите новую дату в формате ДД.ММ.ГГГГ:")
        await state.update_data(action='change_date')
        await ManageBooking.waiting_for_new_date.set()
    
    elif message.text == "🕐 Изменить время":
        await message.answer("Введите новое время в формате ЧЧ.ММ-ЧЧ.ММ:")
        await state.update_data(action='change_time')
        await ManageBooking.waiting_for_new_time.set()
    
    elif message.text == "💰 Изменить цену":
        await message.answer("Введите новую цену:")
        await state.update_data(action='change_price')
        await ManageBooking.waiting_for_new_price.set()
    
    elif message.text == "❌ Отменить бронь":
        if db.cancel_booking(booking_id):
            await message.answer(f"✅ Бронь #{booking_id} отменена.")
            
            # Уведомляем пользователя
            booking = user_data['booking_data']
            try:
                await bot.send_message(
                    booking['user_id'],
                    f"❌ Ваша бронь #{booking_id} была отменена администратором.\n"
                    f"Место: {booking['spot_number']}\n"
                    f"Дата: {booking['date']}"
                )
            except:
                pass
        else:
            await message.answer("❌ Ошибка при отмене брони.")
        await state.finish()
        await show_admin_menu(message)
    
    elif message.text == "🔙 Назад":
        await state.finish()
        await show_admin_menu(message)

@dp.message_handler(state=ManageBooking.waiting_for_new_date)
async def manage_booking_new_date(message: types.Message, state: FSMContext):
    new_date = parse_date(message.text)
    if not new_date:
        await message.answer("❌ Неверный формат даты. Введите ДД.ММ.ГГГГ:")
        return
    
    user_data = await state.get_data()
    booking_id = user_data['booking_id']
    
    if db.update_booking(booking_id, date=new_date):
        await message.answer(f"✅ Дата брони #{booking_id} изменена на {format_date(new_date)}.")
    else:
        await message.answer("❌ Ошибка при изменении даты.")
    
    await state.finish()
    await show_admin_menu(message)

@dp.message_handler(state=ManageBooking.waiting_for_new_time)
async def manage_booking_new_time(message: types.Message, state: FSMContext):
    try:
        time_range = message.text.strip()
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
    except:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ:")
        return
    
    user_data = await state.get_data()
    booking_id = user_data['booking_id']
    
    if db.update_booking(booking_id, start_time=start_time, end_time=end_time):
        await message.answer(f"✅ Время брони #{booking_id} изменено на {time_range}.")
    else:
        await message.answer("❌ Ошибка при изменении времени.")
    
    await state.finish()
    await show_admin_menu(message)

@dp.message_handler(state=ManageBooking.waiting_for_new_price)
async def manage_booking_new_price(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text)
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0:")
            return
    except:
        await message.answer("❌ Неверный формат цены. Введите число:")
        return
    
    user_data = await state.get_data()
    booking_id = user_data['booking_id']
    
    if db.update_booking(booking_id, total_price=new_price):
        await message.answer(f"✅ Цена брони #{booking_id} изменена на {new_price} руб.")
    else:
        await message.answer("❌ Ошибка при изменении цены.")
    
    await state.finish()
    await show_admin_menu(message)

# ============ УПРАВЛЕНИЕ МЕСТАМИ ============
@dp.message_handler(lambda message: message.text == "🔧 Управление местом", state="*")
async def manage_spot_start(message: types.Message, state: FSMContext):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    await message.answer("Введите ID парковочного места для управления:")
    await ManageSpot.waiting_for_spot_id.set()

@dp.message_handler(state=ManageSpot.waiting_for_spot_id)
async def manage_spot_id(message: types.Message, state: FSMContext):
    try:
        spot_id = int(message.text)
    except:
        await message.answer("❌ Неверный формат ID. Введите число:")
        return
    
    spot = db.get_parking_spot(spot_id)
    if not spot:
        await message.answer("❌ Парковочное место не найдено.")
        await state.finish()
        return
    
    await state.update_data(spot_id=spot_id, spot_data=spot)
    
    markup = get_manage_spot_keyboard()
    
    spot_info = (
        f"📍 ИНФОРМАЦИЯ О МЕСТЕ #{spot_id}:\n\n"
        f"Номер: {spot['spot_number']}\n"
        f"Владелец: @{spot['username']} ({spot['first_name']})\n"
        f"Телефон: {spot['phone']}\n"
        f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
        f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
        f"Статус: {'✅ АКТИВНО' if spot['is_active'] else '❌ НЕАКТИВНО'}\n"
    )
    
    await message.answer(spot_info, reply_markup=markup)
    await ManageSpot.waiting_for_action.set()

@dp.message_handler(state=ManageSpot.waiting_for_action)
async def manage_spot_action(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    spot_id = user_data['spot_id']
    
    if message.text == "🏷️ Изменить номер":
        await message.answer("Введите новый номер места:")
        await state.update_data(action='change_number')
        await ManageSpot.waiting_for_new_spot_number.set()
    
    elif message.text == "💰 Изменить цену/час":
        await message.answer("Введите новую цену за час:")
        await state.update_data(action='change_price_hour')
        await ManageSpot.waiting_for_new_price_hour.set()
    
    elif message.text == "💵 Изменить цену/сутки":
        await message.answer("Введите новую цену за сутки:")
        await state.update_data(action='change_price_day')
        await ManageSpot.waiting_for_new_price_day.set()
    
    elif message.text == "✅ Активировать":
        if db.update_parking_spot(spot_id, is_active=1):
            await message.answer(f"✅ Место #{spot_id} активировано.")
        else:
            await message.answer("❌ Ошибка при активации места.")
        await state.finish()
        await show_admin_menu(message)
    
    elif message.text == "❌ Деактивировать":
        if db.update_parking_spot(spot_id, is_active=0):
            await message.answer(f"✅ Место #{spot_id} деактивировано.")
        else:
            await message.answer("❌ Ошибка при деактивации места.")
        await state.finish()
        await show_admin_menu(message)
    
    elif message.text == "🗑️ Удалить":
        if db.delete_parking_spot(spot_id):
            await message.answer(f"✅ Место #{spot_id} удалено.")
        else:
            await message.answer("❌ Ошибка при удалении места.")
        await state.finish()
        await show_admin_menu(message)
    
    elif message.text == "🔙 Назад":
        await state.finish()
        await show_admin_menu(message)

@dp.message_handler(state=ManageSpot.waiting_for_new_spot_number)
async def manage_spot_new_number(message: types.Message, state: FSMContext):
    new_number = message.text.strip()
    if not new_number:
        await message.answer("❌ Номер не может быть пустым. Введите номер:")
        return
    
    user_data = await state.get_data()
    spot_id = user_data['spot_id']
    
    if db.update_parking_spot(spot_id, spot_number=new_number):
        await message.answer(f"✅ Номер места #{spot_id} изменен на '{new_number}'.")
    else:
        await message.answer("❌ Ошибка при изменении номера.")
    
    await state.finish()
    await show_admin_menu(message)

@dp.message_handler(state=ManageSpot.waiting_for_new_price_hour)
async def manage_spot_new_price_hour(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text)
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0:")
            return
    except:
        await message.answer("❌ Неверный формат цены. Введите число:")
        return
    
    user_data = await state.get_data()
    spot_id = user_data['spot_id']
    
    if db.update_parking_spot(spot_id, price_per_hour=new_price):
        await message.answer(f"✅ Цена/час места #{spot_id} изменена на {new_price} руб.")
    else:
        await message.answer("❌ Ошибка при изменении цены.")
    
    await state.finish()
    await show_admin_menu(message)

@dp.message_handler(state=ManageSpot.waiting_for_new_price_day)
async def manage_spot_new_price_day(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text)
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0:")
            return
    except:
        await message.answer("❌ Неверный формат цены. Введите число:")
        return
    
    user_data = await state.get_data()
    spot_id = user_data['spot_id']
    
    if db.update_parking_spot(spot_id, price_per_day=new_price):
        await message.answer(f"✅ Цена/сутки места #{spot_id} изменена на {new_price} руб.")
    else:
        await message.answer("❌ Ошибка при изменении цены.")
    
    await state.finish()
    await show_admin_menu(message)

# ============ ГЛАВНОЕ МЕНЮ ============
@dp.message_handler(lambda message: message.text == "🔙 Главное меню", state="*")
async def cmd_main_menu(message: types.Message):
    await show_main_menu(message)

async def show_admin_menu(message: types.Message):
    """Показывает меню админа"""
    markup = get_admin_keyboard()
    await message.answer("👑 Админ-панель", reply_markup=markup)

# ============ ОБРАБОТЧИК ЛЮБЫХ СООБЩЕНИЙ ============
@dp.message_handler(state="*", content_types=types.ContentTypes.TEXT)
async def handle_any_text(message: types.Message, state: FSMContext):
    # Игнорируем команды меню
    menu_commands = ["🚗 Добавить парковочное место", "📅 Забронировать место", 
                    "📊 Мои места", "📋 Мои бронирования", "👑 Админ-панель",
                    "🔙 Главное меню", "👥 Все пользователи", "🅿️ Все места",
                    "📅 Все бронирования", "📊 Статистика", "⚙️ Управление бронированием",
                    "🔧 Управление местом"]
    
    if message.text in menu_commands:
        return
    
    # Если не команда меню и мы в состоянии - игнорируем
    current_state = await state.get_state()
    if current_state:
        await message.answer("⚠️ Пожалуйста, завершите текущее действие или нажмите /start для отмены")

# ============ ОБРАБОТЧИК ОШИБОК ============
@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Update {update} caused error {exception}")
    return True

# ============ ЗАПУСК БОТА ============
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
