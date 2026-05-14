from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# Тексты кнопок главного меню — используются в фильтрах F.text
MENU_SETUP     = "🎯 Настроить подготовку"
MENU_SUBJECTS  = "📚 Мои предметы"
MENU_SCHEDULE  = "📅 Рассылка"
MENU_PROGRESS  = "📈 Прогресс"
MENU_TODAY     = "📝 Задание сейчас"
MENU_SUBSCRIBE = "💳 Подписка"
MENU_HELP      = "ℹ️ Помощь"


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Главное reply-меню. Компактная сетка из 4 рядов."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=MENU_SETUP))
    builder.row(
        KeyboardButton(text=MENU_SUBJECTS),
        KeyboardButton(text=MENU_TODAY),
    )
    builder.row(
        KeyboardButton(text=MENU_SCHEDULE),
        KeyboardButton(text=MENU_PROGRESS),
    )
    builder.row(
        KeyboardButton(text=MENU_SUBSCRIBE),
        KeyboardButton(text=MENU_HELP),
    )
    return builder.as_markup(resize_keyboard=True)


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
