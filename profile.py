"""
Обработчики для управления профилем пользователя
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
    validate_phone, format_phone, validate_email,
    validate_car_plate, validate_card_number,
    format_user_info, format_price, log_user_action
)

logger = logging.getLogger(__name__)
router = Router()

# ==================== СОСТОЯНИЯ ДЛЯ РЕДАКТИРОВАНИЯ ПРОФИЛЯ ====================

class ProfileStates(StatesGroup):
    """Состояния для редактирования профиля"""
    editing_phone = State()
    editing_email = State()
    editing_car = State()
    editing_card = State()
    adding_car = State()
    adding_money = State()

# ==================== МЕНЮ ПРОФИЛЯ ====================

@router.message(F.text == "👤 Профиль")
async def profile_menu(message: Message, state: FSMContext):
    """Меню профиля пользователя"""
    await state.clear()
    
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Нажмите /start")
        return
    
    # Форматируем информацию о пользователе
    user_info = format_user_info(user)
    
    await message.answer(
        user_info,
        reply_markup=kb_main.get_profile_menu()
    )

# ==================== РЕДАКТИРОВАНИЕ ПРОФИЛЯ ====================

@router.message(F.text == "✏️ Редактировать профиль")
async def edit_profile_menu(message: Message):
    """Меню редактирования профиля"""
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы")
        return
    
    await message.answer(
        "✏️ <b>Редактирование профиля</b>\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=kb_main.get_profile_edit_keyboard()
    )

# ==================== РЕДАКТИРОВАНИЕ ТЕЛЕФОНА ====================

@router.callback_query(F.data == "edit_phone")
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования телефона"""
    await state.set_state(ProfileStates.editing_phone)
    
    await callback.message.edit_text(
        "📱 <b>Изменение номера телефона</b>\n\n"
        "Введите новый номер телефона:\n\n"
        "<i>Формат:</i> +79991234567 или 89991234567\n"
        "<i>Или нажмите кнопку для отправки контакта</i>",
        reply_markup=kb_main.get_contact_keyboard(phone="current")
    )
    await callback.answer()

@router.message(ProfileStates.editing_phone)
async def edit_phone_process(message: Message, state: FSMContext):
    """Обработка нового телефона"""
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
                "Или нажмите кнопку для отправки контакта.",
                reply_markup=kb_main.get_contact_keyboard()
            )
            return
        
        # Форматируем телефон
        formatted_phone = format_phone(phone)
        
        # Проверяем, не занят ли телефон другим пользователем
        existing_user = db.get_user_by_phone(formatted_phone)
        current_user = db.get_user(telegram_id=message.from_user.id)
        
        if existing_user and existing_user['id'] != current_user['id']:
            await message.answer(
                "❌ <b>Этот телефон уже зарегистрирован!</b>\n\n"
                "Пожалуйста, используйте другой номер телефона.",
                reply_markup=kb_main.get_contact_keyboard()
            )
            return
        
        # Обновляем телефон в базе
        success = db.update_user(current_user['id'], phone=formatted_phone)
        
        if success:
            # Логируем действие
            log_user_action(current_user['id'], "phone_updated", f"Телефон изменен на: {formatted_phone}")
            
            await message.answer(
                f"✅ <b>Номер телефона изменен!</b>\n\n"
                f"Новый номер: {formatted_phone}\n\n"
                f"Теперь вы можете получать SMS-уведомления и использовать телефон для входа.",
                reply_markup=kb_main.get_profile_menu()
            )
        else:
            await message.answer(
                "❌ <b>Ошибка изменения телефона!</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                reply_markup=kb_main.get_profile_menu()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка изменения телефона: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_profile_menu()
        )
        await state.clear()

# ==================== РЕДАКТИРОВАНИЕ EMAIL ====================

@router.callback_query(F.data == "edit_email")
async def edit_email_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования email"""
    await state.set_state(ProfileStates.editing_email)
    
    await callback.message.edit_text(
        "📧 <b>Изменение Email</b>\n\n"
        "Введите новый Email адрес:\n\n"
        "<i>Формат:</i> example@mail.ru\n"
        "<i>Для удаления Email отправьте \"удалить\"</i>",
        reply_markup=kb_main.get_back_keyboard()
    )
    await callback.answer()

@router.message(ProfileStates.editing_email)
async def edit_email_process(message: Message, state: FSMContext):
    """Обработка нового email"""
    try:
        email = message.text.strip()
        
        # Проверяем, хочет ли пользователь удалить email
        if email.lower() in ['удалить', 'delete', 'нет', 'no', 'none']:
            email = None
        else:
            # Валидируем email
            if not validate_email(email):
                await message.answer(
                    "❌ <b>Неверный формат Email!</b>\n\n"
                    "Пожалуйста, введите Email в формате:\n"
                    "• example@mail.ru\n"
                    "• example@gmail.com\n\n"
                    "Или отправьте \"удалить\" для удаления Email",
                    reply_markup=kb_main.get_back_keyboard()
                )
                return
        
        # Обновляем email в базе
        user = db.get_user(telegram_id=message.from_user.id)
        success = db.update_user(user['id'], email=email)
        
        if success:
            # Логируем действие
            action = "удален" if email is None else f"изменен на: {email}"
            log_user_action(user['id'], "email_updated", f"Email {action}")
            
            if email:
                await message.answer(
                    f"✅ <b>Email изменен!</b>\n\n"
                    f"Новый Email: {email}\n\n"
                    f"Теперь вы будете получать email-уведомления о бронированиях и оплатах.",
                    reply_markup=kb_main.get_profile_menu()
                )
            else:
                await message.answer(
                    f"✅ <b>Email удален!</b>\n\n"
                    f"Вы больше не будете получать email-уведомления.",
                    reply_markup=kb_main.get_profile_menu()
                )
        else:
            await message.answer(
                "❌ <b>Ошибка изменения Email!</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                reply_markup=kb_main.get_profile_menu()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка изменения email: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_profile_menu()
        )
        await state.clear()

# ==================== РЕДАКТИРОВАНИЕ АВТОМОБИЛЯ ====================

@router.callback_query(F.data == "edit_car")
async def edit_car_menu(callback: CallbackQuery):
    """Меню редактирования автомобиля"""
    user = db.get_user(telegram_id=callback.from_user.id)
    if not user:
        await callback.answer("❌ Вы не зарегистрированы")
        return
    
    # Получаем текущую информацию об автомобиле
    car_info = ""
    if user['car_plate']:
        car_info = user['car_plate']
        if user['car_brand']:
            car_info = f"{user['car_brand']}"
            if user['car_model']:
                car_info += f" {user['car_model']}"
            car_info += f" ({user['car_plate']})"
    
    keyboard = kb_inline.InlineKeyboardBuilder()
    
    if user['car_plate']:
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="✏️ Изменить данные",
            callback_data="change_car_data"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="🗑️ Удалить автомобиль",
            callback_data="delete_car"
        ))
    else:
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="➕ Добавить автомобиль",
            callback_data="add_car"
        ))
    
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_profile_edit"
    ))
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        f"🚗 <b>Управление автомобилями</b>\n\n"
        f"{'У вас нет добавленных автомобилей.' if not user['car_plate'] else f'Текущий автомобиль: {car_info}'}\n\n"
        f"Добавление автомобиля поможет:\n"
        f"• Быстрее заполнять данные при бронировании\n"
        f"• Владельцам мест идентифицировать ваш автомобиль\n"
        f"• Получать персонализированные предложения",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "change_car_data")
async def change_car_data_start(callback: CallbackQuery, state: FSMContext):
    """Начало изменения данных автомобиля"""
    await state.set_state(ProfileStates.editing_car)
    
    await callback.message.edit_text(
        "🚗 <b>Изменение данных автомобиля</b>\n\n"
        "Введите новые данные вашего автомобиля:\n\n"
        "<i>Формат:</i>\n"
        "<code>А123БВ77 Бренд Модель</code>\n\n"
        "<i>Примеры:</i>\n"
        "• А123БВ77 Toyota Camry\n"
        "• А123БВ77 (только номер)\n"
        "• удалить (для удаления автомобиля)\n\n"
        "<i>Для российских номеров используйте кириллицу</i>",
        reply_markup=kb_main.get_back_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "add_car")
async def add_car_start(callback: CallbackQuery, state: FSMContext):
    """Добавление нового автомобиля"""
    await state.set_state(ProfileStates.adding_car)
    
    await callback.message.edit_text(
        "🚗 <b>Добавление автомобиля</b>\n\n"
        "Введите данные вашего автомобиля:\n\n"
        "<i>Формат:</i>\n"
        "<code>А123БВ77 Бренд Модель</code>\n\n"
        "<i>Примеры:</i>\n"
        "• А123БВ77 Toyota Camry\n"
        "• А123БВ77 (только номер)\n\n"
        "<i>Для российских номеров используйте кириллицу</i>",
        reply_markup=kb_main.get_back_keyboard()
    )
    await callback.answer()

@router.message(ProfileStates.editing_car)
@router.message(ProfileStates.adding_car)
async def process_car_data(message: Message, state: FSMContext):
    """Обработка данных автомобиля"""
    try:
        car_text = message.text.strip()
        
        # Проверяем, хочет ли пользователь удалить автомобиль
        if car_text.lower() in ['удалить', 'delete', 'none']:
            car_plate = None
            car_brand = None
            car_model = None
        else:
            # Парсим информацию об автомобиле
            parts = car_text.split()
            
            if len(parts) == 0:
                await message.answer(
                    "❌ <b>Введите данные автомобиля!</b>\n\n"
                    "Пожалуйста, введите номер или полные данные автомобиля.",
                    reply_markup=kb_main.get_back_keyboard()
                )
                return
            
            # Первая часть - номер
            car_plate = parts[0].upper()
            
            # Валидируем номер
            if not validate_car_plate(car_plate):
                await message.answer(
                    "❌ <b>Неверный формат номера!</b>\n\n"
                    "Пожалуйста, введите номер в формате:\n"
                    "• А123БВ77 (российский номер)\n"
                    "• A123BC77 (иностранный номер)\n\n"
                    "<i>Используйте кириллицу для российских номеров</i>",
                    reply_markup=kb_main.get_back_keyboard()
                )
                return
            
            # Остальные части - бренд и модель
            if len(parts) >= 2:
                car_brand = parts[1]
                car_model = ' '.join(parts[2:]) if len(parts) > 2 else None
            else:
                car_brand = None
                car_model = None
        
        # Обновляем данные в базе
        user = db.get_user(telegram_id=message.from_user.id)
        success = db.update_user(
            user['id'],
            car_plate=car_plate,
            car_brand=car_brand,
            car_model=car_model
        )
        
        if success:
            # Логируем действие
            if car_plate is None:
                log_user_action(user['id'], "car_deleted", "Автомобиль удален")
                await message.answer(
                    "✅ <b>Автомобиль удален!</b>\n\n"
                    "Данные об автомобиле были удалены из вашего профиля.",
                    reply_markup=kb_main.get_profile_menu()
                )
            else:
                # Форматируем информацию об автомобиле
                car_info = car_plate
                if car_brand:
                    car_info = f"{car_brand}"
                    if car_model:
                        car_info += f" {car_model}"
                    car_info += f" ({car_plate})"
                
                log_user_action(user['id'], "car_updated", f"Автомобиль обновлен: {car_info}")
                
                await message.answer(
                    f"✅ <b>Данные автомобиля обновлены!</b>\n\n"
                    f"Автомобиль: {car_info}\n\n"
                    f"Теперь при бронировании эти данные будут подставляться автоматически.",
                    reply_markup=kb_main.get_profile_menu()
                )
        else:
            await message.answer(
                "❌ <b>Ошибка обновления данных автомобиля!</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                reply_markup=kb_main.get_profile_menu()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки данных автомобиля: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_profile_menu()
        )
        await state.clear()

@router.callback_query(F.data == "delete_car")
async def delete_car_confirm(callback: CallbackQuery):
    """Подтверждение удаления автомобиля"""
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="✅ Да, удалить",
        callback_data="confirm_delete_car"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="❌ Нет, отмена",
        callback_data="back_to_car_menu"
    ))
    keyboard.adjust(2)
    
    await callback.message.edit_text(
        "⚠️ <b>Подтверждение удаления</b>\n\n"
        "Вы уверены, что хотите удалить данные об автомобиле?\n\n"
        "<i>Это действие нельзя отменить.</i>",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "confirm_delete_car")
async def confirm_delete_car(callback: CallbackQuery):
    """Подтвержденное удаление автомобиля"""
    user = db.get_user(telegram_id=callback.from_user.id)
    if not user:
        await callback.answer("❌ Вы не зарегистрированы")
        return
    
    success = db.update_user(
        user['id'],
        car_plate=None,
        car_brand=None,
        car_model=None
    )
    
    if success:
        log_user_action(user['id'], "car_deleted", "Автомобиль удален")
        
        await callback.message.edit_text(
            "✅ <b>Автомобиль удален!</b>\n\n"
            "Данные об автомобиле были удалены из вашего профиля.",
            reply_markup=kb_inline.InlineKeyboardBuilder()
                .add(kb_inline.InlineKeyboardButton(
                    text="🔙 Назад к профилю",
                    callback_data="back_to_profile"
                ))
                .adjust(1)
                .as_markup()
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка удаления автомобиля!</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=kb_inline.InlineKeyboardBuilder()
                .add(kb_inline.InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="back_to_car_menu"
                ))
                .adjust(1)
                .as_markup()
        )
    await callback.answer()

# ==================== РЕДАКТИРОВАНИЕ БАНКОВСКОЙ КАРТЫ ====================

@router.callback_query(F.data == "edit_card")
async def edit_card_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования банковской карты"""
    await state.set_state(ProfileStates.editing_card)
    
    await callback.message.edit_text(
        "💳 <b>Изменение банковской карты</b>\n\n"
        "Введите номер банковской карты:\n\n"
        "<i>Формат:</i> 2200 1234 5678 9012\n"
        "<i>Или отправьте \"удалить\" для удаления карты</i>\n\n"
        "<b>Важно:</b> Мы храним только последние 4 цифры карты.\n"
        "Полный номер карты не сохраняется в базе данных.",
        reply_markup=kb_main.get_back_keyboard()
    )
    await callback.answer()

@router.message(ProfileStates.editing_card)
async def edit_card_process(message: Message, state: FSMContext):
    """Обработка новой банковской карты"""
    try:
        card_text = message.text.strip()
        
        # Проверяем, хочет ли пользователь удалить карту
        if card_text.lower() in ['удалить', 'delete', 'none']:
            card_number = None
            bank = None
        else:
            # Валидируем номер карты
            masked_card = validate_card_number(card_text)
            if not masked_card:
                await message.answer(
                    "❌ <b>Неверный номер карты!</b>\n\n"
                    "Пожалуйста, введите корректный номер банковской карты.\n"
                    "Или отправьте \"удалить\" для удаления карты.",
                    reply_markup=kb_main.get_back_keyboard()
                )
                return
            
            # Спрашиваем банк
            await state.update_data(card_number=masked_card)
            await message.answer(
                "🏦 <b>Укажите банк карты:</b>\n\n"
                "<i>Примеры:</i>\n"
                "• Сбербанк\n"
                "• Тинькофф\n"
                "• Альфа-Банк\n"
                "• ВТБ\n"
                "• Газпромбанк\n\n"
                "<i>Или любой другой банк</i>",
                reply_markup=kb_main.get_back_keyboard()
            )
            return
        
        # Обновляем данные в базе
        user = db.get_user(telegram_id=message.from_user.id)
        success = db.update_user(
            user['id'],
            card_number=card_number,
            bank=bank
        )
        
        if success:
            # Логируем действие
            if card_number is None:
                log_user_action(user['id'], "card_deleted", "Банковская карта удалена")
                await message.answer(
                    "✅ <b>Банковская карта удалена!</b>\n\n"
                    "Данные карты были удалены из вашего профиля.",
                    reply_markup=kb_main.get_profile_menu()
                )
            else:
                log_user_action(user['id'], "card_updated", f"Карта обновлена: {masked_card}")
                await message.answer(
                    f"✅ <b>Банковская карта обновлена!</b>\n\n"
                    f"Карта: {masked_card}\n"
                    f"{f'Банк: {bank}' if bank else ''}\n\n"
                    f"Теперь вы можете использовать эту карту для оплаты бронирований.",
                    reply_markup=kb_main.get_profile_menu()
                )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка изменения карты: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_profile_menu()
        )
        await state.clear()

@router.message(ProfileStates.editing_card)
async def process_bank(message: Message, state: FSMContext):
    """Обработка банка для карты"""
    try:
        bank = message.text.strip()
        data = await state.get_data()
        masked_card = data.get('card_number')
        
        if not masked_card:
            await message.answer(
                "❌ <b>Ошибка данных!</b>\n\n"
                "Попробуйте начать заново.",
                reply_markup=kb_main.get_profile_menu()
            )
            await state.clear()
            return
        
        # Обновляем данные в базе
        user = db.get_user(telegram_id=message.from_user.id)
        success = db.update_user(
            user['id'],
            card_number=masked_card,
            bank=bank
        )
        
        if success:
            log_user_action(user['id'], "card_updated", f"Карта обновлена: {masked_card}, банк: {bank}")
            
            await message.answer(
                f"✅ <b>Банковская карта обновлена!</b>\n\n"
                f"Карта: {masked_card}\n"
                f"Банк: {bank}\n\n"
                f"Теперь вы можете использовать эту карту для оплаты бронирований.",
                reply_markup=kb_main.get_profile_menu()
            )
        else:
            await message.answer(
                "❌ <b>Ошибка обновления карты!</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                reply_markup=kb_main.get_profile_menu()
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки банка: {e}")
        await message.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=kb_main.get_profile_menu()
        )
        await state.clear()

# ==================== БАЛАНС ====================

@router.message(F.text == "💰 Баланс")
async def balance_menu(message: Message):
    """Меню баланса"""
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы")
        return
    
    # Получаем историю транзакций
    transactions = db.get_user_payments(user['id'], as_payer=True, limit=5)
    
    balance_text = f"💰 <b>Ваш баланс:</b> {format_price(user['balance'])} ₽\n\n"
    
    if transactions:
        balance_text += "<b>Последние операции:</b>\n"
        for t in transactions:
            amount = f"+{format_price(t['amount'])}" if t['amount'] > 0 else format_price(t['amount'])
            balance_text += f"• {amount} ₽ - {t.get('description', 'Операция')}\n"
            balance_text += f"  <i>{datetime.fromisoformat(t['created_at']).strftime('%d.%m.%Y %H:%M')}</i>\n\n"
    
    keyboard = kb_inline.InlineKeyboardBuilder()
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="💵 Пополнить баланс",
        callback_data="add_money"
    ))
    
    if user['balance'] > 0:
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="💸 Вывести средства",
            callback_data="withdraw_money"
        ))
    
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="📋 История операций",
        callback_data="transaction_history"
    ))
    keyboard.add(kb_inline.InlineKeyboardButton(
        text="🔙 Назад к профилю",
        callback_data="back_to_profile"
    ))
    keyboard.adjust(1)
    
    await message.answer(
        balance_text,
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data == "add_money")
async def add_money_start(callback: CallbackQuery, state: FSMContext):
    """Начало пополнения баланса"""
    await state.set_state(ProfileStates.adding_money)
    
    await callback.message.edit_text(
        "💵 <b>Пополнение баланса</b>\n\n"
        "Введите сумму для пополнения (в рублях):\n\n"
        "<i>Минимальная сумма: 100 ₽</i>\n"
        "<i>Максимальная сумма: 50 000 ₽</i>\n\n"
        "<b>После подтверждения вы будете перенаправлены на страницу оплаты.</b>",
        reply_markup=kb_main.get_back_keyboard()
    )
    await callback.answer()

@router.message(ProfileStates.adding_money)
async def add_money_process(message: Message, state: FSMContext):
    """Обработка суммы пополнения"""
    try:
        amount = float(message.text.strip())
        
        if amount < 100:
            await message.answer(
                "❌ <b>Минимальная сумма пополнения - 100 ₽!</b>\n\n"
                "Введите сумму от 100 рублей:",
                reply_markup=kb_main.get_back_keyboard()
            )
            return
        
        if amount > 50000:
            await message.answer(
                "❌ <b>Максимальная сумма пополнения - 50 000 ₽!</b>\n\n"
                "Введите сумму до 50 000 рублей:",
                reply_markup=kb_main.get_back_keyboard()
            )
            return
        
        # Сохраняем сумму в состоянии
        await state.update_data(amount=amount)
        
        # Показываем методы оплаты
        keyboard = kb_inline.InlineKeyboardBuilder()
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="💳 Банковская карта",
            callback_data=f"pay_method_card_{amount}"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="📱 Qiwi",
            callback_data=f"pay_method_qiwi_{amount}"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="🤝 ЮMoney",
            callback_data=f"pay_method_yoomoney_{amount}"
        ))
        keyboard.add(kb_inline.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_balance"
        ))
        keyboard.adjust(1)
        
        await message.answer(
            f"💵 <b>Пополнение баланса на {format_price(amount)} ₽</b>\n\n"
            f"Выберите способ оплаты:",
            reply_markup=keyboard.as_markup()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат суммы!</b>\n\n"
            "Введите число (например: 1000 или 500.50):",
            reply_markup=kb_main.get_back_keyboard()
        )

# ==================== МОИ ОТЗЫВЫ ====================

@router.message(F.text == "⭐ Мои отзывы")
async def my_reviews(message: Message):
    """Мои отзывы"""
    user = db.get_user(telegram_id=message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы")
        return
    
    # Получаем отзывы пользователя
    reviews = db.get_user_reviews(user['id'], as_reviewer=True, limit=10)
    
    if not reviews:
        await message.answer(
            "⭐ <b>У вас пока нет отзывов</b>\n\n"
            "Оставляйте отзывы после завершения бронирований!\n"
            "Это поможет другим пользователям выбирать лучшие места.",
            reply_markup=kb_main.get_profile_menu()
        )
        return
    
    text = "⭐ <b>Ваши отзывы:</b>\n\n"
    
    for i, review in enumerate(reviews, 1):
        stars = "⭐" * review['rating']
        text += f"{stars} <b>Отзыв #{i}</b>\n"
        text += f"🏠 Место: #{review['spot_number']}\n"
        
        if review['comment']:
            text += f"💬 {review['comment'][:100]}...\n"
        
        if review['response']:
            text += f"📝 <i>Ответ владельца: {review['response'][:100]}...</i>\n"
        
        text += f"📅 {datetime.fromisoformat(review['created_at']).strftime('%d.%m.%Y')}\n\n"
    
    await message.answer(
        text,
        reply_markup=kb_main.get_profile_menu()
    )

# ==================== НАСТРОЙКИ ====================

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    """Настройки профиля"""
    await message.answer(
        "⚙️ <b>Настройки профиля</b>\n\n"
        "В этом разделе вы можете настроить:\n\n"
        "• 📢 Уведомления - какие уведомления получать\n"
        "• 🔒 Безопасность - смена пароля, 2FA\n"
        "• 🌐 Язык - выбор языка интерфейса\n"
        "• 👥 Приватность - настройки видимости профиля\n\n"
        "<i>Раздел в разработке...</i>",
        reply_markup=kb_main.get_profile_menu()
    )

# ==================== ОБРАБОТКА КНОПОК НАВИГАЦИИ ====================

@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery):
    """Вернуться к профилю"""
    user = db.get_user(telegram_id=callback.from_user.id)
    if not user:
        await callback.answer("❌ Вы не зарегистрированы")
        return
    
    user_info = format_user_info(user)
    
    await callback.message.edit_text(
        user_info,
        reply_markup=kb_main.get_profile_edit_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_profile_edit")
async def back_to_profile_edit(callback: CallbackQuery):
    """Вернуться к редактированию профиля"""
    await edit_profile_menu(callback.message)
    await callback.answer()

@router.callback_query(F.data == "back_to_car_menu")
async def back_to_car_menu(callback: CallbackQuery):
    """Вернуться к меню автомобилей"""
    await edit_car_menu(callback)
    await callback.answer()

@router.callback_query(F.data == "back_to_balance")
async def back_to_balance(callback: CallbackQuery):
    """Вернуться к балансу"""
    await balance_menu(callback.message)
    await callback.answer()