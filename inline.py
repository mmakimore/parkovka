from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==================== ПАГИНАЦИЯ ====================

def get_pagination_keyboard(page: int, total_pages: int, prefix: str):
    """Клавиатура пагинации"""
    builder = InlineKeyboardBuilder()
    
    if page > 1:
        builder.add(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"{prefix}_page_{page-1}"
        ))
    
    builder.add(InlineKeyboardButton(
        text=f"{page}/{total_pages}",
        callback_data="ignore"
    ))
    
    if page < total_pages:
        builder.add(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"{prefix}_page_{page+1}"
        ))
    
    builder.adjust(3)
    return builder.as_markup()

# ==================== БЫСТРЫЕ ДЕЙСТВИЯ ====================

def get_quick_actions_keyboard(user_id=None):
    """Быстрые действия"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🚗 Найти место",
        callback_data="quick_search"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 Мои брони",
        callback_data="quick_bookings"
    ))
    builder.add(InlineKeyboardButton(
        text="🏠 Мои места",
        callback_data="quick_spots"
    ))
    
    if user_id:
        builder.add(InlineKeyboardButton(
            text="👤 Профиль",
            callback_data=f"quick_profile_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="📢 Уведомления",
            callback_data=f"quick_notifications_{user_id}"
        ))
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()

# ==================== ПОДТВЕРЖДЕНИЯ ====================

def get_confirmation_keyboard(action: str, item_id: int):
    """Подтверждение действия"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Подтвердить",
        callback_data=f"confirm_{action}_{item_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"cancel_{action}_{item_id}"
    ))
    
    builder.adjust(2)
    return builder.as_markup()

# ==================== ВЫБОР ДНЯ НЕДЕЛИ ====================

def get_weekdays_keyboard(selected_days=None):
    """Выбор дней недели"""
    if selected_days is None:
        selected_days = []
    
    weekdays = [
        ("Понедельник", 0),
        ("Вторник", 1),
        ("Среда", 2),
        ("Четверг", 3),
        ("Пятница", 4),
        ("Суббота", 5),
        ("Воскресенье", 6)
    ]
    
    builder = InlineKeyboardBuilder()
    
    for name, day in weekdays:
        prefix = "✅" if day in selected_days else "⬜"
        builder.add(InlineKeyboardButton(
            text=f"{prefix} {name}",
            callback_data=f"toggle_day_{day}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="✅ Все дни",
        callback_data="select_all_days"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Очистить",
        callback_data="clear_all_days"
    ))
    builder.add(InlineKeyboardButton(
        text="💾 Сохранить",
        callback_data="save_days"
    ))
    
    builder.adjust(1, 1, 1, 1, 1, 1, 1, 2, 1)
    return builder.as_markup()

# ==================== ВЫБОР ЧАСОВ ====================

def get_hours_keyboard():
    """Выбор часов работы"""
    builder = InlineKeyboardBuilder()
    
    # Стандартные временные слоты
    slots = [
        ("Круглосуточно", "00:00-23:59"),
        ("Ночь (22:00-08:00)", "22:00-08:00"),
        ("Утро (08:00-14:00)", "08:00-14:00"),
        ("День (14:00-20:00)", "14:00-20:00"),
        ("Вечер (20:00-02:00)", "20:00-02:00"),
    ]
    
    for text, time_range in slots:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"select_hours_{time_range}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Свое время",
        callback_data="custom_hours"
    ))
    
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

# ==================== ФИЛЬТРЫ ПОИСКА ====================

def get_search_filters_inline():
    """Фильтры поиска (инлайн)"""
    builder = InlineKeyboardBuilder()
    
    filters = [
        ("💰 До 100₽/час", "price_100"),
        ("💰 100-200₽/час", "price_200"),
        ("💰 200-500₽/час", "price_500"),
        ("💰 500+₽/час", "price_500+"),
        ("⭐ 4.5+ рейтинг", "rating_4.5"),
        ("⭐ 4.0+ рейтинг", "rating_4.0"),
        ("🏢 Крытая", "covered"),
        ("🎥 CCTV", "cctv"),
        ("💡 Освещение", "lighting"),
        ("🔌 Розетка", "electricity"),
    ]
    
    for text, filter_key in filters:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"filter_{filter_key}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="✅ Применить фильтры",
        callback_data="apply_filters"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Сбросить",
        callback_data="clear_filters"
    ))
    
    builder.adjust(2, 2, 2, 2, 2, 2)
    return builder.as_markup()

# ==================== СТАТУСЫ БРОНИРОВАНИЙ ====================

def get_booking_status_filter():
    """Фильтр по статусу бронирований"""
    builder = InlineKeyboardBuilder()
    
    statuses = [
        ("⏳ Ожидание", "pending"),
        ("✅ Подтверждено", "confirmed"),
        ("🚗 Активно", "active"),
        ("✅ Завершено", "completed"),
        ("❌ Отменено", "cancelled"),
        ("💳 Ожидает оплаты", "awaiting_payment"),
    ]
    
    for text, status in statuses:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"filter_status_{status}"
        ))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup()

# ==================== ТИПЫ ЖАЛОБ ====================

def get_report_types_keyboard():
    """Типы жалоб"""
    builder = InlineKeyboardBuilder()
    
    report_types = [
        ("🚗 Проблема с местом", "spot_issue"),
        ("👤 Проблема с пользователем", "user_issue"),
        ("💳 Проблема с оплатой", "payment_issue"),
        ("📅 Проблема с бронированием", "booking_issue"),
        ("📞 Не отвечает", "no_response"),
        ("🚫 Мошенничество", "fraud"),
        ("⚖️ Другое", "other"),
    ]
    
    for text, report_type in report_types:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"report_type_{report_type}"
        ))
    
    builder.adjust(1, 1, 1, 1, 1, 1, 1)
    return builder.as_markup()

# ==================== УВЕДОМЛЕНИЯ ====================

def get_notification_settings_keyboard():
    """Настройки уведомлений"""
    builder = InlineKeyboardBuilder()
    
    settings = [
        ("📅 Новые бронирования", "notify_bookings"),
        ("💰 Оплаты", "notify_payments"),
        ("⭐ Отзывы", "notify_reviews"),
        ("⚠️ Жалобы", "notify_reports"),
        ("📢 Системные", "notify_system"),
        ("📱 Telegram", "notify_telegram"),
        ("📧 Email", "notify_email"),
        ("🔔 SMS", "notify_sms"),
    ]
    
    for text, setting in settings:
        builder.add(InlineKeyboardButton(
            text=f"✅ {text}",
            callback_data=f"toggle_{setting}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="💾 Сохранить",
        callback_data="save_notification_settings"
    ))
    
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()

# ==================== ЭКСТРЕННЫЕ ДЕЙСТВИЯ ====================

def get_emergency_keyboard(booking_id=None):
    """Экстренные действия"""
    builder = InlineKeyboardBuilder()
    
    if booking_id:
        builder.add(InlineKeyboardButton(
            text="🚨 Проблема на месте",
            callback_data=f"emergency_spot_{booking_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="📞 Срочно связаться",
            callback_data=f"emergency_call_{booking_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="⚠️ Пожаловаться",
        callback_data="emergency_report"
    ))
    builder.add(InlineKeyboardButton(
        text="🏥 Вызов служб",
        callback_data="emergency_services"
    ))
    builder.add(InlineKeyboardButton(
        text="🆘 Техподдержка",
        callback_data="emergency_support"
    ))
    
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()

# ==================== ШАРЕНИЕ ====================

def get_share_keyboard(item_type: str, item_id: int):
    """Поделиться"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📱 Поделиться в Telegram",
        switch_inline_query=f"share_{item_type}_{item_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔗 Скопировать ссылку",
        callback_data=f"copy_link_{item_type}_{item_id}"
    ))
    
    return builder.as_markup()

# ==================== ПРОМО ====================

def get_promo_keyboard():
    """Промо-акции"""
    builder = InlineKeyboardBuilder()
    
    promos = [
        ("🎁 Первое бронирование -20%", "promo_first"),
        ("👥 Приведи друга +100₽", "promo_referral"),
        ("⭐ 5 отзывов +500₽", "promo_reviews"),
        ("📅 Бронируй на неделю -15%", "promo_week"),
        ("🎉 Сезонная скидка", "promo_season"),
    ]
    
    for text, promo in promos:
        builder.add(InlineKeyboardButton(
            text=text,
            callback_data=f"apply_promo_{promo}"
        ))
    
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()