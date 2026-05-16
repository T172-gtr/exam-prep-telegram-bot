"""
/start handler — registration + приветствие + главное меню.
Онбординг запускается через команду /setup или inline-меню.
"""
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import main_menu_kb
from db.service import get_or_create_user

router = Router()


WELCOME_TEXT_NEW = (
    "👋 Привет, <b>{name}</b>!\n\n"
    "Я — <b>ExamBot</b>, твой помощник в подготовке к ОГЭ/ЕГЭ/МЦКО и диагностикам.\n\n"
    "С чего начать:\n"
    "• Нажми <b>📋 Меню</b> — там все разделы подготовки\n"
    "• Или введи /setup для быстрой настройки с нуля\n\n"
    "Используй кнопки внизу для навигации."
)

WELCOME_TEXT_RETURNING = (
    "👋 С возвращением, <b>{name}</b>!\n\n"
    "Нажми <b>📋 Меню</b> чтобы продолжить подготовку."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    user = await get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    text = (WELCOME_TEXT_RETURNING if user.onboarded else WELCOME_TEXT_NEW).format(
        name=message.from_user.first_name or "друг",
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")
