import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from datetime import datetime, timedelta
import re
import asyncio

from config import BOT_TOKEN, ADMIN_CHAT_ID, ADMIN_PASSWORD
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

db = Database()

# ============ STATES ============
class UserRegistration(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

class AddParkingSpot(StatesGroup):
    waiting_for_spot_number = State()
    waiting_for_price_hour = State()
    waiting_for_price_day = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_confirmation = State()

class BookParkingSpot(StatesGroup):
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_spot_selection = State()
    waiting_for_confirmation = State()
    waiting_for_notification_decision = State()

class ViewFreeSpots(StatesGroup):
    waiting_for_days_ahead = State()

class ManageNotifications(StatesGroup):
    waiting_for_action = State()

class EditProfile(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

# ============ HELPER FUNCTIONS ============
def parse_date(date_str):
    """Парсит дату из различных форматов"""
    try:
        date_str = str(date_str).strip()
        
        # Убираем все нецифровые символы, кроме точек и дефисов
        date_str = re.sub(r'[^\d\.\-/]+', '', date_str)
        
        # Заменяем разделители на точки
        date_str = date_str.replace('/', '.').replace('-', '.')
        
        parts = date_str.split('.')
        if len(parts) == 3:
            day = parts[0].zfill(2)
            month = parts[1].zfill(2)
            year = parts[2]
            
            if len(year) == 2:
                year = '20' + year
            elif len(year) != 4:
                return None
            
            try:
                date_obj = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y").date()
                return date_obj
            except ValueError:
                return None
        return None
    except Exception as e:
        logger.error(f"Ошибка парсинга даты: {e}")
        return None

def parse_time(time_str):
    """Парсит время из различных форматов"""
    try:
        time_str = str(time_str).strip()
        time_str = re.sub(r'[^\d:\.]+', '', time_str)
        time_str = time_str.replace('.', ':')
        
        if ':' not in time_str and len(time_str) == 4:
            time_str = time_str[:2] + ':' + time_str[2:]
        elif ':' not in time_str and len(time_str) == 3:
            time_str = '0' + time_str[:1] + ':' + time_str[1:]
        
        try:
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            return time_obj
        except ValueError:
            return None
    except Exception as e:
        logger.error(f"Ошибка парсинга времени: {e}")
        return None

def format_date(date):
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        except:
            return date
    return date.strftime("%d.%m.%Y")

def format_datetime(dt_str):
    try:
        if isinstance(dt_str, str):
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        else:
            dt = dt_str
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return dt_str

def format_time(time_obj):
    if isinstance(time_obj, str):
        return time_obj
    return time_obj.strftime("%H:%M")

def get_next_days(count=6):
    today = datetime.now().date()
    return [today + timedelta(days=i) for i in range(count)]

def calculate_price(price_per_hour, price_per_day, start_datetime, end_datetime):
    duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
    duration_days = int(duration_hours // 24)
    remaining_hours = duration_hours % 24
    total_price = duration_days * price_per_day
    
    if remaining_hours > 6:
        total_price += price_per_day
    else:
        total_price += remaining_hours * price_per_hour
    
    return round(total_price, 2), duration_hours

def get_available_dates_for_period(start_date, end_date, start_time, end_time):
    available_dates = []
    current_date = start_date
    
    while current_date <= end_date:
        day_start = datetime.combine(current_date, start_time)
        day_end = datetime.combine(current_date, end_time)
        
        available_spots = db.get_available_spots_by_date_range(
            day_start.strftime("%Y-%m-%d %H:%M:%S"),
            day_end.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        if available_spots:
            available_dates.append(current_date)
        
        current_date += timedelta(days=1)
    
    return available_dates

# ============ KEYBOARDS ============
def get_main_keyboard(user_id):
    is_admin = db.is_admin(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        "🚗 Сдать место",
        "📅 Найти место",
        "🔍 Найти свободные места",
        "📊 Мои места", 
        "📋 Мои брони",
        "🔔 Мои уведомления",
        "👤 Профиль",
        "ℹ️ Помощь"
    ]
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.add(*row)
    
    if is_admin:
        markup.add("👑 Админ-панель")
    
    return markup

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Отмена")
    return markup

def get_yes_no_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("✅ Да", "❌ Нет")
    markup.add("❌ Отмена")
    return markup

def get_date_selection_keyboard(action="book", include_custom=True):
    days = get_next_days(6)
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for day in days:
        day_name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][day.weekday()]
        text = f"{format_date(day)} ({day_name})"
        markup.insert(types.InlineKeyboardButton(
            text=text,
            callback_data=f"{action}_date_{day}"
        ))
    
    if include_custom:
        markup.row(types.InlineKeyboardButton(
            "📅 Другая дата",
            callback_data=f"{action}_custom_date"
        ))
    
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return markup

def get_time_selection_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=4)
    
    for hour in range(0, 24):
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            markup.insert(types.InlineKeyboardButton(
                time_str,
                callback_data=f"time_{time_str}"
            ))
    
    markup.row(types.InlineKeyboardButton("🕐 Свое время", callback_data="custom_time"))
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return markup

def get_no_available_spots_keyboard(start_datetime, end_datetime):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    markup.add(types.InlineKeyboardButton(
        "🔍 Посмотреть свободные места",
        callback_data=f"view_free_spots_{start_datetime}_{end_datetime}"
    ))
    
    markup.add(types.InlineKeyboardButton(
        "🔔 Упоминуть при появлении",
        callback_data=f"notify_when_available_{start_datetime}_{end_datetime}"
    ))
    
    markup.add(types.InlineKeyboardButton(
        "🔄 Выбрать другой период",
        callback_data="choose_another_period"
    ))
    
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return markup

def get_free_spots_period_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    periods = [
        ("Сегодня", 1),
        ("Завтра", 2),
        ("3 дня", 3),
        ("Неделя", 7),
        ("2 недели", 14),
        ("Месяц", 30)
    ]
    
    for text, days in periods:
        markup.insert(types.InlineKeyboardButton(
            text,
            callback_data=f"free_spots_{days}"
        ))
    
    markup.row(types.InlineKeyboardButton("📅 Указать период", callback_data="custom_free_period"))
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        "👥 Пользователи",
        "🅿️ Места",
        "📅 Бронирования",
        "📊 Статистика",
        "📢 Рассылка"
    )
    markup.add("🔙 Главное меню")
    return markup

# ============ START COMMAND ============
@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    welcome_text = (
        "🚗 <b>Добро пожаловать в сервис бронирования парковок!</b>\n\n"
        "Здесь вы можете:\n"
        "• 🚗 Сдать в аренду свое парковочное место\n"
        "• 📅 Забронировать место для парковки\n"
        "• 🔍 Найти свободные места\n"
        "• 🔔 Получать уведомления о появлении мест\n"
        "• 💰 Зарабатывать на своем парковочном месте\n\n"
        "<b>Новые функции:</b>\n"
        "• 🔍 Поиск свободных мест на любой период\n"
        "• 🔔 Уведомления при появлении свободных мест\n"
        "• 📊 Просмотр всех активных парковок\n"
    )
    
    if not db.check_user_exists(user_id):
        await message.answer(welcome_text)
        await message.answer("📝 Введите ваше полное имя:")
        
        await state.update_data(username=username, first_name=first_name)
        await UserRegistration.waiting_for_name.set()
    else:
        await show_main_menu(message)

async def show_main_menu(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await cmd_start(message, None)
        return
    
    notifications = db.get_unread_notifications(user_id)
    if notifications:
        await message.answer(f"📢 У вас {len(notifications)} непрочитанных уведомлений!\n"
                          "Используйте команду /notifications для просмотра")
    
    markup = get_main_keyboard(user_id)
    await message.answer("🏠 <b>Главное меню</b>\n\n"
                      "Выберите действие:", reply_markup=markup)

@dp.message_handler(state=UserRegistration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Регистрация отменена")
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя должно содержать минимум 2 символа. Введите имя:")
        return
    
    await state.update_data(name=name)
    await message.answer("📱 Введите ваш номер телефона в формате +7XXXXXXXXXX:")
    await UserRegistration.waiting_for_phone.set()

@dp.message_handler(state=UserRegistration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("❌ Регистрация отменена")
        return
    
    phone = message.text.strip()
    phone_pattern = re.compile(r'^\+?7\d{10}$|^8\d{10}$|^\d{11}$')
    
    if not phone_pattern.match(phone.replace(' ', '')):
        await message.answer("❌ Неверный формат телефона. Введите в формате +7XXXXXXXXXX:")
        return
    
    phone = phone.replace(' ', '')
    if phone.startswith('8'):
        phone = '+7' + phone[1:]
    elif phone.startswith('7'):
        phone = '+' + phone
    elif not phone.startswith('+7'):
        if len(phone) == 11:
            phone = '+7' + phone[1:]
        elif len(phone) == 10:
            phone = '+7' + phone
    
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
                f"👤 <b>Новый пользователь</b>\n"
                f"Имя: {user_data['name']}\n"
                f"Телефон: {phone}\n"
                f"Username: @{user.username if user.username else 'нет'}\n"
                f"ID: {user.id}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")
        
        await show_main_menu(message)
        await message.answer(f"✅ <b>Регистрация завершена!</b>\n\n"
                          f"👤 <b>Ваши данные:</b>\n"
                          f"Имя: {user_data['name']}\n"
                          f"Телефон: {phone}")
    else:
        await message.answer("❌ Ошибка при регистрации. Попробуйте снова через /start")
    
    await state.finish()

# ============ ADD PARKING SPOT ============
@dp.message_handler(lambda message: message.text == "🚗 Сдать место")
async def cmd_add_spot(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    await message.answer("🚗 <b>Сдача парковочного места в аренду</b>\n\n"
                      "Введите номер парковочного места (например: A15 или 42):",
                      reply_markup=get_cancel_keyboard())
    await AddParkingSpot.waiting_for_spot_number.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_spot_number)
async def process_spot_number(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    spot_number = message.text.strip().upper()
    if len(spot_number) < 1:
        await message.answer("❌ Номер места не может быть пустым. Введите номер:")
        return
    
    user_spots = db.get_user_spots(message.from_user.id)
    for spot in user_spots:
        if spot['spot_number'] == spot_number:
            await message.answer(f"❌ Место с номером {spot_number} уже существует у вас.\n"
                              "Введите другой номер:")
            return
    
    await state.update_data(spot_number=spot_number)
    await message.answer("💰 <b>Установка цены</b>\n\n"
                      "Введите стоимость аренды за 1 час (в рублях):\n"
                      "Например: 100")
    await AddParkingSpot.waiting_for_price_hour.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_price_hour)
async def process_price_hour(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Введите стоимость:")
            return
        if price > 10000:
            await message.answer("❌ Слишком высокая цена. Введите разумную стоимость (до 10000 руб):")
            return
        
        await state.update_data(price_hour=price)
        await message.answer("💰 Введите стоимость аренды за сутки (24 часа) в рублях:\n"
                          "Например: 800\n"
                          "<i>Рекомендуется установить немного меньше, чем цена за час × 24</i>")
        await AddParkingSpot.waiting_for_price_day.set()
    except ValueError:
        await message.answer("❌ Введите корректное число. Например: 100")

@dp.message_handler(state=AddParkingSpot.waiting_for_price_day)
async def process_price_day(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Введите стоимость:")
            return
        
        user_data = await state.get_data()
        price_hour = user_data.get('price_hour', 0)
        
        if price < price_hour:
            await message.answer(f"❌ Цена за сутки не может быть меньше цены за час ({price_hour} руб).\n"
                              "Введите стоимость за сутки:")
            return
        
        await state.update_data(price_day=price)
        
        await message.answer("📅 <b>Укажите дату и время начала аренды</b>\n\n"
                          "Выберите дату начала или введите свою в формате ДД.ММ.ГГГГ:\n"
                          "Например: 21.02.2026",
                          reply_markup=get_date_selection_keyboard("add_start"))
        await AddParkingSpot.waiting_for_start_date.set()
    except ValueError:
        await message.answer("❌ Введите корректное число. Например: 800")

@dp.callback_query_handler(lambda c: c.data.startswith('add_start_date_'), state=AddParkingSpot.waiting_for_start_date)
async def process_start_date(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "add_start_custom_date":
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Введите дату начала в формате ДД.ММ.ГГГГ:\n"
            "Или введите 'сегодня' или 'завтра'",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    date_str = callback_query.data.replace('add_start_date_', '')
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        await callback_query.answer("❌ Ошибка выбора даты")
        return
    
    await state.update_data(start_date=selected_date)
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🕐 <b>Укажите время начала аренды</b>\n\n"
        f"Дата: {format_date(selected_date)}\n"
        f"Выберите время начала или введите свое в формате ЧЧ:ММ\n"
        f"Например: 21:00",
        reply_markup=get_time_selection_keyboard()
    )
    await AddParkingSpot.waiting_for_start_time.set()
    await callback_query.answer()

@dp.message_handler(state=AddParkingSpot.waiting_for_start_date)
async def process_start_date_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    date_input = message.text.strip().lower()
    
    if date_input == "сегодня":
        selected_date = datetime.now().date()
    elif date_input == "завтра":
        selected_date = datetime.now().date() + timedelta(days=1)
    else:
        selected_date = parse_date(date_input)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите ДД.ММ.ГГГГ:")
        return
    
    today = datetime.now().date()
    if selected_date < today:
        await message.answer("❌ Нельзя выбрать прошедшую дату. Введите будущую дату:")
        return
    
    await state.update_data(start_date=selected_date)
    
    await message.answer(f"🕐 <b>Укажите время начала аренды</b>\n\n"
                      f"Дата: {format_date(selected_date)}\n"
                      f"Выберите время начала или введите свое в формате ЧЧ:ММ\n"
                      f"Например: 21:00",
                      reply_markup=get_time_selection_keyboard())
    await AddParkingSpot.waiting_for_start_time.set()

@dp.callback_query_handler(lambda c: c.data.startswith('time_'), state=AddParkingSpot.waiting_for_start_time)
async def process_start_time(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "custom_time":
        await bot.send_message(
            callback_query.from_user.id,
            "🕐 Введите время начала в формате ЧЧ:ММ\n"
            "Например: 21:30",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    time_str = callback_query.data.replace('time_', '')
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await callback_query.answer("❌ Ошибка выбора времени")
        return
    
    await state.update_data(start_time=time_obj)
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    await bot.send_message(
        callback_query.from_user.id,
        f"📅 <b>Укажите дату окончания аренды</b>\n\n"
        f"Начало: {format_date(start_date)} {format_time(time_obj)}\n\n"
        f"Выберите дату окончания или введите свою в формате ДД.ММ.ГГГГ:\n"
        f"<i>Можно указать ту же дату, если аренда в пределах одного дня</i>",
        reply_markup=get_date_selection_keyboard("add_end")
    )
    await AddParkingSpot.waiting_for_end_date.set()
    await callback_query.answer()

@dp.message_handler(state=AddParkingSpot.waiting_for_start_time)
async def process_start_time_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    time_str = message.text.strip()
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await message.answer("❌ Неверный формат времени. Введите ЧЧ:ММ:")
        return
    
    await state.update_data(start_time=time_obj)
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    await message.answer(f"📅 <b>Укажите дату окончания аренды</b>\n\n"
                      f"Начало: {format_date(start_date)} {format_time(time_obj)}\n\n"
                      f"Выберите дату окончания или введите свою в формате ДД.ММ.ГГГГ:\n"
                      f"<i>Можно указать ту же дату, если аренда в пределах одного день</i>",
                      reply_markup=get_date_selection_keyboard("add_end"))
    await AddParkingSpot.waiting_for_end_date.set()

@dp.callback_query_handler(lambda c: c.data.startswith('add_end_date_'), state=AddParkingSpot.waiting_for_end_date)
async def process_end_date(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "add_end_custom_date":
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Введите дату окончания в формате ДД.ММ.ГГГГ:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    date_str = callback_query.data.replace('add_end_date_', '')
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        await callback_query.answer("❌ Ошибка выбора даты")
        return
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    if selected_date < start_date:
        await callback_query.answer("❌ Дата окончания не может быть раньше даты начала!")
        return
    
    await state.update_data(end_date=selected_date)
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🕐 <b>Укажите время окончания аренды</b>\n\n"
        f"Начало: {format_date(start_date)} {format_time(user_data.get('start_time'))}\n"
        f"Окончание: {format_date(selected_date)}\n\n"
        f"Выберите время окончания или введите свое в формате ЧЧ:ММ\n"
        f"Например: 09:00",
        reply_markup=get_time_selection_keyboard()
    )
    await AddParkingSpot.waiting_for_end_time.set()
    await callback_query.answer()

@dp.message_handler(state=AddParkingSpot.waiting_for_end_date)
async def process_end_date_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    date_input = message.text.strip()
    selected_date = parse_date(date_input)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите ДД.ММ.ГГГГ:")
        return
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    if selected_date < start_date:
        await message.answer("❌ Дата окончания не может быть раньше даты начала!")
        return
    
    await state.update_data(end_date=selected_date)
    
    await message.answer(f"🕐 <b>Укажите время окончания аренды</b>\n\n"
                      f"Начало: {format_date(start_date)} {format_time(user_data.get('start_time'))}\n"
                      f"Окончание: {format_date(selected_date)}\n\n"
                      f"Выберите время окончания или введите свое в формате ЧЧ:ММ\n"
                      f"Например: 09:00",
                      reply_markup=get_time_selection_keyboard())
    await AddParkingSpot.waiting_for_end_time.set()

@dp.callback_query_handler(lambda c: c.data.startswith('time_'), state=AddParkingSpot.waiting_for_end_time)
async def process_end_time(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "custom_time":
        await bot.send_message(
            callback_query.from_user.id,
            "🕐 Введите время окончания в формате ЧЧ:ММ\n"
            "Например: 09:30",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    time_str = callback_query.data.replace('time_', '')
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await callback_query.answer("❌ Ошибка выбора времени")
        return
    
    user_data = await state.get_data()
    
    start_date = user_data.get('start_date')
    start_time = user_data.get('start_time')
    end_date = user_data.get('end_date')
    
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, time_obj)
    
    if start_date == end_date and time_obj <= start_time:
        await callback_query.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    if end_datetime <= start_datetime:
        await callback_query.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    await state.update_data(end_time=time_obj)
    
    price_per_hour = user_data.get('price_hour')
    price_per_day = user_data.get('price_day')
    total_price, duration_hours = calculate_price(price_per_hour, price_per_day, start_datetime, end_datetime)
    
    await state.update_data(total_price=total_price, duration_hours=duration_hours)
    
    spot_number = user_data.get('spot_number')
    
    if start_date == end_date:
        period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(time_obj)}"
    else:
        period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(time_obj)}"
    
    confirmation_text = (
        f"✅ <b>Подтверждение добавления места</b>\n\n"
        f"📍 <b>Номер места:</b> {spot_number}\n"
        f"💰 <b>Цена за час:</b> {price_per_hour} руб.\n"
        f"💰 <b>Цена за сутки:</b> {price_per_day} руб.\n"
        f"📅 <b>Период аренды:</b> {period_text}\n"
        f"⏱️ <b>Продолжительность:</b> {duration_hours:.1f} ч.\n"
        f"💰 <b>Общая стоимость:</b> {total_price:.2f} руб.\n\n"
        f"Все верно?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Да, добавить", callback_data="confirm_add_spot"),
        types.InlineKeyboardButton("❌ Нет, изменить", callback_data="change_spot_data")
    )
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    await bot.send_message(callback_query.from_user.id, confirmation_text, reply_markup=markup)
    await AddParkingSpot.waiting_for_confirmation.set()
    await callback_query.answer()

@dp.message_handler(state=AddParkingSpot.waiting_for_end_time)
async def process_end_time_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    time_str = message.text.strip()
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await message.answer("❌ Неверный формат времени. Введите ЧЧ:ММ:")
        return
    
    user_data = await state.get_data()
    
    start_date = user_data.get('start_date')
    start_time = user_data.get('start_time')
    end_date = user_data.get('end_date')
    
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, time_obj)
    
    if start_date == end_date and time_obj <= start_time:
        await message.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    if end_datetime <= start_datetime:
        await message.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    await state.update_data(end_time=time_obj)
    
    price_per_hour = user_data.get('price_hour')
    price_per_day = user_data.get('price_day')
    total_price, duration_hours = calculate_price(price_per_hour, price_per_day, start_datetime, end_datetime)
    
    await state.update_data(total_price=total_price, duration_hours=duration_hours)
    
    spot_number = user_data.get('spot_number')
    
    if start_date == end_date:
        period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(time_obj)}"
    else:
        period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(time_obj)}"
    
    confirmation_text = (
        f"✅ <b>Подтверждение добавления места</b>\n\n"
        f"📍 <b>Номер места:</b> {spot_number}\n"
        f"💰 <b>Цена за час:</b> {price_per_hour} руб.\n"
        f"💰 <b>Цена за сутки:</b> {price_per_day} руб.\n"
        f"📅 <b>Период аренды:</b> {period_text}\n"
        f"⏱️ <b>Продолжительность:</b> {duration_hours:.1f} ч.\n"
        f"💰 <b>Общая стоимость:</b> {total_price:.2f} руб.\n\n"
        f"Все верно?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Да, добавить", callback_data="confirm_add_spot"),
        types.InlineKeyboardButton("❌ Нет, изменить", callback_data="change_spot_data")
    )
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    await message.answer(confirmation_text, reply_markup=markup)
    await AddParkingSpot.waiting_for_confirmation.set()

@dp.callback_query_handler(lambda c: c.data == 'confirm_add_spot', state=AddParkingSpot.waiting_for_confirmation)
async def confirm_add_spot_final(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    spot_id = db.add_parking_spot(
        owner_id=callback_query.from_user.id,
        spot_number=user_data['spot_number'],
        price_per_hour=user_data['price_hour'],
        price_per_day=user_data['price_day']
    )
    
    if not spot_id:
        await callback_query.message.edit_text(
            "❌ <b>Ошибка!</b>\n"
            "Не удалось добавить место. Возможно, место с таким номером уже существует."
        )
        await state.finish()
        return
    
    start_date = user_data.get('start_date')
    start_time = user_data.get('start_time')
    end_date = user_data.get('end_date')
    end_time = user_data.get('end_time')
    
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, end_time)
    
    period_id = db.add_availability_period(
        spot_id=spot_id,
        start_datetime=start_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        end_datetime=end_datetime.strftime("%Y-%m-%d %H:%M:%S")
    )
    
    if not period_id:
        await callback_query.message.edit_text(
            "❌ <b>Ошибка!</b>\n"
            "Не удалось добавить период доступности."
        )
        await state.finish()
        return
    
    try:
        user = callback_query.from_user
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"🅿️ <b>Добавлено новое место</b>\n"
            f"Место: {user_data['spot_number']}\n"
            f"Владелец: @{user.username if user.username else 'нет'}\n"
            f"Цена/час: {user_data['price_hour']} руб.\n"
            f"Период: {format_datetime(start_datetime)} - {format_datetime(end_datetime)}"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")
    
    success_text = (
        f"✅ <b>Место успешно добавлено!</b>\n\n"
        f"📍 <b>Номер места:</b> {user_data['spot_number']}\n"
        f"💰 <b>Цена за час:</b> {user_data['price_hour']} руб.\n"
        f"💰 <b>Цена за сутки:</b> {user_data['price_day']} руб.\n"
        f"📅 <b>Период аренды:</b>\n"
    )
    
    if start_date == end_date:
        success_text += f"  {format_date(start_date)} с {format_time(start_time)} до {format_time(end_time)}\n"
    else:
        success_text += f"  с {format_date(start_date)} {format_time(start_time)}\n"
        success_text += f"  по {format_date(end_date)} {format_time(end_time)}\n"
    
    success_text += f"⏱️ <b>Продолжительность:</b> {user_data.get('duration_hours', 0):.1f} ч.\n"
    success_text += f"💰 <b>Стоимость за период:</b> {user_data.get('total_price', 0):.2f} руб.\n\n"
    success_text += "Теперь другие пользователи могут бронировать ваше место!"
    
    await callback_query.message.edit_text(success_text)
    
    await asyncio.sleep(2)
    await show_main_menu(callback_query.message)
    
    await state.finish()
    await callback_query.answer()

# ============ FIND FREE SPOTS ============
@dp.message_handler(lambda message: message.text == "🔍 Найти свободные места")
async def cmd_view_free_spots(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    await message.answer("🔍 <b>Поиск свободных мест</b>\n\n"
                      "Выберите период для просмотра свободных мест:",
                      reply_markup=get_free_spots_period_keyboard())
    await ViewFreeSpots.waiting_for_days_ahead.set()

@dp.callback_query_handler(lambda c: c.data.startswith('free_spots_'), state=ViewFreeSpots.waiting_for_days_ahead)
async def process_free_spots_period(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "custom_free_period":
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Введите количество дней для просмотра (максимум 30):",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    days = int(callback_query.data.replace('free_spots_', ''))
    
    free_periods = db.get_next_available_periods(days_ahead=days, limit=50)
    
    if not free_periods:
        await callback_query.message.edit_text(
            f"❌ <b>На ближайшие {days} дней нет свободных мест.</b>\n\n"
            "Попробуйте выбрать другой период или подпишитесь на уведомления.",
            reply_markup=get_free_spots_period_keyboard()
        )
        await callback_query.answer()
        return
    
    spots_by_day = {}
    for period in free_periods:
        start_dt = datetime.strptime(period['start_datetime'], "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(period['end_datetime'], "%Y-%m-%d %H:%M:%S")
        date_key = start_dt.strftime("%d.%m.%Y")
        
        if date_key not in spots_by_day:
            spots_by_day[date_key] = []
        
        start_time = start_dt.strftime("%H:%M")
        end_time = end_dt.strftime("%H:%M")
        duration_hours = (end_dt - start_dt).total_seconds() / 3600
        
        spots_by_day[date_key].append({
            'spot_number': period['spot_number'],
            'price_per_hour': period['price_per_hour'],
            'start_time': start_time,
            'end_time': end_time,
            'duration': f"{duration_hours:.1f} ч.",
            'owner': period['first_name'] or period['username'] or "Владелец"
        })
    
    response = f"🔍 <b>Свободные места на ближайшие {days} дней:</b>\n\n"
    
    for date, spots in list(spots_by_day.items())[:10]:
        response += f"📅 <b>{date}</b>\n"
        
        for spot in spots[:5]:
            response += (
                f"  • {spot['spot_number']} - {spot['start_time']}-{spot['end_time']} "
                f"({spot['duration']})\n"
                f"    💰 {spot['price_per_hour']} руб./час | 👤 {spot['owner']}\n"
            )
        
        response += "\n"
    
    if len(spots_by_day) > 10:
        response += f"\n<i>И еще на {len(spots_by_day) - 10} дней...</i>"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📅 Забронировать", callback_data="book_from_free_list"),
        types.InlineKeyboardButton("🔄 Другой период", callback_data="change_free_period")
    )
    markup.add(types.InlineKeyboardButton("🔔 Подписаться на уведомления", callback_data="subscribe_all_notifications"))
    
    await callback_query.message.edit_text(response, reply_markup=markup)
    await state.finish()
    await callback_query.answer()

@dp.message_handler(state=ViewFreeSpots.waiting_for_days_ahead)
async def process_custom_free_period(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    try:
        days = int(message.text.strip())
        if days <= 0 or days > 30:
            await message.answer("❌ Введите число от 1 до 30:")
            return
        
        free_periods = db.get_next_available_periods(days_ahead=days, limit=50)
        
        if not free_periods:
            await message.answer(
                f"❌ <b>На ближайшие {days} дней нет свободных мест.</b>\n\n"
                "Попробуйте выбрать другой период или подпишитесь на уведомления.",
                reply_markup=get_free_spots_period_keyboard()
            )
            return
        
        spots_by_day = {}
        for period in free_periods:
            start_dt = datetime.strptime(period['start_datetime'], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(period['end_datetime'], "%Y-%m-%d %H:%M:%S")
            date_key = start_dt.strftime("%d.%m.%Y")
            
            if date_key not in spots_by_day:
                spots_by_day[date_key] = []
            
            start_time = start_dt.strftime("%H:%M")
            end_time = end_dt.strftime("%H:%M")
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
            
            spots_by_day[date_key].append({
                'spot_number': period['spot_number'],
                'price_per_hour': period['price_per_hour'],
                'start_time': start_time,
                'end_time': end_time,
                'duration': f"{duration_hours:.1f} ч.",
                'owner': period['first_name'] or period['username'] or "Владелец"
            })
        
        response = f"🔍 <b>Свободные места на ближайшие {days} дней:</b>\n\n"
        
        for date, spots in list(spots_by_day.items())[:10]:
            response += f"📅 <b>{date}</b>\n"
            
            for spot in spots[:5]:
                response += (
                    f"  • {spot['spot_number']} - {spot['start_time']}-{spot['end_time']} "
                    f"({spot['duration']})\n"
                    f"    💰 {spot['price_per_hour']} руб./час | 👤 {spot['owner']}\n"
                )
            
            response += "\n"
        
        if len(spots_by_day) > 10:
            response += f"\n<i>И еще на {len(spots_by_day) - 10} дней...</i>"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📅 Забронировать", callback_data="book_from_free_list"),
            types.InlineKeyboardButton("🔄 Другой период", callback_data="change_free_period")
        )
        markup.add(types.InlineKeyboardButton("🔔 Подписаться на уведомления", callback_data="subscribe_all_notifications"))
        
        await message.answer(response, reply_markup=markup)
        await state.finish()
        
    except ValueError:
        await message.answer("❌ Введите корректное число:")

@dp.callback_query_handler(lambda c: c.data == 'change_free_period')
async def change_free_period(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        "🔍 <b>Поиск свободных мест</b>\n\n"
        "Выберите период для просмотра свободных мест:",
        reply_markup=get_free_spots_period_keyboard()
    )
    await ViewFreeSpots.waiting_for_days_ahead.set()
    await callback_query.answer()

# ============ BOOK PARKING SPOT ============
@dp.message_handler(lambda message: message.text == "📅 Найти место")
async def cmd_find_spot(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    await message.answer("📅 <b>Поиск свободного места</b>\n\n"
                      "Укажите дату и время начала аренды.\n"
                      "Выберите дату или введите свою в формате ДД.ММ.ГГГГ:",
                      reply_markup=get_date_selection_keyboard("book_start"))
    await BookParkingSpot.waiting_for_start_date.set()

@dp.callback_query_handler(lambda c: c.data.startswith('book_start_date_'), state=BookParkingSpot.waiting_for_start_date)
async def process_book_start_date(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "book_start_custom_date":
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Введите дату начала в формате ДД.ММ.ГГГГ:\n"
            "Или введите 'сегодня' или 'завтра'",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    date_str = callback_query.data.replace('book_start_date_', '')
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        await callback_query.answer("❌ Ошибка выбора даты")
        return
    
    await state.update_data(start_date=selected_date)
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🕐 <b>Укажите время начала аренды</b>\n\n"
        f"Дата: {format_date(selected_date)}\n"
        f"Выберите время начала или введите свое в формате ЧЧ:ММ:",
        reply_markup=get_time_selection_keyboard()
    )
    await BookParkingSpot.waiting_for_start_time.set()
    await callback_query.answer()

@dp.message_handler(state=BookParkingSpot.waiting_for_start_date)
async def process_book_start_date_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    date_input = message.text.strip().lower()
    
    if date_input == "сегодня":
        selected_date = datetime.now().date()
    elif date_input == "завтра":
        selected_date = datetime.now().date() + timedelta(days=1)
    else:
        selected_date = parse_date(date_input)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите ДД.ММ.ГГГГ:")
        return
    
    today = datetime.now().date()
    if selected_date < today:
        await message.answer("❌ Нельзя выбрать прошедшую дату. Введите будущую дату:")
        return
    
    await state.update_data(start_date=selected_date)
    
    await message.answer(f"🕐 <b>Укажите время начала аренды</b>\n\n"
                      f"Дата: {format_date(selected_date)}\n"
                      f"Выберите время начала или введите свое в формате ЧЧ:ММ:",
                      reply_markup=get_time_selection_keyboard())
    await BookParkingSpot.waiting_for_start_time.set()

@dp.callback_query_handler(lambda c: c.data.startswith('time_'), state=BookParkingSpot.waiting_for_start_time)
async def process_book_start_time(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "custom_time":
        await bot.send_message(
            callback_query.from_user.id,
            "🕐 Введите время начала в формате ЧЧ:ММ:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    time_str = callback_query.data.replace('time_', '')
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await callback_query.answer("❌ Ошибка выбора времени")
        return
    
    await state.update_data(start_time=time_obj)
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    await bot.send_message(
        callback_query.from_user.id,
        f"📅 <b>Укажите дату окончания аренды</b>\n\n"
        f"Начало: {format_date(start_date)} {format_time(time_obj)}\n\n"
        f"Выберите дату окончания или введите свою в формате ДД.ММ.ГГГГ:\n"
        f"<i>Можно указать ту же дату, если аренда в пределах одного дня</i>",
        reply_markup=get_date_selection_keyboard("book_end")
    )
    await BookParkingSpot.waiting_for_end_date.set()
    await callback_query.answer()

@dp.message_handler(state=BookParkingSpot.waiting_for_start_time)
async def process_book_start_time_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    time_str = message.text.strip()
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await message.answer("❌ Неверный формат времени. Введите ЧЧ:ММ:")
        return
    
    await state.update_data(start_time=time_obj)
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    await message.answer(f"📅 <b>Укажите дату окончания аренды</b>\n\n"
                      f"Начало: {format_date(start_date)} {format_time(time_obj)}\n\n"
                      f"Выберите дату окончания или введите свою в формате ДД.ММ.ГГГГ:\n"
                      f"<i>Можно указать ту же дату, если аренда в пределах одного день</i>",
                      reply_markup=get_date_selection_keyboard("book_end"))
    await BookParkingSpot.waiting_for_end_date.set()

@dp.callback_query_handler(lambda c: c.data.startswith('book_end_date_'), state=BookParkingSpot.waiting_for_end_date)
async def process_book_end_date(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "book_end_custom_date":
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Введите дату окончания в формате ДД.ММ.ГГГГ:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    date_str = callback_query.data.replace('book_end_date_', '')
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        await callback_query.answer("❌ Ошибка выбора даты")
        return
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    if selected_date < start_date:
        await callback_query.answer("❌ Дата окончания не может быть раньше даты начала!")
        return
    
    await state.update_data(end_date=selected_date)
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🕐 <b>Укажите время окончания аренды</b>\n\n"
        f"Начало: {format_date(start_date)} {format_time(user_data.get('start_time'))}\n"
        f"Окончание: {format_date(selected_date)}\n\n"
        f"Выберите время окончания или введите свое в формате ЧЧ:ММ:",
        reply_markup=get_time_selection_keyboard()
    )
    await BookParkingSpot.waiting_for_end_time.set()
    await callback_query.answer()

@dp.message_handler(state=BookParkingSpot.waiting_for_end_date)
async def process_book_end_date_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    date_input = message.text.strip()
    selected_date = parse_date(date_input)
    
    if not selected_date:
        await message.answer("❌ Неверный формат даты. Введите ДД.ММ.ГГГГ:")
        return
    
    user_data = await state.get_data()
    start_date = user_data.get('start_date')
    
    if selected_date < start_date:
        await message.answer("❌ Дата окончания не может быть раньше даты начала!")
        return
    
    await state.update_data(end_date=selected_date)
    
    await message.answer(f"🕐 <b>Укажите время окончания аренды</b>\n\n"
                      f"Начало: {format_date(start_date)} {format_time(user_data.get('start_time'))}\n"
                      f"Окончание: {format_date(selected_date)}\n\n"
                      f"Выберите время окончания или введите свое в формате ЧЧ:ММ:",
                      reply_markup=get_time_selection_keyboard())
    await BookParkingSpot.waiting_for_end_time.set()

@dp.callback_query_handler(lambda c: c.data.startswith('time_'), state=BookParkingSpot.waiting_for_end_time)
async def process_book_end_time(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "cancel":
        await state.finish()
        await show_main_menu(callback_query.message)
        return
    
    if callback_query.data == "custom_time":
        await bot.send_message(
            callback_query.from_user.id,
            "🕐 Введите время окончания в формате ЧЧ:ММ:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    time_str = callback_query.data.replace('time_', '')
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await callback_query.answer("❌ Ошибка выбора времени")
        return
    
    user_data = await state.get_data()
    
    start_date = user_data.get('start_date')
    start_time = user_data.get('start_time')
    end_date = user_data.get('end_date')
    
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, time_obj)
    
    if start_date == end_date and time_obj <= start_time:
        await callback_query.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    if end_datetime <= start_datetime:
        await callback_query.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    await state.update_data(end_time=time_obj)
    
    start_datetime_str = start_datetime.strftime("%Y-%m-%d %H:%M:%S")
    end_datetime_str = end_datetime.strftime("%Y-%m-%d %H:%M:%S")
    
    available_spots = db.get_available_spots_by_date_range(start_datetime_str, end_datetime_str)
    
    if not available_spots:
        await state.update_data(
            start_datetime=start_datetime_str,
            end_datetime=end_datetime_str
        )
        
        if start_date == end_date:
            period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(time_obj)}"
        else:
            period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(time_obj)}"
        
        markup = get_no_available_spots_keyboard(start_datetime_str, end_datetime_str)
        
        await bot.send_message(
            callback_query.from_user.id,
            f"❌ <b>На указанный период нет доступных мест</b>\n\n"
            f"Период: {period_text}\n\n"
            "Что вы хотите сделать?",
            reply_markup=markup
        )
        await BookParkingSpot.waiting_for_notification_decision.set()
        await callback_query.answer()
        return
    
    await state.update_data(
        start_datetime=start_datetime_str,
        end_datetime=end_datetime_str
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for spot in available_spots[:10]:
        owner_name = spot['first_name'] or spot['username'] or "Владелец"
        
        button_text = (
            f"📍 {spot['spot_number']} - {spot['price_per_hour']}₽/час"
        )
        
        markup.add(types.InlineKeyboardButton(
            button_text,
            callback_data=f"select_spot_{spot['id']}"
        ))
    
    if len(available_spots) > 10:
        markup.row(types.InlineKeyboardButton(
            f"📋 Показать еще {len(available_spots) - 10} мест",
            callback_data="show_more_spots"
        ))
    
    markup.row(types.InlineKeyboardButton("🔄 Выбрать другой период", callback_data="choose_another_period"))
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    period_text = ""
    if start_date == end_date:
        period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(time_obj)}"
    else:
        period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(time_obj)}"
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🅿️ <b>Доступные места на период:</b>\n"
        f"{period_text}\n\n"
        f"Найдено мест: {len(available_spots)}\n"
        "Выберите место для бронирования:",
        reply_markup=markup
    )
    await BookParkingSpot.waiting_for_spot_selection.set()
    await callback_query.answer()

@dp.message_handler(state=BookParkingSpot.waiting_for_end_time)
async def process_book_end_time_custom(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    time_str = message.text.strip()
    time_obj = parse_time(time_str)
    
    if not time_obj:
        await message.answer("❌ Неверный формат времени. Введите ЧЧ:ММ:")
        return
    
    user_data = await state.get_data()
    
    start_date = user_data.get('start_date')
    start_time = user_data.get('start_time')
    end_date = user_data.get('end_date')
    
    start_datetime = datetime.combine(start_date, start_time)
    end_datetime = datetime.combine(end_date, time_obj)
    
    if start_date == end_date and time_obj <= start_time:
        await message.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    if end_datetime <= start_datetime:
        await message.answer("❌ Время окончания должно быть позже времени начала!")
        return
    
    await state.update_data(end_time=time_obj)
    
    start_datetime_str = start_datetime.strftime("%Y-%m-%d %H:%M:%S")
    end_datetime_str = end_datetime.strftime("%Y-%m-%d %H:%M:%S")
    
    available_spots = db.get_available_spots_by_date_range(start_datetime_str, end_datetime_str)
    
    if not available_spots:
        await state.update_data(
            start_datetime=start_datetime_str,
            end_datetime=end_datetime_str
        )
        
        if start_date == end_date:
            period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(time_obj)}"
        else:
            period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(time_obj)}"
        
        await message.answer(
            f"❌ <b>На указанный период нет доступных мест</b>\n\n"
            f"Период: {period_text}\n\n"
            "Что вы хотите сделать?",
            reply_markup=get_no_available_spots_keyboard(start_datetime_str, end_datetime_str)
        )
        await BookParkingSpot.waiting_for_notification_decision.set()
        return
    
    await state.update_data(
        start_datetime=start_datetime_str,
        end_datetime=end_datetime_str
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for spot in available_spots[:10]:
        owner_name = spot['first_name'] or spot['username'] or "Владелец"
        
        button_text = (
            f"📍 {spot['spot_number']} - {spot['price_per_hour']}₽/час"
        )
        
        markup.add(types.InlineKeyboardButton(
            button_text,
            callback_data=f"select_spot_{spot['id']}"
        ))
    
    if len(available_spots) > 10:
        markup.row(types.InlineKeyboardButton(
            f"📋 Показать еще {len(available_spots) - 10} мест",
            callback_data="show_more_spots"
        ))
    
    markup.row(types.InlineKeyboardButton("🔄 Выбрать другой период", callback_data="choose_another_period"))
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    period_text = ""
    if start_date == end_date:
        period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(time_obj)}"
    else:
        period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(time_obj)}"
    
    await message.answer(
        f"🅿️ <b>Доступные места на период:</b>\n"
        f"{period_text}\n\n"
        f"Найдено мест: {len(available_spots)}\n"
        "Выберите место для бронирования:",
        reply_markup=markup
    )
    await BookParkingSpot.waiting_for_spot_selection.set()

@dp.callback_query_handler(lambda c: c.data.startswith('select_spot_'), state=BookParkingSpot.waiting_for_spot_selection)
async def process_select_spot_booking(callback_query: types.CallbackQuery, state: FSMContext):
    spot_id = int(callback_query.data.replace('select_spot_', ''))
    
    spot = db.get_parking_spot(spot_id)
    if not spot:
        await callback_query.answer("❌ Место не найдено")
        return
    
    user_data = await state.get_data()
    
    start_datetime = datetime.strptime(user_data['start_datetime'], "%Y-%m-%d %H:%M:%S")
    end_datetime = datetime.strptime(user_data['end_datetime'], "%Y-%m-%d %H:%M:%S")
    
    available_periods = db.find_available_periods(
        spot_id,
        user_data['start_datetime'],
        user_data['end_datetime']
    )
    
    if not available_periods:
        await callback_query.answer("❌ Это место больше не доступно на выбранный период")
        return
    
    period = available_periods[0]
    
    total_price, duration_hours = calculate_price(
        spot['price_per_hour'],
        spot['price_day'],
        start_datetime,
        end_datetime
    )
    
    await state.update_data(
        selected_spot_id=spot_id,
        selected_period_id=period['id'],
        spot_number=spot['spot_number'],
        price_per_hour=spot['price_per_hour'],
        price_per_day=spot['price_day'],
        total_price=total_price,
        duration_hours=duration_hours
    )
    
    start_date = start_datetime.date()
    end_date = end_datetime.date()
    start_time = start_datetime.time()
    end_time = end_datetime.time()
    
    if start_date == end_date:
        period_text = f"{format_date(start_date)} с {format_time(start_time)} до {format_time(end_time)}"
    else:
        period_text = f"с {format_date(start_date)} {format_time(start_time)} по {format_date(end_date)} {format_time(end_time)}"
    
    confirmation_text = (
        f"✅ <b>Подтверждение бронирования</b>\n\n"
        f"📍 <b>Место:</b> {spot['spot_number']}\n"
        f"👤 <b>Владелец:</b> {spot['first_name'] or spot['username'] or 'Владелец'}\n"
        f"📅 <b>Период:</b> {period_text}\n"
        f"⏱️ <b>Продолжительность:</b> {duration_hours:.1f} ч.\n"
        f"💰 <b>Стоимость:</b> {total_price:.2f} руб.\n\n"
        f"Подтвердить бронирование?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_booking_final"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_booking")
    )
    markup.add(types.InlineKeyboardButton("✏️ Изменить период", callback_data="choose_another_period"))
    
    await callback_query.message.edit_text(confirmation_text, reply_markup=markup)
    await BookParkingSpot.waiting_for_confirmation.set()
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'confirm_booking_final', state=BookParkingSpot.waiting_for_confirmation)
async def confirm_booking_final(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    booking_id = db.create_booking(
        user_id=callback_query.from_user.id,
        spot_id=user_data['selected_spot_id'],
        period_id=user_data['selected_period_id'],
        start_datetime=user_data['start_datetime'],
        end_datetime=user_data['end_datetime'],
        total_price=user_data['total_price']
    )
    
    if not booking_id:
        await callback_query.message.edit_text(
            "❌ <b>Не удалось создать бронирование.</b>\n\n"
            "Возможно, это место уже занято другим пользователем.\n"
            "Пожалуйста, выберите другое место или период."
        )
        await callback_query.answer()
        return
    
    try:
        user = callback_query.from_user
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📅 <b>Новое бронирование #{booking_id}</b>\n"
            f"👤 Пользователь: @{user.username if user.username else 'нет'}\n"
            f"Место: {user_data['spot_number']}\n"
            f"Период: {format_datetime(user_data['start_datetime'])} - {format_datetime(user_data['end_datetime'])}\n"
            f"Сумма: {user_data['total_price']:.2f} руб."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")
    
    try:
        spot = db.get_parking_spot(user_data['selected_spot_id'])
        if spot and spot['owner_id']:
            start_dt = datetime.strptime(user_data['start_datetime'], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(user_data['end_datetime'], "%Y-%m-%d %H:%M:%S")
            
            period_text = ""
            if start_dt.date() == end_dt.date():
                period_text = f"{format_date(start_dt.date())} с {format_time(start_dt.time())} до {format_time(end_dt.time())}"
            else:
                period_text = f"с {format_date(start_dt.date())} {format_time(start_dt.time())} по {format_date(end_dt.date())} {format_time(end_dt.time())}"
            
            await bot.send_message(
                spot['owner_id'],
                f"🔔 <b>Новое бронирование вашего места!</b>\n\n"
                f"📍 Место: {user_data['spot_number']}\n"
                f"👤 Арендатор: @{user.username if user.username else 'не указан'}\n"
                f"📅 Период: {period_text}\n"
                f"💰 Сумма: {user_data['total_price']:.2f} руб.\n\n"
                f"Номер брони: #{booking_id}"
            )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления владельцу: {e}")
    
    start_dt = datetime.strptime(user_data['start_datetime'], "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(user_data['end_datetime'], "%Y-%m-%d %H:%M:%S")
    
    if start_dt.date() == end_dt.date():
        period_text = f"{format_date(start_dt.date())} с {format_time(start_dt.time())} до {format_time(end_dt.time())}"
    else:
        period_text = f"с {format_date(start_dt.date())} {format_time(start_dt.time())} по {format_date(end_dt.date())} {format_time(end_dt.time())}"
    
    success_text = (
        f"✅ <b>Бронирование подтверждено!</b>\n\n"
        f"📋 <b>Детали бронирования:</b>\n"
        f"• Номер брони: #{booking_id}\n"
        f"• Место: {user_data['spot_number']}\n"
        f"• Период: {period_text}\n"
        f"• Продолжительность: {user_data.get('duration_hours', 0):.1f} ч.\n"
        f"• Стоимость: {user_data['total_price']:.2f} руб.\n\n"
        f"ℹ️ Информация о местонахождении парковки будет отправлена вам перед началом аренды."
    )
    
    await callback_query.message.edit_text(success_text)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "📋 Мои бронирования",
        callback_data="view_my_bookings"
    ))
    
    await callback_query.message.reply(
        "Вы можете посмотреть все свои бронирования в разделе '📋 Мои брони'",
        reply_markup=markup
    )
    
    await state.finish()
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith('view_free_spots_'), state=BookParkingSpot.waiting_for_notification_decision)
async def view_free_spots_from_booking(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data.replace('view_free_spots_', '')
    start_datetime_str, end_datetime_str = data.split('_')[:2]
    
    free_periods = db.get_next_available_periods(days_ahead=7, limit=30)
    
    if not free_periods:
        await callback_query.message.edit_text(
            "❌ <b>На ближайшую неделю нет свободных мест.</b>\n\n"
            "Попробуйте выбрать другой период или подпишитесь на уведомления.",
            reply_markup=get_no_available_spots_keyboard(start_datetime_str, end_datetime_str)
        )
        await callback_query.answer()
        return
    
    response = "🔍 <b>Свободные места на ближайшие 7 дней:</b>\n\n"
    
    spots_by_day = {}
    for period in free_periods:
        start_dt = datetime.strptime(period['start_datetime'], "%Y-%m-%d %H:%M:%S")
        date_key = start_dt.strftime("%d.%m.%Y")
        
        if date_key not in spots_by_day:
            spots_by_day[date_key] = []
        
        end_dt = datetime.strptime(period['end_datetime'], "%Y-%m-%d %H:%M:%S")
        start_time = start_dt.strftime("%H:%M")
        end_time = end_dt.strftime("%H:%M")
        duration_hours = (end_dt - start_dt).total_seconds() / 3600
        
        spots_by_day[date_key].append({
            'spot_number': period['spot_number'],
            'price_per_hour': period['price_per_hour'],
            'start_time': start_time,
            'end_time': end_time,
            'duration': f"{duration_hours:.1f} ч.",
            'owner': period['first_name'] or period['username'] or "Владелец"
        })
    
    for date, spots in list(spots_by_day.items())[:5]:
        response += f"📅 <b>{date}</b>\n"
        
        for spot in spots[:3]:
            response += (
                f"  • {spot['spot_number']} - {spot['start_time']}-{spot['end_time']} "
                f"({spot['duration']})\n"
                f"    💰 {spot['price_per_hour']} руб./час\n"
            )
        
        response += "\n"
    
    if len(spots_by_day) > 5:
        response += f"\n<i>И еще на {len(spots_by_day) - 5} дней...</i>"
    
    start_dt = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M:%S")
    
    if start_dt.date() == end_dt.date():
        period_text = f"{format_date(start_dt.date())} с {format_time(start_dt.time())} до {format_time(end_dt.time())}"
    else:
        period_text = f"с {format_date(start_dt.date())} {format_time(start_dt.time())} по {format_date(end_dt.date())} {format_time(end_dt.time())}"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(
        "🔔 Упоминуть при появлении на мой период",
        callback_data=f"notify_when_available_{start_datetime_str}_{end_datetime_str}"
    ))
    markup.add(types.InlineKeyboardButton(
        "📅 Искать другой период",
        callback_data="choose_another_period"
    ))
    markup.add(types.InlineKeyboardButton("🔍 Больше свободных мест", callback_data="view_more_free_spots"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    
    await callback_query.message.edit_text(
        f"{response}\n"
        f"📅 <b>Ваш исходный период:</b> {period_text}\n\n"
        "Вы можете подписаться на уведомления о появлении мест на ваш период.",
        reply_markup=markup
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith('notify_when_available_'), state=BookParkingSpot.waiting_for_notification_decision)
async def notify_when_available(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data.replace('notify_when_available_', '')
    start_datetime_str, end_datetime_str = data.split('_')[:2]
    
    user_id = callback_query.from_user.id
    
    notification_id = db.add_availability_notification(
        user_id=user_id,
        spot_id=None,
        start_datetime=start_datetime_str,
        end_datetime=end_datetime_str
    )
    
    if notification_id:
        start_dt = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_datetime_str, "%Y-%m-%d %H:%M:%S")
        
        if start_dt.date() == end_dt.date():
            period_text = f"{format_date(start_dt.date())} с {format_time(start_dt.time())} до {format_time(end_dt.time())}"
        else:
            period_text = f"с {format_date(start_dt.date())} {format_time(start_dt.time())} по {format_date(end_dt.date())} {format_time(end_dt.time())}"
        
        await callback_query.message.edit_text(
            f"🔔 <b>Вы подписались на уведомления!</b>\n\n"
            f"Мы уведомим вас, когда появится свободное место на период:\n"
            f"{period_text}\n\n"
            "Как только место появится, мы сразу отправим вам уведомление.\n"
            "Вы можете управлять своими подписками в разделе '🔔 Мои уведомления'."
        )
        
        db.add_notification(user_id, f"✅ Вы подписались на уведомления о свободных местах на период: {period_text}")
    else:
        await callback_query.message.edit_text(
            "❌ <b>Не удалось создать подписку.</b>\n\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )
    
    await state.finish()
    await asyncio.sleep(3)
    await show_main_menu(callback_query.message)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'choose_another_period', state="*")
async def choose_another_period(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    
    await callback_query.message.edit_text(
        "📅 <b>Поиск свободного места</b>\n\n"
        "Укажите дату и время начала аренды.\n"
        "Выберите дату или введите свою в формате ДД.ММ.ГГГГ:",
        reply_markup=get_date_selection_keyboard("book_start")
    )
    await BookParkingSpot.waiting_for_start_date.set()
    await callback_query.answer()

# ============ MY NOTIFICATIONS ============
@dp.message_handler(lambda message: message.text == "🔔 Мои уведомления")
async def cmd_my_notifications(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    notifications = db.get_user_notifications(message.from_user.id)
    
    if not notifications:
        await message.answer(
            "🔔 <b>У вас нет активных подписок на уведомления</b>\n\n"
            "Вы можете подписаться на уведомления при поиске места, "
            "если на нужный период нет свободных мест."
        )
        return
    
    response = "🔔 <b>Ваши активные подписки на уведомления:</b>\n\n"
    
    for i, notification in enumerate(notifications, 1):
        start_dt = datetime.strptime(notification['start_datetime'], "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(notification['end_datetime'], "%Y-%m-%d %H:%M:%S")
        
        if start_dt.date() == end_dt.date():
            period_text = f"{format_date(start_dt.date())} {format_time(start_dt.time())}-{format_time(end_dt.time())}"
        else:
            period_text = f"{format_datetime(start_dt)} - {format_datetime(end_dt)}"
        
        spot_text = f"📍 {notification['spot_number']}" if notification['spot_number'] else "📍 Любое место"
        
        response += (
            f"{i}. {spot_text}\n"
            f"   📅 {period_text}\n"
            f"   [ID: {notification['id']}]\n\n"
        )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("❌ Удалить все подписки", callback_data="delete_all_notifications"),
        types.InlineKeyboardButton("📝 Управлять подписками", callback_data="manage_notifications")
    )
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back_to_main"))
    
    await message.answer(response, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'delete_all_notifications')
async def delete_all_notifications(callback_query: types.CallbackQuery):
    notifications = db.get_user_notifications(callback_query.from_user.id)
    
    if not notifications:
        await callback_query.answer("❌ У вас нет активных подписок")
        return
    
    for notification in notifications:
        db.remove_notification(notification['id'])
    
    await callback_query.message.edit_text(
        "✅ <b>Все ваши подписки удалены.</b>\n\n"
        "Вы больше не будете получать уведомления о появлении свободных мест."
    )
    
    db.add_notification(callback_query.from_user.id, "❌ Все ваши подписки на уведомления удалены")
    
    await asyncio.sleep(2)
    await show_main_menu(callback_query.message)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'manage_notifications')
async def manage_notifications(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        "🔔 <b>Управление подписками</b>\n\n"
        "Для управления подписками отправьте ID подписки, которую хотите удалить.\n"
        "ID указан в квадратных скобках в списке подписок.\n\n"
        "Пример: <code>удалить 5</code> или <code>5</code>"
    )
    
    await ManageNotifications.waiting_for_action.set()
    await callback_query.answer()

@dp.message_handler(state=ManageNotifications.waiting_for_action)
async def process_notification_action(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await show_main_menu(message)
        return
    
    text = message.text.lower().strip()
    import re
    numbers = re.findall(r'\d+', text)
    
    if not numbers:
        await message.answer("❌ Не найден ID подписки. Попробуйте еще раз:")
        return
    
    notification_id = int(numbers[0])
    
    notifications = db.get_user_notifications(message.from_user.id)
    notification_exists = any(n['id'] == notification_id for n in notifications)
    
    if not notification_exists:
        await message.answer("❌ Подписка с таким ID не найдена или не принадлежит вам. Попробуйте еще раз:")
        return
    
    if db.remove_notification(notification_id):
        await message.answer(f"✅ Подписка #{notification_id} успешно удалена.")
        db.add_notification(message.from_user.id, f"❌ Подписка #{notification_id} удалена")
    else:
        await message.answer("❌ Не удалось удалить подписку. Попробуйте еще раз:")
        return
    
    await state.finish()
    await asyncio.sleep(1)
    await cmd_my_notifications(message)

# ============ MY SPOTS ============
@dp.message_handler(lambda message: message.text == "📊 Мои места")
async def cmd_my_spots(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    spots = db.get_user_spots(message.from_user.id)
    
    if not spots:
        await message.answer(
            "🚗 <b>У вас пока нет добавленных мест</b>\n\n"
            "Хотите добавить свое парковочное место для аренды?\n"
            "Нажмите '🚗 Сдать место' в главном меню."
        )
        return
    
    all_active_spots = db.get_all_active_spots()
    
    response = "📍 <b>Ваши парковочные места:</b>\n\n"
    
    for spot in spots:
        response += (
            f"<b>Место: {spot['spot_number']}</b>\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"📅 Доступных периодов: {spot['total_periods'] - spot.get('booked_periods', 0)}\n"
            f"📅 Забронировано: {spot.get('active_bookings', 0)}\n"
            f"────────────────────\n"
        )
    
    other_spots = [s for s in all_active_spots if s['owner_id'] != message.from_user.id]
    
    if other_spots:
        response += f"\n🔍 <b>Всего активных мест в системе: {len(all_active_spots)}</b>\n"
        response += f"👤 <b>Ваших мест: {len(spots)}</b>\n"
        response += f"👥 <b>Мест других пользователей: {len(other_spots)}</b>\n\n"
        
        response += "<b>Последние добавленные места:</b>\n"
        for spot in other_spots[:3]:
            owner_name = spot['first_name'] or spot['username'] or "Владелец"
            response += f"• {spot['spot_number']} - {spot['price_per_hour']} руб./час ({owner_name})\n"
    
    await message.answer(response)

# ============ MY BOOKINGS ============
@dp.message_handler(lambda message: message.text == "📋 Мои брони")
async def cmd_my_bookings(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    bookings = db.get_user_bookings(message.from_user.id, include_cancelled=False)
    
    if not bookings:
        await message.answer(
            "📋 <b>У вас пока нет активных бронирований</b>\n\n"
            "Найдите свободное место через меню '📅 Найти место'"
        )
        return
    
    response = "📋 <b>Ваши бронирования:</b>\n\n"
    
    for booking in bookings[:5]:
        start_dt = datetime.strptime(booking['start_datetime'], "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(booking['end_datetime'], "%Y-%m-%d %H:%M:%S")
        
        if start_dt.date() == end_dt.date():
            period_text = f"{format_date(start_dt.date())} {format_time(start_dt.time())}-{format_time(end_dt.time())}"
        else:
            period_text = f"{format_datetime(start_dt)} - {format_datetime(end_dt)}"
        
        response += (
            f"<b>Бронь #{booking['id']}</b>\n"
            f"📍 Место: {booking['spot_number']}\n"
            f"📅 Период: {period_text}\n"
            f"💰 Стоимость: {booking['total_price']} руб.\n"
            f"📊 Статус: {booking['status']}\n"
            f"────────────────────\n"
        )
    
    if len(bookings) > 5:
        response += f"\n<i>И еще {len(bookings) - 5} бронирований...</i>"
    
    await message.answer(response)

# ============ PROFILE ============
@dp.message_handler(lambda message: message.text == "👤 Профиль")
async def cmd_profile(message: types.Message):
    if not db.check_user_exists(message.from_user.id):
        await message.answer("⚠️ Сначала зарегистрируйтесь через /start")
        return
    
    user = db.get_user(message.from_user.id)
    spots = db.get_user_spots(message.from_user.id)
    bookings = db.get_user_bookings(message.from_user.id)
    
    response = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>Основная информация:</b>\n"
        f"• Имя: {user['first_name']}\n"
        f"• Телефон: {user['phone']}\n"
        f"• Username: @{user['username'] if user['username'] else 'не указан'}\n"
        f"• ID: {user['user_id']}\n\n"
        
        f"<b>Статистика:</b>\n"
        f"• Мест добавлено: {len(spots)}\n"
        f"• Активных броней: {len([b for b in bookings if b['status'] == 'active'])}\n"
        f"• Всего броней: {len(bookings)}\n"
    )
    
    if db.is_admin(message.from_user.id):
        response += f"\n👑 <b>Статус:</b> Администратор\n"
    
    await message.answer(response)

# ============ HELP ============
@dp.message_handler(lambda message: message.text == "ℹ️ Помощь")
async def cmd_help(message: types.Message):
    help_text = (
        "ℹ️ <b>Помощь по использованию бота</b>\n\n"
        
        "<b>Основные функции:</b>\n"
        "• <b>🚗 Сдать место</b> - сдать свое парковочное место в аренду\n"
        "• <b>📅 Найти место</b> - найти и забронировать свободное место\n"
        "• <b>🔍 Найти свободные места</b> - посмотреть все свободные места на период\n"
        "• <b>📊 Мои места</b> - просмотреть и управлять своими местами\n"
        "• <b>📋 Мои брони</b> - просмотреть свои бронирования\n"
        "• <b>🔔 Мои уведомления</b> - управление подписками на уведомления\n"
        "• <b>👤 Профиль</b> - информация о вашем аккаунте\n\n"
        
        "<b>Новые возможности:</b>\n"
        "• 🔔 <b>Уведомления о свободных местах</b> - подпишитесь на уведомление, если на нужный период нет свободных мест\n"
        "• 🔍 <b>Поиск всех свободных мест</b> - посмотрите все свободные места на любой период\n"
        "• 📊 <b>Обзор рынка</b> - увидите сколько всего мест в системе и их стоимость\n\n"
        
        "<b>Что делать если нет свободных мест?</b>\n"
        "1. Нажмите кнопку '🔍 Посмотреть свободные места' - увидите все свободные места на ближайшие дни\n"
        "2. Нажмите кнопку '🔔 Упоминуть при появлении' - получите уведомление, когда появится место на ваш период\n"
        "3. Попробуйте выбрать другой период времени\n\n"
        
        "<b>Контакты поддержки:</b>\n"
        "По вопросам работы бота обращайтесь к администратору.\n\n"
        
        "<b>Команды:</b>\n"
        "/start - начало работы\n"
        "/help - эта справка\n"
        "/notifications - уведомления\n"
        "/admin - панель администратора (если есть доступ)"
    )
    
    await message.answer(help_text)

# ============ NOTIFICATIONS COMMAND ============
@dp.message_handler(commands=['notifications'])
async def cmd_notifications_command(message: types.Message):
    await cmd_my_notifications(message)

# ============ CANCEL HANDLER ============
@dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
async def cancel_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_main_menu(callback_query.message)
    await callback_query.answer("❌ Действие отменено")

@dp.message_handler(lambda message: message.text == "❌ Отмена", state="*")
async def cancel_text(message: types.Message, state: FSMContext):
    await state.finish()
    await show_main_menu(message)

@dp.callback_query_handler(lambda c: c.data == 'back_to_main')
async def back_to_main_callback(callback_query: types.CallbackQuery):
    await show_main_menu(callback_query.message)
    await callback_query.answer()

# ============ ADMIN PANEL ============
@dp.message_handler(lambda message: message.text == "👑 Админ-панель")
async def cmd_admin_panel(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    markup = get_admin_keyboard()
    await message.answer("👑 <b>Админ-панель</b>\n\n"
                      "Выберите раздел для управления:",
                      reply_markup=markup)

@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def admin_statistics(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа")
        return
    
    stats = db.get_statistics()
    
    response = (
        "📊 <b>Общая статистика:</b>\n\n"
        
        "<b>Пользователи:</b>\n"
        f"• Всего пользователей: {stats.get('total_users', 0)}\n"
        f"• Активных мест: {stats.get('active_spots', 0)}\n\n"
        
        "<b>Бронирования:</b>\n"
        f"• Всего бронирований: {stats.get('total_bookings', 0)}\n"
        f"• Активных броней: {stats.get('active_bookings', 0)}\n\n"
        
        "<b>Периоды:</b>\n"
        f"• Доступных периодов: {stats.get('available_periods', 0)}\n"
        f"• Занятых периодов: {stats.get('booked_periods', 0)}\n\n"
        
        "<b>Уведомления:</b>\n"
        f"• Активных подписок: {stats.get('active_notifications', 0)}\n\n"
        
        "<b>Финансы:</b>\n"
        f"• Общий доход: {stats.get('total_income', 0):.2f} руб.\n"
    )
    
    await message.answer(response)

@dp.message_handler(lambda message: message.text == "🔙 Главное меню")
async def back_to_main(message: types.Message):
    await show_main_menu(message)

# ============ ERROR HANDLER ============
@dp.errors_handler()
async def errors_handler(update, exception):
    logger.error(f"Ошибка: {exception}")
    
    try:
        if hasattr(update, 'message'):
            await update.message.answer(
                "❌ <b>Произошла ошибка</b>\n\n"
                "Попробуйте выполнить действие еще раз.\n"
                "Если ошибка повторяется, обратитесь к администратору."
            )
    except:
        pass
    
    return True

# ============ COMMON MESSAGE HANDLER ============
@dp.message_handler(state="*", content_types=types.ContentTypes.ANY)
async def handle_unknown(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state:
        await message.answer("Пожалуйста, введите текст или используйте кнопки меню")
    else:
        await show_main_menu(message)

# ============ MAIN ============
if __name__ == '__main__':
    logger.info("Бот запускается...")
    
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
