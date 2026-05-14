"""
Onboarding FSM handlers: grade → exam → subject → level → minutes.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import OnboardingStates, PlanStates
from bot.keyboards import (
    exams_kb, subjects_kb, levels_kb, minutes_kb,
)
from db.service import (
    get_exams_for_grade, get_subjects_for_exam,
    get_grade, get_exam_type,
    update_user_profile,
)

router = Router()

LEVEL_DESCRIPTIONS = {
    "low":    ("🔵 Низкий",       "базовые задания, минимальный проходной балл"),
    "medium": ("🟢 Средний",      "задания 1–2 части, уверенная сдача"),
    "high":   ("🟠 Высокий",      "сложные задания, высокий балл"),
    "max":    ("🔴 Максимальный", "полное погружение, максимум баллов"),
}


# ── Step 1: grade chosen ──────────────────────────────────────

@router.callback_query(OnboardingStates.choose_grade, F.data.startswith("grade:"))
async def cb_grade(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    grade_id = int(call.data.split(":")[1])
    grade    = await get_grade(session, grade_id)
    await state.update_data(grade_id=grade_id)
    await update_user_profile(session, call.from_user.id, grade_id=grade_id)

    exams = await get_exams_for_grade(session, grade_id)
    await state.set_state(OnboardingStates.choose_exam)
    await call.message.edit_text(
        f"✅ Выбран: <b>{grade.label}</b>\n\nТеперь выбери тип экзамена:",
        reply_markup=exams_kb(exams),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 2: exam chosen ───────────────────────────────────────

@router.callback_query(OnboardingStates.choose_exam, F.data.startswith("exam:"))
async def cb_exam(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    exam_id   = int(call.data.split(":")[1])
    exam_type = await get_exam_type(session, exam_id)
    await state.update_data(exam_type_id=exam_id)
    await update_user_profile(session, call.from_user.id, exam_type_id=exam_id)

    subjects = await get_subjects_for_exam(session, exam_id)
    await state.set_state(OnboardingStates.choose_subject)
    await call.message.edit_text(
        f"✅ Выбран: <b>{exam_type.name}</b>\n\nВыбери предмет:",
        reply_markup=subjects_kb(subjects),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 3: subject chosen ────────────────────────────────────

@router.callback_query(OnboardingStates.choose_subject, F.data.startswith("subject:"))
async def cb_subject(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    subject_id = int(call.data.split(":")[1])
    from db.service import get_subject
    subject = await get_subject(session, subject_id)
    await state.update_data(subject_id=subject_id)
    await update_user_profile(session, call.from_user.id, subject_id=subject_id)

    lines = ["✅ Выбран предмет: <b>{}</b>\n\nВыбери целевой уровень:".format(subject.name), ""]
    for code, (label, desc) in LEVEL_DESCRIPTIONS.items():
        lines.append(f"{label} — {desc}")

    await state.set_state(OnboardingStates.choose_level)
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=levels_kb(),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 4: level chosen ──────────────────────────────────────

@router.callback_query(OnboardingStates.choose_level, F.data.startswith("level:"))
async def cb_level(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    level = call.data.split(":")[1]
    label, desc = LEVEL_DESCRIPTIONS[level]
    await state.update_data(target_level=level)
    await update_user_profile(session, call.from_user.id, target_level=level)

    await state.set_state(OnboardingStates.choose_minutes)
    await call.message.edit_text(
        f"✅ Уровень: <b>{label}</b> — {desc}\n\n"
        "Сколько минут в день ты готов уделять подготовке?",
        reply_markup=minutes_kb(),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 5: minutes chosen → generate plans ───────────────────

@router.callback_query(OnboardingStates.choose_minutes, F.data.startswith("minutes:"))
async def cb_minutes(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    minutes = int(call.data.split(":")[1])
    await state.update_data(daily_minutes=minutes)
    await update_user_profile(session, call.from_user.id, daily_minutes=minutes)

    data = await state.get_data()
    from db.service import get_plan_variants
    from bot.keyboards import plan_variants_kb

    templates = await get_plan_variants(
        session,
        subject_id    = data["subject_id"],
        target_level  = data["target_level"],
        daily_minutes = minutes,
    )

    if not templates:
        await call.message.edit_text(
            "⚠️ Шаблоны планов не найдены для заданных параметров. "
            "Попробуй /start ещё раз."
        )
        await state.clear()
        await call.answer()
        return

    await state.set_state(PlanStates.show_variants)
    await call.message.edit_text(
        f"⏱ Отлично! <b>{minutes} мин/день</b>.\n\n"
        "Для тебя подобраны варианты плана. Выбери один из них:",
        reply_markup=plan_variants_kb(templates),
        parse_mode="HTML",
    )
    await call.answer()
