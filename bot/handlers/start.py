"""
/start handler — registration + onboarding entry point.
"""
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import OnboardingStates
from bot.keyboards import grades_kb, main_menu_kb
from db.service import get_or_create_user, get_all_grades

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    if user.onboarded:
        await message.answer(
            f"👋 С возвращением, <b>{message.from_user.first_name}</b>!\n"
            "Используй меню или команды /today, /progress, /profile.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    await state.set_state(OnboardingStates.choose_grade)
    grades = await get_all_grades(session)
    await message.answer(
        "👋 Привет! Я — <b>ExamBot</b>, твой помощник в подготовке к экзаменам.\n\n"
        "Давай настроим твой план. Для начала — выбери свой класс:",
        reply_markup=grades_kb(grades),
        parse_mode="HTML",
    )
