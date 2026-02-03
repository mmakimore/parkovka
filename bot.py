import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from datetime import datetime, timedelta
from config import BOT_TOKEN, ADMIN_CHAT_ID, ADMIN_PASSWORD
from database import Database

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Initialize database
db = Database()

# States
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

# Helper functions
def get_next_days():
    """Get next 4 days including today"""
    today = datetime.now().date()
    return [today + timedelta(days=i) for i in range(4)]

def format_date(date):
    """Format date to string"""
    return date.strftime("%d.%m.%Y")

# Start command
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Check if user exists
    if not db.is_admin(user_id):  # Simple check if user exists
        await message.answer("👋 Добро пожаловать! Для начала зарегистрируйтесь.")
        await message.answer("📝 Введите ваше имя:")
        await UserRegistration.waiting_for_name.set()
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🚗 Добавить парковочное место")
        markup.add("📅 Забронировать место")
        markup.add("📊 Мои места", "📋 Мои бронирования")
        await message.answer("🎉 С возвращением! Что вы хотите сделать?", reply_markup=markup)

# Registration process
@dp.message_handler(state=UserRegistration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📱 Теперь введите ваш номер телефона:")
    await UserRegistration.waiting_for_phone.set()

@dp.message_handler(state=UserRegistration.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text
    user_data = await state.get_data()
    
    # Save user to database
    success = db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=user_data['name'],
        phone=phone
    )
    
    if success:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🚗 Добавить парковочное место")
        markup.add("📅 Забронировать место")
        markup.add("📊 Мои места", "📋 Мои бронирования")
        
        await message.answer("✅ Регистрация завершена!", reply_markup=markup)
        
        # Notify admin
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"👤 Новый пользователь зарегистрировался:\n"
            f"Имя: {user_data['name']}\n"
            f"Телефон: {phone}\n"
            f"Username: @{message.from_user.username}"
        )
    else:
        await message.answer("❌ Ошибка при регистрации. Попробуйте еще раз.")
    
    await state.finish()

# Add parking spot
@dp.message_handler(lambda message: message.text == "🚗 Добавить парковочное место")
async def cmd_add_spot(message: types.Message):
    await message.answer("🚗 Введите номер парковочного места:")
    await AddParkingSpot.waiting_for_spot_number.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_spot_number)
async def process_spot_number(message: types.Message, state: FSMContext):
    await state.update_data(spot_number=message.text)
    await message.answer("💰 Введите цену за час (например: 100):")
    await AddParkingSpot.waiting_for_price_hour.set()

@dp.message_handler(state=AddParkingSpot.waiting_for_price_hour)
async def process_price_hour(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price_hour=price)
        await message.answer("💰 Введите цену за сутки (например: 800):")
        await AddParkingSpot.waiting_for_price_day.set()
    except:
        await message.answer("❌ Введите корректную сумму (только цифры):")

@dp.message_handler(state=AddParkingSpot.waiting_for_price_day)
async def process_price_day(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price_day=price)
        
        # Show date selection
        days = get_next_days()
        markup = types.InlineKeyboardMarkup()
        for day in days:
            markup.add(types.InlineKeyboardButton(
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
        
        # Add parking spot to database
        spot_id = db.add_parking_spot(
            owner_id=message.from_user.id,
            spot_number=user_data['spot_number'],
            price_per_hour=user_data['price_hour'],
            price_per_day=user_data['price_day']
        )
        
        if spot_id:
            # Add availability
            db.add_availability(
                spot_id=spot_id,
                date=user_data['selected_date'],
                start_time=start_time,
                end_time=end_time
            )
            
            # Notify admin
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
                f"✅ Парковочное место успешно добавлено!\n"
                f"Номер: {user_data['spot_number']}\n"
                f"Дата: {format_date(user_data['selected_date'])}\n"
                f"Время: {time_range}"
            )
        else:
            await message.answer("❌ Ошибка при добавлении места.")
        
        await state.finish()
    except:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ")

# Book parking spot
@dp.message_handler(lambda message: message.text == "📅 Забронировать место")
async def cmd_book_spot(message: types.Message):
    # Show date selection
    days = get_next_days()
    markup = types.InlineKeyboardMarkup()
    for day in days:
        markup.add(types.InlineKeyboardButton(
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
    
    # Get available spots for selected date
    spots = db.get_available_spots(selected_date)
    
    if not spots:
        await bot.send_message(
            callback_query.from_user.id,
            "❌ На эту дату нет доступных мест."
        )
        await state.finish()
        return
    
    markup = types.InlineKeyboardMarkup()
    for spot in spots:
        markup.add(types.InlineKeyboardButton(
            f"Место {spot['spot_number']} - {spot['price_per_hour']} руб./час",
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
        
        # Calculate price (simplified - assuming hourly rate)
        # You might want to implement more complex pricing logic
        hours = (datetime.combine(datetime.today(), end_time) - 
                 datetime.combine(datetime.today(), start_time)).seconds / 3600
        
        # Get spot price
        spots = db.get_available_spots(user_data['selected_date'])
        spot_price = next((s['price_per_hour'] for s in spots if s['id'] == user_data['selected_spot_id']), 0)
        
        total_price = hours * spot_price
        
        await state.update_data(
            start_time=start_time,
            end_time=end_time,
            total_price=total_price,
            time_range=time_range
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_booking"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_booking")
        )
        
        await message.answer(
            f"📋 Подтвердите бронирование:\n"
            f"Дата: {format_date(user_data['selected_date'])}\n"
            f"Время: {time_range}\n"
            f"Стоимость: {total_price:.2f} руб.\n\n"
            f"Подтвердить бронирование?",
            reply_markup=markup
        )
        await BookParkingSpot.waiting_for_confirmation.set()
    except:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ.ММ-ЧЧ.ММ")

@dp.callback_query_handler(lambda c: c.data == 'confirm_booking', state=BookParkingSpot.waiting_for_confirmation)
async def confirm_booking(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    
    # Create booking
    booking_id = db.create_booking(
        user_id=callback_query.from_user.id,
        spot_id=user_data['selected_spot_id'],
        date=user_data['selected_date'],
        start_time=user_data['start_time'],
        end_time=user_data['end_time'],
        total_price=user_data['total_price']
    )
    
    if booking_id:
        # Notify admin
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📅 Новая бронь!\n"
            f"Пользователь: @{callback_query.from_user.username}\n"
            f"Дата: {format_date(user_data['selected_date'])}\n"
            f"Время: {user_data['time_range']}\n"
            f"Сумма: {user_data['total_price']:.2f} руб."
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Бронирование подтверждено!\n"
            f"Номер брони: #{booking_id}\n"
            f"Сумма к оплате: {user_data['total_price']:.2f} руб."
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

# My spots
@dp.message_handler(lambda message: message.text == "📊 Мои места")
async def cmd_my_spots(message: types.Message):
    spots = db.get_user_spots(message.from_user.id)
    
    if not spots:
        await message.answer("У вас пока нет добавленных мест.")
        return
    
    response = "📊 Ваши парковочные места:\n\n"
    for spot in spots:
        response += (
            f"📍 Место {spot['spot_number']}\n"
            f"Цена/час: {spot['price_per_hour']} руб.\n"
            f"Цена/сутки: {spot['price_per_day']} руб.\n"
            f"Броней: {spot['total_bookings']}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

# My bookings
@dp.message_handler(lambda message: message.text == "📋 Мои бронирования")
async def cmd_my_bookings(message: types.Message):
    bookings = db.get_user_bookings(message.from_user.id)
    
    if not bookings:
        await message.answer("У вас пока нет бронирований.")
        return
    
    response = "📋 Ваши бронирования:\n\n"
    for booking in bookings:
        response += (
            f"Бронь #{booking['id']}\n"
            f"Место: {booking['spot_number']}\n"
            f"Дата: {booking['date'].strftime('%d.%m.%Y')}\n"
            f"Время: {booking['start_time']} - {booking['end_time']}\n"
            f"Сумма: {booking['total_price']} руб.\n"
            f"Статус: {booking['status']}\n"
            f"────────────────────\n"
        )
    
    await message.answer(response)

# Admin panel
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    await message.answer("🔐 Введите пароль для доступа к админ-панели:")
    await AdminPanel.waiting_for_password.set()

@dp.message_handler(state=AdminPanel.waiting_for_password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        db.set_admin(message.from_user.id)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("👥 Все пользователи")
        markup.add("🅿️ Все места")
        markup.add("📊 Статистика")
        markup.add("🔙 Главное меню")
        
        await message.answer("✅ Доступ к админ-панели предоставлен!", reply_markup=markup)
    else:
        await message.answer("❌ Неверный пароль!")
    
    await state.finish()

# Main menu
@dp.message_handler(lambda message: message.text == "🔙 Главное меню")
async def cmd_main_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚗 Добавить парковочное место")
    markup.add("📅 Забронировать место")
    markup.add("📊 Мои места", "📋 Мои бронирования")
    await message.answer("🏠 Главное меню", reply_markup=markup)

# Error handler
@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Update {update} caused error {exception}")
    return True

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)