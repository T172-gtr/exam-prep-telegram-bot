"""
Admin-only commands: /admin, add task via FSM, stats.
Protected by AdminFilter.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import AdminFilter
from bot.states import AdminStates
from db.models import User, Task, Subject, ExamType
from db.service import (
    get_subject, get_subscription_stats, get_subject_distribution,
)

router = Router()
router.message.filter(AdminFilter())


PLAN_LABELS = {
    "premium_month": "Premium · месяц",
    "premium_year":  "Premium · год",
    "free":          "Free",
}


# ── /admin — обзор без выполненных заданий, с подписками ─────

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    task_count = (await session.execute(select(func.count()).select_from(Task))).scalar() or 0
    stats = await get_subscription_stats(session)

    by_plan_lines = []
    for code, n in stats["by_plan"].items():
        by_plan_lines.append(f"  · {PLAN_LABELS.get(code, code)}: {n}")
    by_plan_block = "\n".join(by_plan_lines) if by_plan_lines else "  · нет активных Premium"

    await message.answer(
        "🔧 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"📝 Заданий в банке: <b>{task_count}</b>\n\n"
        f"💎 <b>Подписки</b>\n"
        f"Активных Premium: <b>{stats['active_premium']}</b>\n"
        f"{by_plan_block}\n\n"
        f"💳 <b>Платежи</b>\n"
        f"Всего записей: {stats['payments_total']}\n"
        f"Успешных: {stats['payments_ok']}\n"
        f"Сумма успешных, ₽: <b>{stats['payments_amount']}</b>\n\n"
        "Команды:\n"
        "/admin_add_task — добавить задание\n"
        "/admin_stats — статистика по предметам",
        parse_mode="HTML",
    )


# ── /admin_stats — распределение пользователей по предметам ──

@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message, session: AsyncSession) -> None:
    rows = await get_subject_distribution(session)

    if not rows:
        await message.answer("Пока нет данных по выбранным предметам.")
        return

    lines = ["📊 <b>Распределение пользователей по предметам:</b>", ""]
    for grade_label, exam_name, subj_name, cnt in rows:
        lines.append(f"• {grade_label} · {exam_name} · <b>{subj_name}</b> — {cnt} польз.")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /admin_add_task — FSM ────────────────────────────────────

@router.message(Command("admin_add_task"))
async def cmd_admin_add_task_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    rows = (await session.execute(
        select(Subject.id, Subject.name, ExamType.name)
        .join(ExamType, Subject.exam_type_id == ExamType.id)
        .order_by(ExamType.name, Subject.name)
    )).all()

    lines = ["Введи ID предмета (число):\n"]
    for sid, sname, ename in rows:
        lines.append(f"  {sid}: [{ename}] {sname}")

    await state.set_state(AdminStates.wait_task_subject)
    await message.answer("\n".join(lines))


@router.message(AdminStates.wait_task_subject)
async def admin_task_subject(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        subject_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введи числовой ID предмета.")
        return
    subject = await get_subject(session, subject_id)
    if subject is None:
        await message.answer("Предмет не найден. Попробуй ещё раз.")
        return
    await state.update_data(subject_id=subject_id, subject_name=subject.name)
    await state.set_state(AdminStates.wait_task_level)
    await message.answer(f"Предмет: {subject.name}\nВведи уровень: low / medium / high / max")


@router.message(AdminStates.wait_task_level)
async def admin_task_level(message: Message, state: FSMContext) -> None:
    level = message.text.strip().lower()
    if level not in ("low", "medium", "high", "max"):
        await message.answer("Допустимые значения: low, medium, high, max")
        return
    await state.update_data(target_level=level)
    await state.set_state(AdminStates.wait_task_title)
    await message.answer("Введи заголовок задания:")


@router.message(AdminStates.wait_task_title)
async def admin_task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminStates.wait_task_body)
    await message.answer("Введи текст задания (условие):")


@router.message(AdminStates.wait_task_body)
async def admin_task_body(message: Message, state: FSMContext) -> None:
    await state.update_data(body=message.text.strip())
    await state.set_state(AdminStates.wait_task_answer)
    await message.answer(
        "Введи правильный ответ (для автопроверки).\n"
        "Можно указать несколько вариантов через | — например: 4|x=4|четыре.\n"
        "Или '-' если автопроверки не будет."
    )


@router.message(AdminStates.wait_task_answer)
async def admin_task_answer(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if raw == "-":
        await state.update_data(correct_answer=None, acceptable_answers=None)
    else:
        parts = [p.strip() for p in raw.split("|") if p.strip()]
        primary = parts[0]
        rest = "|".join(parts[1:]) if len(parts) > 1 else None
        await state.update_data(correct_answer=primary, acceptable_answers=rest)
    await state.set_state(AdminStates.wait_task_hint)
    await message.answer("Введи подсказку (или отправь '-' если нет):")


@router.message(AdminStates.wait_task_hint)
async def admin_task_hint(message: Message, state: FSMContext) -> None:
    hint = message.text.strip()
    await state.update_data(hint=None if hint == "-" else hint)
    await state.set_state(AdminStates.wait_task_confirm)

    data = await state.get_data()
    preview = (
        "📝 Новое задание:\n"
        f"Предмет: {data['subject_name']} (ID {data['subject_id']})\n"
        f"Уровень: {data['target_level']}\n"
        f"Заголовок: {data['title']}\n"
        f"Условие: {data['body']}\n"
        f"Ответ: {data.get('correct_answer') or '—'}\n"
        f"Доп. ответы: {data.get('acceptable_answers') or '—'}\n"
        f"Подсказка: {data.get('hint') or '—'}\n\n"
        "Отправь 'да' для сохранения или 'нет' для отмены."
    )
    await message.answer(preview)


@router.message(AdminStates.wait_task_confirm)
async def admin_task_confirm(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text.strip().lower() not in ("да", "yes", "y", "+"):
        await state.clear()
        await message.answer("Отменено.")
        return

    data = await state.get_data()
    task = Task(
        subject_id         = data["subject_id"],
        target_level       = data["target_level"],
        title              = data["title"],
        body               = data["body"],
        answer             = data.get("correct_answer"),  # совместимость
        correct_answer     = data.get("correct_answer"),
        acceptable_answers = data.get("acceptable_answers"),
        hint               = data.get("hint"),
        tags               = f"{data['target_level']}",
    )
    session.add(task)
    await session.flush()
    await state.clear()
    await message.answer(f"✅ Задание #{task.id} добавлено в базу.")


# ── /admin_import — импорт задач из JSON ─────────────────────

@router.message(Command("admin_import"))
async def cmd_admin_import(message: Message, session: AsyncSession) -> None:
    """Импорт задач из JSON-файла, лежащего в data/tasks_import.json.

    Структура файла описана в db/import_tasks.py.
    """
    from db.import_tasks import import_tasks_from_default_file
    try:
        added, skipped = await import_tasks_from_default_file(session)
        await message.answer(
            f"📥 Импорт завершён.\n"
            f"Добавлено: <b>{added}</b>\n"
            f"Пропущено (дубликаты/ошибки): <b>{skipped}</b>",
            parse_mode="HTML",
        )
    except FileNotFoundError as exc:
        await message.answer(f"⚠️ Файл импорта не найден: {exc}")
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"⚠️ Ошибка импорта: {exc}")
