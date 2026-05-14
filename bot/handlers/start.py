"""
/start handler — registration + приветствие + главное меню.
Онбординг запускается через кнопку «🎯 Настроить подготовку».
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
    "• 🎯 <b>Настроить подготовку</b> — выбрать класс, экзамен и предметы\n"
    "• 📅 <b>Рассылка</b> — настроить, когда присылать задания\n"
    "• 📝 <b>Задание сейчас</b> — получить задачу прямо сейчас\n\n"
    "Используй меню ниже или команду /menu."
)

WELCOME_TEXT_RETURNING = (
    "👋 С возвращением, <b>{name}</b>!\n\n"
    "Выбери действие в меню или вызови /menu."
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


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📋 Главное меню. Выбери действие:",
        reply_markup=main_menu_kb(),
    )
