"""
Обработчики для команды /start, регистрации и основного меню
"""

import logging
import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database import db
from keyboards import main as kb_main
from handlers.utils import (
    validate_phone, format_phone, validate_email, validate_card_number,
    log_user_action, notify_admins_about_event
)

logger = logging.getLogger(__name__)
router = Router()

# ==================== СОСТОЯНИЯ РЕГИСТРАЦИИ ====================

class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    waiting_for_phone = State()
    waiting_for_card_info = State()
    waiting_for_bank = State()

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
        full_name = message.from_user.full_name or f"User_{user_id}"
        
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
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
        f"Для начала работы нужно пройти быструю регистрацию.\n\n"
        f"<b>Шаг 1/3: Укажите ваш номер телефона:</b>\n"
        f"📱 Формат: +79991234567 или 89991234567\n\n"
        f"<i>Номер нужен для связи при бронировании</i>"
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
                "Или нажмите кнопку '📞 Отправить контакт'",
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
                "Если это ваш телефон, обратитесь в поддержку.",
                reply_markup=kb_main.get_contact_keyboard()
            )
            return
        
        # Сохраняем телефон
        await state.update_data(phone=formatted_phone)
        
        # Спрашиваем информацию о карте
        await message.answer(
            "💳 <b>Шаг 2/3: Укажите данные карты для получения оплат:</b>\n\n"
            "Формат: <code>XXXX XXXX XXXX XXXX</code>\n\n"
            "Примеры:\n"
            "• 2200 1234 5678 9012\n"
            "• 2202 2345 6789 0123\n\n"
            "<i>Номер карты будет виден только при бронировании вашего места</i>",
            reply_markup=kb_main.get_back_keyboard()
        )
        
        await state.set_state(RegistrationStates.waiting_for_card_info)
        
    except Exception as e:
        logger.error(f"Ошибка обработки телефона: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_contact_keyboard()
        )

# ==================== ПОЛУЧЕНИЕ НОМЕРА КАРТЫ ====================

@router.message(RegistrationStates.waiting_for_card_info)
async def process_card_info(message: Message, state: FSMContext):
    """Обработка введенного номера карты"""
    try:
        card_text = message.text.strip()
        
        # Валидируем номер карты
        validated_card = validate_card_number(card_text)
        if not validated_card:
            await message.answer(
                "❌ <b>Неверный формат номера карты!</b>\n\n"
                "Пожалуйста, укажите номер карты в формате:\n"
                "• 2200 1234 5678 9012\n"
                "• 16 цифр, можно с пробелами\n\n"
                "<i>Номер карты должен быть действительным</i>",
                reply_markup=kb_main.get_back_keyboard()
            )
            return
        
        # Сохраняем номер карты (маскированный)
        await state.update_data(card_number=validated_card)
        
        # Спрашиваем банк
        await message.answer(
            "🏦 <b>Шаг 3/3: Укажите банк карты:</b>\n\n"
            "Выберите банк из списка или введите свой:\n"
            "• Сбербанк\n"
            "• Тинькофф\n"
            "• Альфа-Банк\n"
            "• ВТБ\n"
            "• Газпромбанк\n"
            "• Другой (введите название)",
            reply_markup=kb_main.get_banks_keyboard()
        )
        
        await state.set_state(RegistrationStates.waiting_for_bank)
        
    except Exception as e:
        logger.error(f"Ошибка обработки номера карты: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_back_keyboard()
        )

# ==================== ПОЛУЧЕНИЕ БАНКА ====================

@router.message(RegistrationStates.waiting_for_bank)
async def process_bank(message: Message, state: FSMContext):
    """Обработка введенного банка"""
    try:
        bank = message.text.strip()
        
        # Проверяем стандартные банки
        bank = bank.capitalize()
        
        # Получаем все данные
        user_data = await state.get_data()
        
        # Регистрируем пользователя
        user_id = db.register_user(
            telegram_id=user_data['telegram_id'],
            full_name=user_data['full_name'],
            phone=user_data['phone'],
            username=user_data.get('username'),
            card_number=user_data['card_number'],
            bank=bank
        )
        
        if user_id:
            # Успешная регистрация
            await complete_registration(message, state, user_id, user_data, bank)
        else:
            await message.answer(
                "❌ <b>Ошибка регистрации!</b>\n\n"
                "Не удалось зарегистрировать пользователя.\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
            )
            
    except Exception as e:
        logger.error(f"Ошибка обработки информации о банке: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_back_keyboard()
        )

async def complete_registration(message: Message, state: FSMContext, user_id: int, user_data: dict, bank: str):
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
            f"💳 Карта: {user['card_number']} ({bank})\n\n"
            f"🎉 <b>Добро пожаловать в сервис бронирования парковок!</b>\n\n"
            f"<b>Теперь вы можете:</b>\n"
            f"• 🚗 Найти и забронировать парковочное место\n"
            f"• 🏠 Сдавать в аренду свои места\n"
            f"• 📊 Управлять бронированиями\n"
            f"• ⭐ Оставлять отзывы\n"
            f"• 💰 Получать оплату на свою карту\n\n"
            f"<i>Используйте меню ниже для навигации</i>"
        )
        
        # Отправляем приветственное сообщение
        await message.answer(
            success_text,
            reply_markup=kb_main.get_main_menu(telegram_id=user['telegram_id'])
        )
        
        # Логируем регистрацию
        log_user_action(user_id, "registration_complete", f"Пользователь зарегистрирован: {user['full_name']}")
        
        # Уведомляем администраторов
        await notify_admins_about_event(
            "Новая регистрация",
            f"Зарегистрирован новый пользователь:\n"
            f"👤 {user['full_name']}\n"
            f"📱 {user['phone']}\n"
            f"🏦 {bank}\n"
            f"🆔 {user['telegram_id']}",
            {"user_id": user_id}
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка завершения регистрации: {e}")
        await message.answer(
            "✅ Регистрация завершена, но произошла ошибка при отправке приветствия.",
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
        )
        await state.clear()

# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.message(F.text == "🔙 Главное меню")
@router.message(F.text == "🏠 Главное меню")
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
                "Нажмите /start чтобы начать."
            )
            return
        
        # Проверяем, не заблокирован ли пользователь
        if user.get('is_blocked'):
            await message.answer(
                "🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
                "Обратитесь в поддержку для выяснения причин."
            )
            return
        
        # Обновляем время последней активности
        db.update_user(user['id'], last_active=datetime.now())
        
        # Формируем приветственное сообщение
        welcome_text = (
            f"👋 <b>Добро пожаловать, {user['full_name']}!</b>\n\n"
            f"Я - ваш помощник в поиске и бронировании парковочных мест.\n\n"
        )
        
        # Добавляем информацию о бронированиях
        active_bookings = db.count_bookings(user_id=user['id'], status='active')
        if active_bookings > 0:
            welcome_text += f"📋 Активных бронирований: <b>{active_bookings}</b>\n"
        
        # Добавляем информацию о местах
        user_spots = db.get_user_spots(user['id'])
        if user_spots:
            welcome_text += f"🏠 Ваших мест: <b>{len(user_spots)}</b>\n"
        
        welcome_text += f"\n👇 <b>Выберите действие в меню ниже:</b>"
        
        # Отправляем сообщение с динамической клавиатурой
        await message.answer(
            welcome_text,
            reply_markup=kb_main.get_main_menu(telegram_id=user_id, is_admin=db.is_admin_user(user_id))
        )
        
    except Exception as e:
        logger.error(f"Ошибка показа главного меню: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=kb_main.get_main_menu(telegram_id=user_id)
        )

# ==================== КОМАНДА /ADMIN ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, command: CommandObject):
    """Вход в админ-панель по паролю с поддержкой аргументов"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, не является ли пользователь уже админом
        if db.is_admin_user(user_id):
            await message.answer(
                "👑 <b>Вы уже администратор!</b>\n\n"
                "Используйте кнопку '⚙️ Админ-панель' в главном меню.",
                reply_markup=kb_main.get_main_menu(telegram_id=user_id, is_admin=True)
            )
            return
        
        # Если пользователь не зарегистрирован
        user = db.get_user(telegram_id=user_id)
        if not user:
            await message.answer(
                "❌ <b>Для входа в админ-панель нужно быть зарегистрированным пользователем!</b>\n\n"
                "Нажмите /start чтобы зарегистрироваться."
            )
            return
        
        # Проверяем активную сессию
        session = db.get_admin_session(user['id'])
        if session and datetime.fromisoformat(session['expires_at']) > datetime.now():
            await message.answer(
                "✅ <b>У вас уже есть активная админ-сессия!</b>\n\n"
                "Используйте кнопку '⚙️ Админ-панель' в главном меню.",
                reply_markup=kb_main.get_main_menu(telegram_id=user_id, is_admin=True)
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
            "Отправьте /cancel для отмены",
            reply_markup=kb_main.get_cancel_keyboard()
        )
        
        # Сохраняем ID пользователя для проверки пароля
        await state.update_data(admin_auth_user_id=user['id'])
        await state.set_state(AdminAuthStates.waiting_for_password)
        
    except Exception as e:
        logger.error(f"Ошибка команды /admin: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, is_admin=True)
                )
                
                # Логируем вход
                log_user_action(user['id'], "admin_login", f"Вход в админ-панель по паролю (аргументы)")
                
                # Уведомляем всех постоянных админов
                admins = db.get_all_users(is_admin=True)
                for admin in admins:
                    if admin['telegram_id'] != message.from_user.id:
                        db.add_notification(
                            admin['id'],
                            "admin_login",
                            "📢 Вход в админ-панель",
                            f"Пользователь {user['full_name']} вошел в админ-панель по паролю.\n"
                            f"ID: {user['telegram_id']}\n"
                            f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                        )
            else:
                await message.answer(
                    "❌ <b>Ошибка создания сессии!</b>\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
            )
            await state.clear()
            return
        
        user = db.get_user(user_id=user_id)
        if not user:
            await message.answer(
                "❌ Пользователь не найден.",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, is_admin=True)
                )
                
                # Логируем вход
                log_user_action(user_id, "admin_login", f"Вход в админ-панель по паролю")
                
                # Уведомляем всех постоянных админов
                admins = db.get_all_users(is_admin=True)
                for admin in admins:
                    if admin['telegram_id'] != message.from_user.id:
                        db.add_notification(
                            admin['id'],
                            "admin_login",
                            "📢 Вход в админ-панель",
                            f"Пользователь {user['full_name']} вошел в админ-панель по паролю.\n"
                            f"ID: {user['telegram_id']}\n"
                            f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                        )
            else:
                await message.answer(
                    "❌ <b>Ошибка создания сессии!</b>\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
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
        
        # Удаляем сессию
        success = db.delete_admin_session(user['id'])
        
        if success:
            await message.answer(
                "✅ <b>Админ-сессия завершена!</b>\n\n"
                "Доступ к админ-панели отозван.\n\n"
                "Для входа снова используйте /admin",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
            )
            
            # Логируем выход
            log_user_action(user['id'], "admin_logout", "Выход из админ-панели")
        else:
            await message.answer(
                "ℹ️ <b>У вас нет активной админ-сессии</b>\n\n"
                "Используйте /admin для входа в админ-панель.",
                reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
            )
        
    except Exception as e:
        logger.error(f"Ошибка команды /admin_logout: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id)
        )

# ==================== ОБРАБОТКА КНОПКИ "НАЗАД" ====================

@router.message(F.text == "🔙 Назад")
async def back_button(message: Message, state: FSMContext):
    """Обработчик кнопки Назад"""
    # Очищаем состояние
    await state.clear()
    
    # Возвращаем в главное меню
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
            "Для использования бота нажмите /start и пройдите регистрацию."
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
        "/admin - Вход в админ-панель\n"
        "/admin_logout - Выход из админ-панели",
        reply_markup=kb_main.get_main_menu(telegram_id=message.from_user.id, is_admin=db.is_admin_user(message.from_user.id))
    )
