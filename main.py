"""
Обработчики для команды /start, регистрации и основного меню
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import db
from keyboards import main as kb_main
from keyboards import inline as kb_inline
from handlers.utils import (
    validate_phone, format_phone, validate_email,
    log_user_action, notify_user, notify_admins_about_event
)

logger = logging.getLogger(__name__)
router = Router()

# ==================== СОСТОЯНИЯ РЕГИСТРАЦИИ ====================

class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    waiting_for_phone = State()
    waiting_for_email = State()
    waiting_for_car_info = State()

# ==================== СОСТОЯНИЯ ДЛЯ АДМИН АВТОРИЗАЦИИ ====================

class AdminAuthStates(StatesGroup):
    """Состояния для авторизации в админке"""
    waiting_for_password = State()

# ==================== КОМАНДА /START ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    try:
        # Очищаем состояние
        await state.clear()
        
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        
        logger.info(f"Пользователь {user_id} ({full_name}) начал работу с ботом")
        
        # Проверяем, зарегистрирован ли пользователь
        user = db.get_user(telegram_id=user_id)
        
        if user:
            # Пользователь уже зарегистрирован
            await show_main_menu(message)
            return
        
        # Пользователь не зарегистрирован - начинаем регистрацию
        await start_registration(message, state, username, full_name)
        
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=kb_main.get_main_menu()
        )

async def start_registration(message: Message, state: FSMContext, username: str, full_name: str):
    """Начало процесса регистрации"""
    # Сохраняем базовую информацию
    await state.update_data(
        telegram_id=message.from_user.id,
        username=username,
        full_name=full_name
    )
    
    # Отправляем приветственное сообщение
    welcome_text = (
        f"👋 <b>Добро пожаловать, {full_name}!</b>\n\n"
        f"Я - бот для бронирования парковочных мест.\n"
        f"Перед началом работы необходимо пройти регистрацию.\n\n"
        f"<b>Для регистрации потребуется:</b>\n"
        f"• Номер телефона\n"
        f"• Email (необязательно)\n"
        f"• Данные автомобиля (необязательно)\n\n"
        f"<b>Отправьте свой номер телефона:</b>\n"
        f"📱 Формат: +79991234567 или 89991234567"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=kb_main.get_contact_keyboard()
    )
    
    # Устанавливаем состояние ожидания телефона
    await state.set_state(RegistrationStates.waiting_for_phone)

# ==================== ПОЛУЧЕНИЕ ТЕЛЕФОНА ====================

@router.message(RegistrationStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка введенного телефона"""
    try:
        phone = None
        
        # Проверяем, отправил ли пользователь контакт
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text
        
        # Валидируем телефон
        if not validate_phone(phone):
            await message.answer(
                "❌ <b>Неверный формат телефона!</b>\n\n"
                "Пожалуйста, отправьте номер в формате:\n"
                "• +79991234567\n"
                "• 89991234567\n\n"
                "Или нажмите кнопку '📞 Позвонить' для отправки контакта.",
                reply_markup=kb_main.get_contact_keyboard()
            )
            return
        
        # Форматируем телефон
        formatted_phone = format_phone(phone)
        
        # Проверяем, не занят ли телефон
        existing_user = db.get_user_by_phone(formatted_phone)
        if existing_user:
            await message.answer(
                "❌ <b>Этот телефон уже зарегистрирован!</b>\n\n"
                "Если это ваш телефон, обратитесь в поддержку.\n"
                "Или используйте другой номер телефона.",
                reply_markup=kb_main.get_contact_keyboard()
            )
            return
        
        # Сохраняем телефон
        await state.update_data(phone=formatted_phone)
        
        # Спрашиваем email
        await message.answer(
            "📧 <b>Укажите ваш Email (необязательно):</b>\n\n"
            "Email используется для:\n"
            "• Восстановления доступа\n"
            "• Важных уведомлений\n"
            "• Чеков об оплате\n\n"
            "Если не хотите указывать Email, отправьте <code>пропустить</code>",
            reply_markup=kb_main.get_back_keyboard()
        )
        
        await state.set_state(RegistrationStates.waiting_for_email)
        
    except Exception as e:
        logger.error(f"Ошибка обработки телефона: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_contact_keyboard()
        )

# ==================== ПОЛУЧЕНИЕ EMAIL ====================

@router.message(RegistrationStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    """Обработка введенного email"""
    try:
        email = message.text.strip()
        
        # Проверяем, не хочет ли пользователь пропустить
        if email.lower() in ['пропустить', 'skip', 'нет', 'no']:
            email = None
        else:
            # Валидируем email
            if not validate_email(email):
                await message.answer(
                    "❌ <b>Неверный формат Email!</b>\n\n"
                    "Пожалуйста, укажите Email в формате:\n"
                    "• example@mail.ru\n"
                    "• example@gmail.com\n\n"
                    "Или отправьте <code>пропустить</code>, чтобы не указывать Email",
                    reply_markup=kb_main.get_back_keyboard()
                )
                return
        
        # Сохраняем email
        await state.update_data(email=email)
        
        # Спрашиваем информацию об автомобиле
        await message.answer(
            "🚗 <b>Укажите данные вашего автомобиля (необязательно):</b>\n\n"
            "Формат:\n"
            "<code>А123БВ77 Бренд Модель</code>\n\n"
            "Примеры:\n"
            "• А123БВ77 Toyota Camry\n"
            "• А123БВ77 (только номер)\n"
            "• пропустить\n\n"
            "Эти данные помогут владельцам мест идентифицировать ваш автомобиль.",
            reply_markup=kb_main.get_back_keyboard()
        )
        
        await state.set_state(RegistrationStates.waiting_for_car_info)
        
    except Exception as e:
        logger.error(f"Ошибка обработки email: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_back_keyboard()
        )

# ==================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ ОБ АВТОМОБИЛЕ ====================

@router.message(RegistrationStates.waiting_for_car_info)
async def process_car_info(message: Message, state: FSMContext):
    """Обработка информации об автомобиле"""
    try:
        car_text = message.text.strip()
        
        # Проверяем, не хочет ли пользователь пропустить
        if car_text.lower() in ['пропустить', 'skip', 'нет', 'no']:
            car_plate = None
            car_brand = None
            car_model = None
        else:
            # Парсим информацию об автомобиле
            parts = car_text.split()
            
            if len(parts) == 0:
                car_plate = None
                car_brand = None
                car_model = None
            elif len(parts) == 1:
                # Только номер
                car_plate = parts[0].upper()
                car_brand = None
                car_model = None
            elif len(parts) == 2:
                # Номер и бренд
                car_plate = parts[0].upper()
                car_brand = parts[1]
                car_model = None
            else:
                # Номер, бренд и модель
                car_plate = parts[0].upper()
                car_brand = parts[1]
                car_model = ' '.join(parts[2:])
        
        # Получаем все данные
        user_data = await state.get_data()
        
        # Регистрируем пользователя
        user_id = db.register_user(
            telegram_id=user_data['telegram_id'],
            full_name=user_data['full_name'],
            phone=user_data['phone'],
            username=user_data.get('username'),
            email=user_data.get('email')
        )
        
        if user_id:
            # Обновляем информацию об автомобиле, если есть
            if car_plate:
                db.update_user(user_id, car_plate=car_plate)
            if car_brand:
                db.update_user(user_id, car_brand=car_brand)
            if car_model:
                db.update_user(user_id, car_model=car_model)
            
            # Успешная регистрация
            await complete_registration(message, state, user_id, user_data, car_plate, car_brand, car_model)
        else:
            await message.answer(
                "❌ <b>Ошибка регистрации!</b>\n\n"
                "Не удалось зарегистрировать пользователя.\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
            )
            
    except Exception as e:
        logger.error(f"Ошибка обработки информации об автомобиле: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_back_keyboard()
        )

async def complete_registration(message: Message, state: FSMContext, user_id: int, user_data: dict, car_plate=None, car_brand=None, car_model=None):
    """Завершение регистрации"""
    try:
        # Получаем полную информацию о пользователе
        user = db.get_user(user_id=user_id)
        
        # Формируем сообщение о успешной регистрации
        success_text = (
            f"✅ <b>Регистрация завершена!</b>\n\n"
            f"<b>Ваши данные:</b>\n"
            f"👤 Имя: {user['full_name']}\n"
            f"📱 Телефон: {user['phone']}\n"
        )
        
        if user['email']:
            success_text += f"📧 Email: {user['email']}\n"
        
        if car_plate:
            car_info = car_plate
            if car_brand:
                car_info = f"{car_brand}"
                if car_model:
                    car_info += f" {car_model}"
                car_info += f" ({car_plate})"
            success_text += f"🚗 Автомобиль: {car_info}\n"
        
        success_text += (
            f"\n🎉 <b>Добро пожаловать в сервис бронирования парковок!</b>\n\n"
            f"<b>Что вы можете делать:</b>\n"
            f"• 🚗 Найти и забронировать парковочное место\n"
            f"• 🏠 Сдавать в аренду свои места\n"
            f"• 📊 Управлять бронированиями\n"
            f"• ⭐ Оставлять отзывы\n"
            f"• 💰 Получать и тратить деньги\n\n"
            f"<i>Используйте меню ниже для навигации</i>"
        )
        
        # Отправляем приветственное сообщение
        await message.answer(
            success_text,
            reply_markup=kb_main.get_main_menu(telegram_id=user['telegram_id'], db_instance=db)
        )
        
        # Логируем регистрацию
        log_user_action(user_id, "registration_complete", f"Пользователь зарегистрирован: {user['full_name']}")
        
        # Уведомляем администраторов
        await notify_admins_about_event(
            "Новая регистрация",
            f"Зарегистрирован новый пользователь:\n"
            f"👤 {user['full_name']}\n"
            f"📱 {user['phone']}\n"
            f"🆔 {user['telegram_id']}",
            {"user_id": user_id}
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка завершения регистрации: {e}")
        await message.answer(
            "✅ Регистрация завершена, но произошла ошибка при отправке приветствия.",
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
        )
        await state.clear()

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.message(F.text == "🔙 Главное меню")
@router.message(F.text == "🏠 Главное меню")
@router.message(F.text == "📋 Главное меню")
async def main_menu(message: Message, state: FSMContext):
    """Обработчик кнопки Главное меню"""
    await show_main_menu(message)

async def show_main_menu(message: Message = None):
    """Показать главное меню"""
    try:
        if not message:
            return
        
        user_id = message.from_user.id
        
        # Получаем информацию о пользователе
        user = db.get_user(telegram_id=user_id)
        
        if not user:
            # Пользователь не найден, предлагаем зарегистрироваться
            await message.answer(
                "❌ <b>Вы не зарегистрированы!</b>\n\n"
                "Для использования бота необходимо пройти регистрацию.\n"
                "Нажмите /start чтобы начать.",
                reply_markup=kb_main.get_main_menu()
            )
            return
        
        # Проверяем, не заблокирован ли пользователь
        if user.get('is_blocked'):
            await message.answer(
                "🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
                "Обратитесь в поддержку для выяснения причин.",
                reply_markup=kb_main.get_main_menu()
            )
            return
        
        # Обновляем время последней активности
        db.update_user(user['id'], last_active=datetime.now())
        
        # Формируем приветственное сообщение
        welcome_text = (
            f"👋 <b>Добро пожаловать, {user['full_name']}!</b>\n\n"
            f"Я - ваш помощник в поиске и бронировании парковочных мест.\n\n"
        )
        
        # Добавляем уведомления, если есть
        unread_count = db.count_unread_notifications(user['id'])
        if unread_count > 0:
            welcome_text += f"📢 У вас <b>{unread_count}</b> непрочитанных уведомлений\n"
        
        # Добавляем информацию о бронированиях
        active_bookings = db.count_bookings(user_id=user['id'], status='active')
        if active_bookings > 0:
            welcome_text += f"📋 Активных бронирований: <b>{active_bookings}</b>\n"
        
        # Добавляем баланс
        if user['balance'] > 0:
            welcome_text += f"💰 Баланс: <b>{user['balance']} ₽</b>\n"
        
        # Проверяем админ-сессию
        admin_session = db.get_admin_session(user['id'])
        if admin_session and datetime.fromisoformat(admin_session['expires_at']) > datetime.now():
            expires_time = datetime.fromisoformat(admin_session['expires_at'])
            welcome_text += f"👑 Админ-сессия активна до: <b>{expires_time.strftime('%d.%m.%Y %H:%M')}</b>\n"
        
        welcome_text += f"\n👇 <b>Выберите действие в меню ниже:</b>"
        
        # Отправляем сообщение с динамической клавиатурой
        await message.answer(
            welcome_text,
            reply_markup=kb_main.get_main_menu(telegram_id=user_id, db_instance=db)
        )
        
    except Exception as e:
        logger.error(f"Ошибка показа главного меню: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=kb_main.get_main_menu()
        )

# ==================== КОМАНДА /ADMIN ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, command: CommandObject):
    """Вход в админ-панель по паролю"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, не является ли пользователь уже админом
        user = db.get_user(telegram_id=user_id)
        if user and user.get('is_admin'):
            await message.answer(
                "👑 <b>Вы уже администратор!</b>\n\n"
                "Используйте кнопку '⚙️ Админ-панель' в главном меню.",
                reply_markup=kb_main.get_main_menu(telegram_id=user_id, db_instance=db)
            )
            return
        
        # Проверяем активную сессию
        if user:
            session = db.get_admin_session(user['id'])
            if session and datetime.fromisoformat(session['expires_at']) > datetime.now():
                await message.answer(
                    "✅ <b>У вас уже есть активная админ-сессия!</b>\n\n"
                    "Используйте кнопку '⚙️ Админ-панель' в главном меню.\n\n"
                    f"Сессия действует до: {datetime.fromisoformat(session['expires_at']).strftime('%d.%m.%Y %H:%M')}",
                    reply_markup=kb_main.get_main_menu(telegram_id=user_id, db_instance=db)
                )
                return
        
        # Если пользователь не зарегистрирован
        if not user:
            await message.answer(
                "❌ <b>Для входа в админ-панель нужно быть зарегистрированным пользователем!</b>\n\n"
                "Нажмите /start чтобы зарегистрироваться."
            )
            return
        
        # Проверяем, есть ли пароль в аргументах команды
        if command.args and command.args.strip():
            password = command.args.strip()
            await process_admin_password_with_args(message, state, user, password)
            return
        
        # Если пароля нет в аргументах, запрашиваем его
        await message.answer(
            "🔐 <b>Вход в админ-панель</b>\n\n"
            "Введите пароль для доступа к админ-панели:\n\n"
            "<i>Пароль по умолчанию: qwerty123</i>\n\n"
            "Отправьте /cancel для отмена",
            reply_markup=kb_main.get_cancel_keyboard()
        )
        
        # Сохраняем ID пользователя для проверки пароля
        await state.update_data(admin_auth_user_id=user['id'])
        await state.set_state(AdminAuthStates.waiting_for_password)
        
    except Exception as e:
        logger.error(f"Ошибка команды /admin: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=kb_main.get_main_menu()
        )

async def process_admin_password_with_args(message: Message, state: FSMContext, user: dict, password: str):
    """Обработка пароля из аргументов команды /admin"""
    try:
        # Проверяем пароль
        if db.check_admin_password(password):
            # Создаем админ-сессию на 24 часа
            session_token = db.create_admin_session(user['id'], expires_hours=24)
            
            if session_token:
                await message.answer(
                    f"✅ <b>Доступ к админ-панели предоставлен!</b>\n\n"
                    f"Теперь у вас есть доступ к админ-панели на 24 часа.\n\n"
                    f"Используйте кнопку '⚙️ Админ-панель' в главном меню для управления системой.",
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
                )
                
                # Логируем вход
                log_user_action(user['id'], "admin_login", f"Вход в админ-панель по паролю (аргументы)")
                
                # Уведомляем постоянных админов
                admins = db.get_all_users(is_admin=True)
                for admin in admins:
                    if admin['telegram_id'] != message.from_user.id:
                        await notify_user(
                            admin['telegram_id'],
                            "📢 Вход в админ-панель",
                            f"Пользователь {user['full_name']} вошел в админ-панель по паролю.\n"
                            f"ID: {user['telegram_id']}\n"
                            f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
                            "admin_login_notification"
                        )
            else:
                await message.answer(
                    "❌ <b>Ошибка создания сессии!</b>\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    reply_markup=kb_main.get_main_menu()
                )
        else:
            # Неверный пароль, запрашиваем снова
            await message.answer(
                "❌ <b>Неверный пароль!</b>\n\n"
                "Попробуйте снова или обратитесь к администратору.\n\n"
                "Введите пароль:",
                reply_markup=kb_main.get_cancel_keyboard()
            )
            
            # Сохраняем ID пользователя и переходим в состояние ожидания пароля
            await state.update_data(admin_auth_user_id=user['id'])
            await state.set_state(AdminAuthStates.waiting_for_password)
            
    except Exception as e:
        logger.error(f"Ошибка обработки пароля из аргументов: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=kb_main.get_main_menu()
        )

# ==================== ОБРАБОТКА ПАРОЛЯ (отдельное сообщение) ====================

@router.message(AdminAuthStates.waiting_for_password)
async def process_admin_password(message: Message, state: FSMContext):
    """Обработка пароля для входа в админку (отдельное сообщение)"""
    try:
        password = message.text.strip()
        data = await state.get_data()
        user_id = data.get('admin_auth_user_id')
        
        if not user_id:
            await message.answer(
                "❌ Ошибка авторизации. Попробуйте снова.",
                reply_markup=kb_main.get_main_menu()
            )
            await state.clear()
            return
        
        user = db.get_user(user_id=user_id)
        if not user:
            await message.answer(
                "❌ Пользователь не найден.",
                reply_markup=kb_main.get_main_menu()
            )
            await state.clear()
            return
        
        # Проверяем пароль
        if db.check_admin_password(password):
            # Создаем админ-сессию на 24 часа
            session_token = db.create_admin_session(user_id, expires_hours=24)
            
            if session_token:
                await message.answer(
                    "✅ <b>Доступ к админ-панели предоставлен!</b>\n\n"
                    "Теперь у вас есть доступ к админ-панели на 24 часа.\n\n"
                    "Используйте кнопку '⚙️ Админ-панель' в главном меню для управления системой.",
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
                )
                
                # Логируем вход
                log_user_action(user_id, "admin_login", f"Вход в админ-панель по паролю")
                
                # Уведомляем постоянных админов
                admins = db.get_all_users(is_admin=True)
                for admin in admins:
                    if admin['telegram_id'] != message.from_user.id:
                        await notify_user(
                            admin['telegram_id'],
                            "📢 Вход в админ-панель",
                            f"Пользователь {user['full_name']} вошел в админ-панель по паролю.\n"
                            f"ID: {user['telegram_id']}\n"
                            f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
                            "admin_login_notification"
                        )
            else:
                await message.answer(
                    "❌ <b>Ошибка создания сессии!</b>\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    reply_markup=kb_main.get_main_menu()
                )
        else:
            await message.answer(
                "❌ <b>Неверный пароль!</b>\n\n"
                "Попробуйте снова или обратитесь к администратору.\n\n"
                "Введите пароль:",
                reply_markup=kb_main.get_cancel_keyboard()
            )
            return
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки пароля админа: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=kb_main.get_main_menu()
        )
        await state.clear()

# ==================== КОМАНДА /ADMIN_LOGOUT ====================

@router.message(Command("admin_logout"))
async def cmd_admin_logout(message: Message):
    """Выход из админ-панели (завершение сессии)"""
    try:
        user = db.get_user(telegram_id=message.from_user.id)
        if not user:
            await message.answer("❌ Вы не зарегистрированы.")
            return
        
        # Проверяем, есть ли активная сессия
        session = db.get_admin_session(user['id'])
        if not session:
            await message.answer(
                "ℹ️ <b>У вас нет активной админ-сессии</b>\n\n"
                "Используйте /admin для входа в админ-панель.",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
            )
            return
        
        # Удаляем сессию
        success = db.delete_admin_session(user['id'])
        
        if success:
            await message.answer(
                "✅ <b>Админ-сессия завершена!</b>\n\n"
                "Доступ к админ-панели отозван.\n\n"
                "Для входа снова используйте /admin",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
            )
            
            # Логируем выход
            log_user_action(user['id'], "admin_logout", "Выход из админ-панели")
        else:
            await message.answer(
                "❌ <b>Ошибка завершения сессии!</b>\n\n"
                "Попробуйте позже или обратитесь к администратору.",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
            )
        
    except Exception as e:
        logger.error(f"Ошибка команды /admin_logout: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=kb_main.get_main_menu()
        )

# ==================== КОМАНДА /HELP ====================

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "🆘 <b>Помощь по использованию бота</b>\n\n"
        
        "<b>Основные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/profile - Управление профилем\n"
        "/support - Связаться с поддержкой\n"
        "/admin - Вход в админ-панель (требует пароль)\n"
        "/admin_logout - Выход из админ-панели\n\n"
        
        "<b>Основные функции:</b>\n"
        "• 🚗 <b>Найти место</b> - поиск и бронирование парковок\n"
        "• 🏠 <b>Мои места</b> - управление вашими парковочными местами\n"
        "• 📊 <b>Мои бронирования</b> - просмотр и управление бронями\n"
        "• 👤 <b>Профиль</b> - настройки аккаунта и баланс\n"
        "• 📢 <b>Уведомления</b> - системные уведомления\n"
        "• ⚙️ <b>Админ-панель</b> - управление системой (если есть доступ)\n\n"
        
        "<b>Для владельцев парковок:</b>\n"
        "• Добавляйте свои места в систему\n"
        "• Устанавливайте цену и расписание\n"
        "• Получайте уведомления о новых бронированиях\n"
        "• Управляйте доступностью мест\n\n"
        
        "<b>Для водителей:</b>\n"
        "• Ищите свободные места поблизости\n"
        "• Бронируйте на нужное время\n"
        "• Оплачивайте удобным способом\n"
        "• Оставляйте отзывы о местах\n\n"
        
        "<b>Техническая поддержка:</b>\n"
        "Если у вас возникли проблемы, нажмите /support\n"
        "Или напишите нам: @support_parking_bot"
    )
    
    await message.answer(help_text)

# ==================== КОМАНДА /PROFILE ====================

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Обработчик команды /profile"""
    from handlers.utils import format_user_info
    
    user = db.get_user(telegram_id=message.from_user.id)
    
    if not user:
        await message.answer(
            "❌ Вы не зарегистрированы. Нажмите /start для регистрации."
        )
        return
    
    profile_info = format_user_info(user)
    
    await message.answer(
        profile_info,
        reply_markup=kb_main.get_profile_menu()
    )

# ==================== КОМАНДА /SUPPORT ====================

@router.message(Command("support"))
async def cmd_support(message: Message):
    """Обработчик команды /support"""
    support_text = (
        "📞 <b>Техническая поддержка</b>\n\n"
        
        "<b>Связь с поддержкой:</b>\n"
        "Telegram: @support_parking_bot\n"
        "Email: support@parkingbot.ru\n"
        "Телефон: +7 (999) 000-00-00\n\n"
        
        "<b>Часы работы:</b>\n"
        "Пн-Пт: 9:00 - 18:00\n"
        "Сб-Вс: 10:00 - 16:00\n\n"
        
        "<b>Что мы можем помочь:</b>\n"
        "• Проблемы с регистрацией\n"
        "• Вопросы по бронированию\n"
        "• Проблемы с оплатой\n"
        "• Жалобы на пользователей\n"
        "• Предложения по улучшению\n\n"
        
        "<b>При обращении укажите:</b>\n"
        "1. Ваш ID: <code>{}</code>\n"
        "2. Описание проблемы\n"
        "3. Скриншоты (если есть)\n"
        "4. Время возникновения проблемы\n\n"
        
        "<i>Мы ответим в ближайшее время</i>"
    ).format(message.from_user.id)
    
    await message.answer(support_text)

# ==================== ОБРАБОТКА КНОПКИ "НАЗАД" ====================

@router.message(F.text == "🔙 Назад")
async def back_button(message: Message, state: FSMContext):
    """Обработчик кнопки Назад"""
    # Получаем текущее состояние
    current_state = await state.get_state()
    
    if current_state:
        # Если есть состояние, очищаем его и возвращаем в главное меню
        await state.clear()
    
    await show_main_menu(message)

# ==================== ОБРАБОТКА КНОПКИ "ОТМЕНА" ====================

@router.message(F.text == "❌ Отмена")
async def cancel_button(message: Message, state: FSMContext):
    """Обработчик кнопки Отмена"""
    await state.clear()
    await show_main_menu(message)

# ==================== ОБРАБОТКА ЛЮБЫХ СООБЩЕНИЙ ====================

@router.message()
async def handle_unknown(message: Message, state: FSMContext):
    """Обработчик неизвестных сообщений"""
    # Проверяем, зарегистрирован ли пользователь
    user = db.get_user(telegram_id=message.from_user.id)
    
    if not user:
        # Пользователь не зарегистрирован
        await message.answer(
            "❌ <b>Вы не зарегистрированы!</b>\n\n"
            "Для использования бота нажмите /start и пройдите регистрацию.",
            reply_markup=kb_main.get_main_menu()
        )
        return
    
    # Проверяем, не заблокирован ли пользователь
    if user.get('is_blocked'):
        await message.answer(
            "🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            "Обратитесь в поддержку для выяснения причин."
        )
        return
    
    # Если сообщение не обработано другими хендлерами
    await message.answer(
        "🤔 <b>Не понимаю вашу команду</b>\n\n"
        "Используйте кнопки меню или команды:\n"
        "/start - Главное меню\n"
        "/help - Помощь\n"
        "/profile - Профиль\n"
        "/support - Поддержка\n"
        "/admin - Вход в админ-панель",
        reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, db_instance=db)
    )
