import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from datetime import datetime, timedelta
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
    waiting_for_time_range = State()

class BookParkingSpot(StatesGroup):
    waiting_for_date_selection = State()
    waiting_for_spot_selection = State()
    waiting_for_time_selection = State()
    waiting_for_confirmation = State()

class AdminPanel(StatesGroup):
    waiting_for_password = State()

# Вспомогательные функции
def get_next_days():
    """Получение ближайших 4 дней"""
    today = datetime.now().date()
    return [today + timedelta(days=i) for i in range(4)]

def format_date(date):
    """Форматирование даты в строку"""
    return date.strftime("%d.%m.%Y")

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем существование пользователя
    if not db.check_user_exists(user_id):
        # Берем username автоматически
        username = message.from_user.username or "не указан"
        
        # Запрашиваем имя
        await message.answer(f"👋 Добро пожаловать! Ваш username: @{username}")
        await message.answer("📝 Введите ваше имя:")
        await UserRegistration.waiting_for_name.set()
    else:
        # Показываем главное меню
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("🚗 Добавить парковочное место", "📅 Забронировать место")
        markup.add("📊 Мои места", "📋 Мои бронирования")
        await message.answer("🎉 С возвращением! Что вы хотите сделать?", reply_markup=markup)

# Регистрация пользователя
@dp.message_handler(state=UserRegistration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📱 Теперь введите ваш номер телефона:")
    await UserRegistration.waiting_for_phone.set()

@dp.message_handler(state=UserRegistration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text
    user_data = await state.get_data()
    user = message.from_user
    
    # Сохраняем пользователя в БД
    success = db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user_data['name'],
        phone=phone
    )
    
    if success:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("🚗 Добавить парковочное место", "📅 Забронировать место")
        markup.add("📊 Мои места", "📋 Мои бронирования")
        
        await message.answer("✅ Регистрация завершена!", reply_markup=markup)
        
        # Уведомление админу
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"👤 Новый пользователь зарегистрирован:\n"
            f"Имя: {user_data['name']}\n"
            f"Телефон: {phone}\n"
            f"Username: @{user.username}"
        )
    else:
        await message.answer("❌ Ошибка при регистрации. Попробуйте еще раз.")
    
    await state.finish()

# Добавление парковочного места
@dp.message_handler(lambda message: message.text == "🚗 Добавить парковочное место")
async def cmd_add_spot(message: types.Message):
    await message.answer("🚗 Введите номер парковочного места (например, A-15):")
    await AddParkingSpot.waiting_for_spot_number.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_spot_number)
async def process_spot_number(message: types.Message, state: FSMContext):
    await state.update_data(spot_number=message.text)
    await message.answer("💰 Введите цену за час в рублях (например: 100):")
    await AddParkingSpot.waiting_for_price_hour.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_price_hour)
async def process_price_hour(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price_hour=price)
        await message.answer("💰 Введите цену за сутки в рублях (например: 800):")
        await AddParkingSpot.waiting_for_price_day.set()
    except:
        await message.answer("❌ Введите корректную сумму (только цифры):")

@dp.message_handler(state=AddParkingSpot.waiting_for_price_day)
async def process_price_day(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price_day=price)
        
        # Показываем ближайшие 4 дня
        days = get_next_days()
        markup = types.InlineKeyboardMarkup(row_width=2)
        for day in days:
            markup.insert(types.InlineKeyboardButton(
                format_date(day),
                callback_data=f"add_date_{day}"
            ))
        
        await message.answer("📅 Выберите дату для сдачи места:", reply_markup=markup)
        await AddParkingSpot.waiting_for_date_selection.set()
    except:
        await message.answer("❌ Введите корректную сумму (только цифры):")

@dp.callback_query_handler(lambda c: c.data.startswith('add_date_'), state=AddParkingSpot.waiting_for_date_selection)
async def process_date_selection(callback_query: types.CallbackQuery, state: FSMContext):
    date_str = callback_query.data.replace('add_date_', '')
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    await state.update_data(selected_date=selected_date)
    await bot.send_message(
        callback_query.from_user.id,
        f"🕐 Введите время доступности для {format_date(selected_date)} в формате ЧЧ.ММ-ЧЧ.ММ\n"
        f"Например: 09.00-18.00"
    )
    await AddParkingSpot.waiting_for_time_range.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_time_range)
async def process_time_range(message: types.Message, state: FSMContext):
    try:
        time_range = message.text
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
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
            db.add_availability(
                spot_id=spot_id,
                date=user_data['selected_date'],
                start_time=start_time,
                end_time=end_time
            )
            
            # Уведомление админу
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"🅿️ Новое парковочное место добавлено!\n"
                f"Место: {user_data['spot_number']}\n"
                f"Владелец: @{message.from_user.username}\n"
                f"Цена/час: {user_data['price_hour']} руб.\n"
                f"Цена/сутки: {user_data['price_day']} руб.\n"
                f"Дата: {format_date(user_data['selected_date'])}\n"
                f"Время: {time_range}"
            )
            
            await message.answer(
                f"✅ Парковочное место успешно добавлено!\n\n"
                f"📌 Номер места: {user_data['spot_number']}\n"
                f"📅 Дата: {format_date(user_data['selected_date'])}\n"
                f"🕐 Время: {time_range}\n"
                f"💰 Цена/час: {user_data['price_hour']} руб.\n"
                f"💰 Цена/сутки: {user_data['price_day']} руб."
            )
        else:
            await message.answer("❌ Ошибка при добавлении места.")
        
        await state.finish()
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ")

# Бронирование места
@dp.message_handler(lambda message: message.text == "📅 Забронировать место")
async def cmd_book_spot(message: types.Message):
    # Показываем ближайшие 4 дня
    days = get_next_days()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for day in days:
        markup.insert(types.InlineKeyboardButton(
            format_date(day),
            callback_data=f"book_date_{day}"
        ))
    
    await message.answer("📅 Выберите дату бронирования:", reply_markup=markup)
    await BookParkingSpot.waiting_for_date_selection.set()

@dp.callback_query_handler(lambda c: c.data.startswith('book_date_'), state=BookParkingSpot.waiting_for_date_selection)
async def process_book_date(callback_query: types.CallbackQuery, state: FSMContext):
    date_str = callback_query.data.replace('book_date_', '')
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    await state.update_data(selected_date=selected_date)
    
    # Получаем доступные места на выбранную дату
    spots = db.get_available_spots(selected_date)
    
    if not spots:
        await bot.send_message(
            callback_query.from_user.id,
            f"❌ На {format_date(selected_date)} нет доступных мест."
        )
        await state.finish()
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for spot in spots:
        markup.add(types.InlineKeyboardButton(
            f"📍 Место {spot['spot_number']} - {spot['price_per_hour']} руб./час",
            callback_data=f"select_spot_{spot['id']}"
        ))
    
    await bot.send_message(
        callback_query.from_user.id,
        f"🅿️ Доступные места на {format_date(selected_date)}:",
        reply_markup=markup
    )
    await BookParkingSpot.waiting_for_spot_selection.set()

@dp.callback_query_handler(lambda c: c.data.startswith('select_spot_'), state=BookParkingSpot.waiting_for_spot_selection)
async def process_spot_selection(callback_query: types.CallbackQuery, state: FSMContext):
    spot_id = int(callback_query.data.replace('select_spot_', ''))
    await state.update_data(selected_spot_id=spot_id)
    
    await bot.send_message(
        callback_query.from_user.id,
        "🕐 Введите время бронирования в формате ЧЧ.ММ-ЧЧ.ММ\n"
        "Например: 14.00-16.00"
    )
    await BookParkingSpot.waiting_for_time_selection.set()

@dp.message_handler(state=BookParkingSpot.waiting_for_time_selection)
async def process_book_time(message: types.Message, state: FSMContext):
    try:
        time_range = message.text
        start_str, end_str = time_range.split('-')
        start_time = datetime.strptime(start_str.strip(), "%H.%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H.%M").time()
        
        user_data = await state.get_data()
        
        # Получаем информацию о месте для расчета цены
        spots = db.get_available_spots(user_data['selected_date'])
        selected_spot = next((s for s in spots if s['id'] == user_data['selected_spot_id']), None)
        
        if not selected_spot:
            await message.answer("❌ Место больше не доступно.")
            await state.finish()
            return
        
        # Расчет стоимости (упрощенный - по часам)
        hours = (datetime.combine(datetime.today(), end_time) - 
                 datetime.combine(datetime.today(), start_time)).seconds / 3600
        total_price = hours * selected_spot['price_per_hour']
        
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
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_booking")
        )
        
        await message.answer(
            f"📋 Подтвердите бронирование:\n\n"
            f"📍 Место: {selected_spot['spot_number']}\n"
            f"📅 Дата: {format_date(user_data['selected_date'])}\n"
            f"🕐 Время: {time_range}\n"
            f"⏱️ Часов: {hours:.1f}\n"
            f"💰 Стоимость: {total_price:.2f} руб.\n\n"
            f"Подтвердить бронирование?",
            reply_markup=markup
        )
        await BookParkingSpot.waiting_for_confirmation.set()
    except:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ")

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
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📅 НОВАЯ БРОНЬ!\n\n"
            f"👤 Пользователь: @{callback_query.from_user.username}\n"
            f"📍 Место: {user_data['spot_number']}\n"
            f"📅 Дата: {format_date(user_data['selected_date'])}\n"
            f"🕐 Время: {user_data['time_range']}\n"
            f"💰 Сумма: {user_data['total_price']:.2f} руб."
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Бронирование подтверждено!\n\n"
            f"📌 Номер брони: #{booking_id}\n"
            f"📍 Место: {user_data['spot_number']}\n"
            f"📅 Дата: {format_date(user_data['selected_date'])}\n"
            f"🕐 Время: {user_data['time_range']}\n"
            f"💰 Сумма к оплате: {user_data['total_price']:.2f} руб."
        )
    else:
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Не удалось создать бронирование. Место может быть уже занято."
        )
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'cancel_booking', state=BookParkingSpot.waiting_for_confirmation)
async def cancel_booking(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.send_message(callback_query.from_user.id, "❌ Бронирование отменено.")
    await state.finish()

# Мои места
@dp.message_handler(lambda message: message.text == "📊 Мои места")
async def cmd_my_spots(message: types.Message):
    spots = db.get_user_spots(message.from_user.id)
    
    if not spots:
        await message.answer("У вас пока нет добавленных парковочных мест.")
        return
    
    response = "📊 Ваши парковочные места:\n\n"
    for spot in spots:
        response += (
            f"📍 Место: {spot['spot_number']}\n"
            f"💰 Цена/час: {spot['price_per_hour']} руб.\n"
            f"💰 Цена/сутки: {spot['price_per_day']} руб.\n"
            f"📅 Добавлено: {spot['created_at'][:10]}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

# Мои бронирования
@dp.message_handler(lambda message: message.text == "📋 Мои бронирования")
async def cmd_my_bookings(message: types.Message):
    bookings = db.get_user_bookings(message.from_user.id)
    
    if not bookings:
        await message.answer("У вас пока нет бронирований.")
        return
    
    response = "📋 Ваши бронирования:\n\n"
    for booking in bookings:
        response += (
            f"📌 Бронь #{booking['id']}\n"
            f"📍 Место: {booking['spot_number']}\n"
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
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("👥 Все пользователи", "🅿️ Все места")
        markup.add("📅 Все бронирования", "📊 Статистика")
        markup.add("🔙 Главное меню")
        
        await message.answer("✅ Доступ к админ-панели предоставлен!", reply_markup=markup)
    else:
        await message.answer("❌ Неверный пароль!")
        await state.finish()

# Админ функции
@dp.message_handler(lambda message: message.text == "👥 Все пользователи")
async def admin_all_users(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    # Простая заглушка - можно расширить
    await message.answer("Функция просмотра всех пользователей будет реализована позже.")

@dp.message_handler(lambda message: message.text == "🅿️ Все места")
async def admin_all_spots(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    await message.answer("Функция просмотра всех мест будет реализована позже.")

@dp.message_handler(lambda message: message.text == "📅 Все бронирования")
async def admin_all_bookings(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    await message.answer("Функция просмотра всех бронирований будет реализована позже.")

@dp.message_handler(lambda message: message.text == "📊 Статистика")
async def admin_statistics(message: types.Message):
    if not db.is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    await message.answer("Функция статистики будет реализована позже.")

# Главное меню
@dp.message_handler(lambda message: message.text == "🔙 Главное меню")
async def cmd_main_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🚗 Добавить парковочное место", "📅 Забронировать место")
    markup.add("📊 Мои места", "📋 Мои бронирования")
    await message.answer("🏠 Главное меню", reply_markup=markup)

# Обработчик ошибок
@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Update {update} caused error {exception}")
    return True

# Запуск бота
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
