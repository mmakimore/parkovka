from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_menu(telegram_id=None, db_instance=None):
    """Главное меню с динамической кнопкой админ-панели"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="🚗 Найти место"))
    builder.add(KeyboardButton(text="📊 Мои бронирования"))
    builder.add(KeyboardButton(text="🏠 Мои места"))
    builder.add(KeyboardButton(text="👤 Профиль"))
    builder.add(KeyboardButton(text="📢 Уведомления"))
    
    # Проверяем, есть ли доступ к админ-панели
    is_admin = False
    if telegram_id and db_instance:
        try:
            is_admin = db_instance.is_admin_user(telegram_id)
        except Exception as e:
            print(f"Ошибка проверки прав админа: {e}")
            is_admin = False
    
    if is_admin:
        builder.add(KeyboardButton(text="⚙️ Админ-панель"))
    
    # Настройка макета
    if is_admin:
        builder.adjust(2, 2, 2, 1)  # 2-2-2-1 (админка отдельно)
    else:
        builder.adjust(2, 2, 1)     # 2-2-1
    
    return builder.as_markup(resize_keyboard=True)

def get_cancel_keyboard():
    """Клавиатура отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_back_keyboard():
    """Клавиатура Назад"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True
    )

def get_yes_no_keyboard():
    """Клавиатура Да/Нет"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="✅ Да"))
    builder.add(KeyboardButton(text="❌ Нет"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# ==================== МЕНЮ МЕСТ ====================

def get_spots_menu():
    """Меню работы с местами"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="➕ Добавить место"))
    builder.add(KeyboardButton(text="📋 Мои места"))
    builder.add(KeyboardButton(text="📅 Управление расписанием"))
    builder.add(KeyboardButton(text="💰 Статистика доходов"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_spot_management_keyboard(spot_id):
    """Управление конкретным местом"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✏️ Редактировать",
        callback_data=f"edit_spot_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📅 Расписание",
        callback_data=f"spot_schedule_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📊 Статистика",
        callback_data=f"spot_stats_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🗑️ Удалить",
        callback_data=f"delete_spot_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_spots"
    ))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

# ==================== МЕНЮ БРОНИРОВАНИЙ ====================

def get_bookings_menu():
    """Меню бронирований"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="🔍 Найти место"))
    builder.add(KeyboardButton(text="📋 Активные брони"))
    builder.add(KeyboardButton(text="✅ Подтвержденные"))
    builder.add(KeyboardButton(text="📅 Завершенные"))
    builder.add(KeyboardButton(text="❌ Отмененные"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_booking_actions_keyboard(booking_id, is_owner=False):
    """Действия с бронированием"""
    builder = InlineKeyboardBuilder()
    
    if is_owner:
        builder.add(InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_booking_{booking_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject_booking_{booking_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="💳 Оплатить",
            callback_data=f"pay_booking_{booking_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"cancel_booking_{booking_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="📞 Связаться",
        callback_data=f"contact_booking_{booking_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⭐ Оставить отзыв",
        callback_data=f"review_booking_{booking_id}"
    ))
    
    builder.adjust(2, 2)
    return builder.as_markup()

# ==================== МЕНЮ ПРОФИЛЯ ====================

def get_profile_menu():
    """Меню профиля"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="✏️ Редактировать профиль"))
    builder.add(KeyboardButton(text="💰 Баланс"))
    builder.add(KeyboardButton(text="📱 Мои автомобили"))
    builder.add(KeyboardButton(text="⭐ Мои отзывы"))
    builder.add(KeyboardButton(text="⚙️ Настройки"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_profile_edit_keyboard():
    """Редактирование профиля"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📱 Телефон",
        callback_data="edit_phone"
    ))
    builder.add(InlineKeyboardButton(
        text="📧 Email",
        callback_data="edit_email"
    ))
    builder.add(InlineKeyboardButton(
        text="🚗 Автомобиль",
        callback_data="edit_car"
    ))
    builder.add(InlineKeyboardButton(
        text="💳 Банковская карта",
        callback_data="edit_card"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_profile"
    ))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

# ==================== МЕНЮ УВЕДОМЛЕНИЙ ====================

def get_notifications_menu():
    """Меню уведомлений"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📨 Все уведомления"))
    builder.add(KeyboardButton(text="📥 Непрочитанные"))
    builder.add(KeyboardButton(text="✅ Отметить все прочитанными"))
    builder.add(KeyboardButton(text="⚙️ Настройки уведомлений"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_notification_actions_keyboard(notification_id):
    """Действия с уведомлением"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Прочитано",
        callback_data=f"read_notification_{notification_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🗑️ Удалить",
        callback_data=f"delete_notification_{notification_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_notifications"
    ))
    
    builder.adjust(2, 1)
    return builder.as_markup()

# ==================== АДМИН-ПАНЕЛЬ ====================

def get_admin_menu():
    """Меню админ-панели"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📊 Статистика"))
    builder.add(KeyboardButton(text="👥 Пользователи"))
    builder.add(KeyboardButton(text="🏠 Места"))
    builder.add(KeyboardButton(text="📋 Бронирования"))
    builder.add(KeyboardButton(text="⚠️ Жалобы"))
    builder.add(KeyboardButton(text="💰 Финансы"))
    builder.add(KeyboardButton(text="⚙️ Настройки системы"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_admin_users_keyboard():
    """Управление пользователями"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="👥 Все пользователи"))
    builder.add(KeyboardButton(text="👑 Администраторы"))
    builder.add(KeyboardButton(text="🚫 Заблокированные"))
    builder.add(KeyboardButton(text="📈 Новички"))
    builder.add(KeyboardButton(text="🔍 Поиск пользователя"))
    builder.add(KeyboardButton(text="🔙 Админ-панель"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_admin_user_actions_keyboard(user_id):
    """Действия с пользователем"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="👑 Назначить админом",
        callback_data=f"make_admin_{user_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🚫 Заблокировать",
        callback_data=f"block_user_{user_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="✅ Разблокировать",
        callback_data=f"unblock_user_{user_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📊 Статистика",
        callback_data=f"user_stats_{user_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="✉️ Написать",
        callback_data=f"message_user_{user_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_users"
    ))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def get_admin_reports_keyboard():
    """Управление жалобами"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="⚠️ Новые жалобы"))
    builder.add(KeyboardButton(text="🔍 В процессе"))
    builder.add(KeyboardButton(text="✅ Решенные"))
    builder.add(KeyboardButton(text="❌ Отклоненные"))
    builder.add(KeyboardButton(text="🔙 Админ-панель"))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_admin_report_actions_keyboard(report_id):
    """Действия с жалобой"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Решено",
        callback_data=f"resolve_report_{report_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отклонено",
        callback_data=f"reject_report_{report_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔍 В процессе",
        callback_data=f"investigate_report_{report_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="✉️ Ответить",
        callback_data=f"reply_report_{report_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_reports"
    ))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_admin_finance_keyboard():
    """Финансовое меню"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="💰 Общая статистика"))
    builder.add(KeyboardButton(text="📈 Доходы по дням"))
    builder.add(KeyboardButton(text="👥 Доходы по пользователям"))
    builder.add(KeyboardButton(text="🏠 Доходы по местам"))
    builder.add(KeyboardButton(text="💳 Транзакции"))
    builder.add(KeyboardButton(text="🔙 Админ-панель"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_admin_settings_keyboard():
    """Настройки системы"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="⚙️ Общие настройки"))
    builder.add(KeyboardButton(text="💰 Комиссия"))
    builder.add(KeyboardButton(text="⏰ Время автоотмены"))
    builder.add(KeyboardButton(text="📢 Настройки уведомлений"))
    builder.add(KeyboardButton(text="📊 Резервная копия"))
    builder.add(KeyboardButton(text="🔙 Админ-панель"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

# ==================== ПОИСК МЕСТ ====================

def get_search_filters_keyboard():
    """Фильтры поиска"""
    builder = ReplyKeyboardBuilder()
    
    builder.add(KeyboardButton(text="📍 По адресу"))
    builder.add(KeyboardButton(text="💰 По цене"))
    builder.add(KeyboardButton(text="⏰ По времени"))
    builder.add(KeyboardButton(text="⭐ По рейтингу"))
    builder.add(KeyboardButton(text="🔧 С фильтрами"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_search_results_keyboard(spots):
    """Результаты поиска мест"""
    builder = InlineKeyboardBuilder()
    
    for spot in spots[:10]:  # Ограничиваем 10 результатами
        builder.add(InlineKeyboardButton(
            text=f"🏠 {spot['spot_number']} - {spot['price_per_hour']}₽/час",
            callback_data=f"view_spot_{spot['id']}"
        ))
    
    builder.adjust(1)
    return builder.as_markup()

def get_spot_view_keyboard(spot_id, is_available=True):
    """Просмотр места"""
    builder = InlineKeyboardBuilder()
    
    if is_available:
        builder.add(InlineKeyboardButton(
            text="✅ Забронировать",
            callback_data=f"book_spot_{spot_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="⭐ Отзывы",
        callback_data=f"spot_reviews_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📞 Связаться",
        callback_data=f"contact_owner_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📍 На карте",
        callback_data=f"spot_map_{spot_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к поиску",
        callback_data="back_to_search"
    ))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

# ==================== ВРЕМЯ БРОНИРОВАНИЯ ====================

def get_booking_time_keyboard():
    """Выбор времени бронирования"""
    builder = InlineKeyboardBuilder()
    
    # Ближайшие часы
    import datetime
    now = datetime.datetime.now()
    
    for i in range(1, 7):
        hour = now + datetime.timedelta(hours=i)
        builder.add(InlineKeyboardButton(
            text=f"⏰ {hour.strftime('%H:%M')}",
            callback_data=f"book_time_{hour.strftime('%H:%M')}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="📅 Выбрать дату и время",
        callback_data="select_datetime"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_spot"
    ))
    
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()

def get_booking_duration_keyboard():
    """Выбор продолжительности"""
    builder = InlineKeyboardBuilder()
    
    durations = [
        ("1 час", 1),
        ("2 часа", 2),
        ("3 часа", 3),
        ("4 часа", 4),
        ("6 часов", 6),
        ("12 часов", 12),
        ("1 день", 24),
        ("2 дня", 48),
        ("Неделя", 168)
    ]
    
    for text, hours in durations:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"book_duration_{hours}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Указать свои часы",
        callback_data="custom_duration"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_time"
    ))
    
    builder.adjust(3, 3, 3, 1, 1)
    return builder.as_markup()

# ==================== ОПЛАТА ====================

def get_payment_methods_keyboard():
    """Выбор способа оплаты"""
    builder = InlineKeyboardBuilder()
    
    methods = [
        ("💳 Карта", "card"),
        ("🏦 Перевод", "transfer"),
        ("💰 Баланс", "balance"),
        ("📱 Qiwi", "qiwi"),
        ("💵 Наличные", "cash")
    ]
    
    for text, method in methods:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"pay_method_{method}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Отменить",
        callback_data="cancel_payment"
    ))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_payment_confirmation_keyboard(booking_id):
    """Подтверждение оплаты"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Оплачено",
        callback_data=f"confirm_payment_{booking_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена оплаты",
        callback_data=f"cancel_payment_{booking_id}"
    ))
    
    builder.adjust(2)
    return builder.as_markup()

# ==================== КОНТАКТЫ ====================

def get_contact_keyboard(phone=None):
    """Кнопка контакта"""
    builder = ReplyKeyboardBuilder()
    
    if phone:
        builder.add(KeyboardButton(
            text="📞 Позвонить",
            request_contact=True
        ))
    
    builder.add(KeyboardButton(text="✏️ Написать сообщение"))
    builder.add(KeyboardButton(text="🔙 Назад"))
    
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

# ==================== ДАТА И ВРЕМЯ ====================

def get_calendar_keyboard(year=None, month=None):
    """Календарь для выбора даты"""
    import calendar
    from datetime import datetime
    
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    cal = calendar.monthcalendar(year, month)
    builder = InlineKeyboardBuilder()
    
    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in week_days:
        builder.add(InlineKeyboardButton(
            text=day,
            callback_data="ignore"
        ))
    
    # Дни месяца
    today = datetime.now().date()
    for week in cal:
        for day in week:
            if day == 0:
                builder.add(InlineKeyboardButton(
                    text=" ",
                    callback_data="ignore"
                ))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                if datetime(year, month, day).date() < today:
                    builder.add(InlineKeyboardButton(
                        text=f"❌{day}",
                        callback_data="ignore"
                    ))
                else:
                    builder.add(InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"select_date_{date_str}"
                    ))
    
    # Навигация
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    builder.add(InlineKeyboardButton(
        text="◀️",
        callback_data=f"calendar_{prev_year}_{prev_month}"
    ))
    builder.add(InlineKeyboardButton(
        text=f"{calendar.month_name[month]} {year}",
        callback_data="ignore"
    ))
    builder.add(InlineKeyboardButton(
        text="▶️",
        callback_data=f"calendar_{next_year}_{next_month}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_booking"
    ))
    
    builder.adjust(7, 7, 7, 7, 7, 7, 3, 1)
    return builder.as_markup()

def get_time_keyboard():
    """Выбор времени"""
    builder = InlineKeyboardBuilder()
    
    times = []
    for hour in range(0, 24):
        for minute in [0, 15, 30, 45]:
            times.append(f"{hour:02d}:{minute:02d}")
    
    for time_str in times[:48]:  # Первые 48 вариантов (первые 12 часов)
        builder.add(InlineKeyboardButton(
            text=time_str,
            callback_data=f"select_time_{time_str}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад к дате",
        callback_data="back_to_calendar"
    ))
    
    builder.adjust(4, 4, 4, 4, 4, 4, 4, 4, 1)
    return builder.as_markup()

# ==================== РЕЙТИНГ ====================

def get_rating_keyboard():
    """Выбор рейтинга"""
    builder = InlineKeyboardBuilder()
    
    for i in range(1, 6):
        stars = "⭐" * i
        builder.add(InlineKeyboardButton(
            text=stars,
            callback_data=f"rate_{i}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_booking"
    ))
    
    builder.adjust(5, 1)
    return builder.as_markup()