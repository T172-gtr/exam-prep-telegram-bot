"""
Plan selection and confirmation handlers.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import PlanStates, OnboardingStates
from bot.keyboards import (
    confirm_plan_kb, plan_variants_kb, setup_more_kb, main_menu_kb,
)
from db.service import (
    get_plan_template, get_plan_variants, create_user_plan,
    update_user_profile, get_user_subjects,
)
from bot.handlers.onboarding import proceed_to_next_subject

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
        subject_id    = data["current_subject_id"],
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

    data = await state.get_data()
    queue: list[int] = list(data.get("setup_queue", []))

    if queue:
        # есть ещё предметы — спросим, продолжить или закончить
        await state.set_state(PlanStates.setup_next)
        await call.message.edit_text(
            f"✅ План <b>«{template.title}»</b> сохранён.\n\n"
            f"Осталось настроить ещё <b>{len(queue)}</b> предмет(ов). "
            "Продолжим?",
            reply_markup=setup_more_kb(),
            parse_mode="HTML",
        )
    else:
        # последний предмет — финал
        await state.clear()
        await update_user_profile(session, call.from_user.id, onboarded=True)
        subj_rows = await get_user_subjects(session, call.from_user.id)
        names = ", ".join(us.subject.name for us in subj_rows) or "—"
        await call.message.edit_text(
            f"🎉 Готово! План <b>«{template.title}»</b> активирован.\n"
            f"Все выбранные предметы настроены: <b>{names}</b>.\n\n"
            "Используй меню или /today чтобы получить задание.",
            parse_mode="HTML",
        )
        await call.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await call.answer()


# ── Продолжить / завершить настройку ─────────────────────────

@router.callback_query(PlanStates.setup_next, F.data == "setup_next")
async def cb_setup_next(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await proceed_to_next_subject(call.message, state, session)
    await call.answer()


@router.callback_query(PlanStates.setup_next, F.data == "setup_done")
async def cb_setup_done(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await update_user_profile(session, call.from_user.id, onboarded=True)
    subj_rows = await get_user_subjects(session, call.from_user.id)
    names = ", ".join(us.subject.name for us in subj_rows) or "—"
    await call.message.edit_text(
        f"🏁 Настройка завершена.\n"
        f"Готовимся по предметам: <b>{names}</b>.",
        parse_mode="HTML",
    )
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await call.answer()
