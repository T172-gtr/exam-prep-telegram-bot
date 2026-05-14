"""
Plan selection and confirmation handlers.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import PlanStates
from bot.keyboards import confirm_plan_kb, plan_variants_kb, main_menu_kb
from db.service import (
    get_plan_template, get_plan_variants, create_user_plan,
    update_user_profile,
)

router = Router()


@router.callback_query(PlanStates.show_variants, F.data.startswith("plan_select:"))
async def cb_plan_select(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    template_id = int(call.data.split(":")[1])
    template    = await get_plan_template(session, template_id)

    await state.update_data(selected_template_id=template_id)
    await state.set_state(PlanStates.confirm_plan)

    text = (
        f"📋 <b>{template.title}</b>\n\n"
        f"{template.description}\n\n"
        f"⏳ Длительность: <b>{template.total_days} дней</b>\n"
        f"📅 Старт: сегодня\n\n"
        "Подтвердить выбор?"
    )
    await call.message.edit_text(text, reply_markup=confirm_plan_kb(template_id), parse_mode="HTML")
    await call.answer()


@router.callback_query(PlanStates.confirm_plan, F.data == "plan_back")
async def cb_plan_back(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.set_state(PlanStates.show_variants)
    templates = await get_plan_variants(
        session,
        subject_id    = data["subject_id"],
        target_level  = data["target_level"],
        daily_minutes = data["daily_minutes"],
    )
    await call.message.edit_text(
        "Выбери вариант плана:",
        reply_markup=plan_variants_kb(templates),
    )
    await call.answer()


@router.callback_query(PlanStates.confirm_plan, F.data.startswith("plan_confirm:"))
async def cb_plan_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    template_id = int(call.data.split(":")[1])
    template    = await get_plan_template(session, template_id)

    await create_user_plan(session, user_id=call.from_user.id, template_id=template_id)
    await update_user_profile(session, call.from_user.id, onboarded=True)

    await state.clear()
    await call.message.edit_text(
        f"🎉 Отлично! План <b>«{template.title}»</b> активирован.\n\n"
        "Каждый день я буду присылать тебе задания. "
        "Используй /today чтобы получить задание прямо сейчас!",
        parse_mode="HTML",
    )
    await call.message.answer(
        "Главное меню:",
        reply_markup=main_menu_kb(),
    )
    await call.answer()
