"""
Onboarding FSM handlers: grade → exam → subjects (multi) → per-subject plan.

Жёсткие правила:
- В одном «наборе подготовки» все предметы относятся к одному классу и
  одному типу экзамена.
- Один предмет нельзя добавить дважды.
- Сменить класс/экзамен можно только через явный сброс
  («Настроить подготовку» заново → старые предметы и планы очищаются).
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import OnboardingStates, PlanStates
from bot.keyboards import (
    grades_kb, exams_kb, subjects_multi_kb, levels_kb, minutes_kb,
    main_menu_kb, MENU_SETUP,
)
from db.service import (
    get_all_grades, get_exams_for_grade, get_subjects_for_exam,
    get_grade, get_exam_type, get_subject,
    update_user_profile, clear_user_subjects, add_user_subject,
    deactivate_all_user_plans, get_user_subjects,
)

router = Router()

LEVEL_DESCRIPTIONS = {
    "low":    ("🔵 Низкий",       "базовые задания, минимальный проходной балл"),
    "medium": ("🟢 Средний",      "задания 1–2 части, уверенная сдача"),
    "high":   ("🟠 Высокий",      "сложные задания, высокий балл"),
    "max":    ("🔴 Максимальный", "полное погружение, максимум баллов"),
}


# ─────────────────────────────────────────────────────────────
# Вход в онбординг: из меню или /setup
# ─────────────────────────────────────────────────────────────

@router.message(Command("setup"))
@router.message(F.text == MENU_SETUP)
async def start_setup(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Полный сброс предыдущей подготовки и старт онбординга заново."""
    await state.clear()
    await clear_user_subjects(session, message.from_user.id)
    await deactivate_all_user_plans(session, message.from_user.id)
    await update_user_profile(
        session, message.from_user.id,
        grade_id=None, exam_type_id=None, subject_id=None,
        target_level=None, daily_minutes=None,
    )

    grades = await get_all_grades(session)
    await state.set_state(OnboardingStates.choose_grade)
    await message.answer(
        "🎯 <b>Настройка подготовки</b>\n\n"
        "Шаг 1 из 4. Выбери класс:",
        reply_markup=grades_kb(grades),
        parse_mode="HTML",
    )


# ── Step 1: grade chosen ─────────────────────────────────────

@router.callback_query(OnboardingStates.choose_grade, F.data.startswith("grade:"))
async def cb_grade(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    grade_id = int(call.data.split(":")[1])
    grade    = await get_grade(session, grade_id)
    await state.update_data(grade_id=grade_id)
    await update_user_profile(session, call.from_user.id, grade_id=grade_id)

    exams = await get_exams_for_grade(session, grade_id)
    await state.set_state(OnboardingStates.choose_exam)
    await call.message.edit_text(
        f"✅ Выбран: <b>{grade.label}</b>\n\n"
        "Шаг 2 из 4. Выбери тип экзамена:",
        reply_markup=exams_kb(exams),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 2: exam chosen → выбор предметов ────────────────────

@router.callback_query(OnboardingStates.choose_exam, F.data.startswith("exam:"))
async def cb_exam(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    exam_id   = int(call.data.split(":")[1])
    exam_type = await get_exam_type(session, exam_id)
    await state.update_data(exam_type_id=exam_id, selected_subject_ids=[])
    await update_user_profile(session, call.from_user.id, exam_type_id=exam_id)
    await clear_user_subjects(session, call.from_user.id)

    subjects = await get_subjects_for_exam(session, exam_id)
    await state.set_state(OnboardingStates.choose_subjects)
    await call.message.edit_text(
        f"✅ Экзамен: <b>{exam_type.name}</b>\n\n"
        "Шаг 3 из 4. Выбери один или несколько предметов "
        "(нажми по предмету, чтобы добавить или убрать его). "
        "Когда закончишь — нажми <b>«✔️ Готово»</b>.",
        reply_markup=subjects_multi_kb(subjects, []),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 3a: toggle subject ──────────────────────────────────

@router.callback_query(OnboardingStates.choose_subjects, F.data.startswith("subj_toggle:"))
async def cb_subject_toggle(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    subject_id = int(call.data.split(":")[1])
    data = await state.get_data()
    selected: list[int] = list(data.get("selected_subject_ids", []))

    if subject_id in selected:
        selected.remove(subject_id)
        note = "Убрано"
    else:
        selected.append(subject_id)
        note = "Добавлено"

    await state.update_data(selected_subject_ids=selected)
    subjects = await get_subjects_for_exam(session, data["exam_type_id"])
    try:
        await call.message.edit_reply_markup(
            reply_markup=subjects_multi_kb(subjects, selected),
        )
    except Exception:
        pass
    await call.answer(note)


# ── Step 3b: reset selection ─────────────────────────────────

@router.callback_query(OnboardingStates.choose_subjects, F.data == "subj_reset")
async def cb_subject_reset(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.update_data(selected_subject_ids=[])
    subjects = await get_subjects_for_exam(session, data["exam_type_id"])
    try:
        await call.message.edit_reply_markup(
            reply_markup=subjects_multi_kb(subjects, []),
        )
    except Exception:
        pass
    await call.answer("Выбор очищен")


# ── Step 3c: done — переход к настройке планов ───────────────

@router.callback_query(OnboardingStates.choose_subjects, F.data == "subj_done")
async def cb_subjects_done(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    selected: list[int] = list(data.get("selected_subject_ids", []))
    if not selected:
        await call.answer("Выбери хотя бы один предмет", show_alert=True)
        return

    # сохраняем все выбранные предметы в БД
    await clear_user_subjects(session, call.from_user.id)
    for sid in selected:
        await add_user_subject(session, call.from_user.id, sid)

    # ставим «основной» предмет = первый выбранный (для совместимости)
    await update_user_profile(session, call.from_user.id, subject_id=selected[0])

    # сохраняем очередь предметов, которые ещё надо настроить
    await state.update_data(setup_queue=list(selected), current_subject_id=None)
    await _proceed_to_next_subject(call.message, state, session)
    await call.answer()


# ─────────────────────────────────────────────────────────────
# Per-subject plan setup
# ─────────────────────────────────────────────────────────────

async def _proceed_to_next_subject(message: Message, state: FSMContext,
                                    session: AsyncSession) -> None:
    """Берёт следующий предмет из очереди и запускает выбор уровня."""
    data = await state.get_data()
    queue: list[int] = list(data.get("setup_queue", []))
    if not queue:
        # все предметы настроены — завершение
        await state.clear()
        await update_user_profile(session, message.chat.id, onboarded=True)

        subj_rows = await get_user_subjects(session, message.chat.id)
        names = ", ".join(us.subject.name for us in subj_rows) or "—"
        await message.edit_text(
            f"🎉 Готово! Настроены планы по предметам: <b>{names}</b>.\n\n"
            "Каждый день буду присылать задания согласно настройкам рассылки "
            "(см. «📅 Рассылка»).\n\n"
            "Чтобы получить задание прямо сейчас — «📝 Задание сейчас» или /today.",
            parse_mode="HTML",
        )
        await message.answer("Главное меню:", reply_markup=main_menu_kb())
        return

    current = queue.pop(0)
    subj = await get_subject(session, current)
    await state.update_data(
        setup_queue=queue,
        current_subject_id=current,
        subject_id=current,        # для совместимости с дальнейшими шагами
    )

    lines = [
        f"🧩 Настройка предмета <b>{subj.name}</b>",
        "",
        "Выбери целевой уровень:",
        "",
    ]
    for code, (label, desc) in LEVEL_DESCRIPTIONS.items():
        lines.append(f"{label} — {desc}")

    await state.set_state(OnboardingStates.choose_level)
    await message.edit_text(
        "\n".join(lines),
        reply_markup=levels_kb(),
        parse_mode="HTML",
    )


# ── Step 4: level chosen ─────────────────────────────────────

@router.callback_query(OnboardingStates.choose_level, F.data.startswith("level:"))
async def cb_level(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    level = call.data.split(":")[1]
    label, desc = LEVEL_DESCRIPTIONS[level]
    await state.update_data(target_level=level)
    await update_user_profile(session, call.from_user.id, target_level=level)

    await state.set_state(OnboardingStates.choose_minutes)
    await call.message.edit_text(
        f"✅ Уровень: <b>{label}</b> — {desc}\n\n"
        "Сколько минут в день готов уделять подготовке?",
        reply_markup=minutes_kb(),
        parse_mode="HTML",
    )
    await call.answer()


# ── Step 5: minutes chosen → варианты плана ──────────────────

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
        subject_id    = data["current_subject_id"],
        target_level  = data["target_level"],
        daily_minutes = minutes,
    )

    if not templates:
        await call.message.edit_text(
            "⚠️ Шаблоны планов не найдены для заданных параметров. "
            "Попробуй «🎯 Настроить подготовку» ещё раз."
        )
        await state.clear()
        await call.answer()
        return

    await state.set_state(PlanStates.show_variants)
    await call.message.edit_text(
        f"⏱ Отлично! <b>{minutes} мин/день</b>.\n\n"
        "Подобраны варианты плана. Выбери один:",
        reply_markup=plan_variants_kb(templates),
        parse_mode="HTML",
    )
    await call.answer()


# Эта функция нужна plan.py — экспорт.
proceed_to_next_subject = _proceed_to_next_subject
