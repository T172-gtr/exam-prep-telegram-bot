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
from db.models import User, Task, UserProgress, Subject, ExamType
from db.service import get_subject

router = Router()
router.message.filter(AdminFilter())


# ── /admin — stats overview ───────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar()
    task_count = (await session.execute(select(func.count()).select_from(Task))).scalar()
    prog_count = (await session.execute(select(func.count()).select_from(UserProgress))).scalar()

    await message.answer(
        "🔧 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: {user_count}\n"
        f"📝 Заданий в базе: {task_count}\n"
        f"📊 Выполнений заданий: {prog_count}\n\n"
        "Команды:\n"
        "/admin_add_task — добавить задание\n"
        "/admin_stats — подробная статистика",
        parse_mode="HTML",
    )


# ── /admin_stats ──────────────────────────────────────────────

@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message, session: AsyncSession) -> None:
    rows = (await session.execute(
        select(Subject.name, func.count(Task.id))
        .join(Task, Task.subject_id == Subject.id)
        .group_by(Subject.id)
        .order_by(func.count(Task.id).desc())
        .limit(15)
    )).all()

    lines = ["📊 <b>Задания по предметам:</b>"]
    for name, cnt in rows:
        lines.append(f"  • {name}: {cnt}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /admin_add_task — FSM ─────────────────────────────────────

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
    await message.answer("Введи ответ (или отправь '-' если нет):")


@router.message(AdminStates.wait_task_answer)
async def admin_task_answer(message: Message, state: FSMContext) -> None:
    ans = message.text.strip()
    await state.update_data(answer=None if ans == "-" else ans)
    await state.set_state(AdminStates.wait_task_hint)
    await message.answer("Введи подсказку (или отправь '-' если нет):")


@router.message(AdminStates.wait_task_hint)
async def admin_task_hint(message: Message, state: FSMContext) -> None:
    hint = message.text.strip()
    await state.update_data(hint=None if hint == "-" else hint)
    await state.set_state(AdminStates.wait_task_confirm)

    data = await state.get_data()
    preview = (
        f"📝 Новое задание:\n"
        f"Предмет: {data['subject_name']} (ID {data['subject_id']})\n"
        f"Уровень: {data['target_level']}\n"
        f"Заголовок: {data['title']}\n"
        f"Условие: {data['body']}\n"
        f"Ответ: {data.get('answer') or '—'}\n"
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
    from db.models import Task
    task = Task(
        subject_id   = data["subject_id"],
        target_level = data["target_level"],
        title        = data["title"],
        body         = data["body"],
        answer       = data.get("answer"),
        hint         = data.get("hint"),
        tags         = f"{data['target_level']}",
    )
    session.add(task)
    await session.flush()
    await state.clear()
    await message.answer(f"✅ Задание #{task.id} добавлено в базу.")
