from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# Тексты кнопок нижней панели
MENU_MAIN      = "📋 Меню"
MENU_SUBSCRIBE = "💳 Управление подпиской"
MENU_SUPPORT   = "🆘 Поддержка"

# Тексты кнопок внутри inline-подменю (используются в фильтрах F.text / callback)
MENU_SETUP     = "🎯 Настроить подготовку"
MENU_SUBJECTS  = "📚 Мои предметы"
MENU_SCHEDULE  = "📅 Рассылка"
MENU_PROGRESS  = "📈 Прогресс"
MENU_TODAY     = "📝 Задание сейчас"
MENU_HELP      = "ℹ️ Помощь"


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Нижняя reply-панель — всего 3 кнопки."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=MENU_MAIN))
    builder.row(
        KeyboardButton(text=MENU_SUBSCRIBE),
        KeyboardButton(text=MENU_SUPPORT),
    )
    return builder.as_markup(resize_keyboard=True)


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
