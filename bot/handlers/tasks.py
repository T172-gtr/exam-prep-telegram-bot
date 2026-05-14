"""
Task delivery and answer tracking handlers.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import task_answer_kb
from db.service import (
    get_active_plan, get_next_task, get_task,
    get_or_create_subscription, record_progress,
    count_progress,
)
from config import settings

router = Router()


async def send_today_task(message: Message, session: AsyncSession) -> None:
    """Core logic — shared between /today command and scheduler."""
    plan = await get_active_plan(session, message.chat.id)
    if plan is None:
        await message.answer(
            "У тебя ещё нет активного плана. Используй /start чтобы настроить его."
        )
        return

    # Check free limit
    sub = await get_or_create_subscription(session, message.chat.id)
    is_premium = sub.is_active and sub.plan_type != "free"

    stats = await count_progress(session, message.chat.id)
    tasks_today = plan.tasks_sent_today

    if not is_premium and tasks_today >= settings.FREE_DAILY_LIMIT:
        await message.answer(
            f"🔒 Ты достиг лимита бесплатных заданий ({settings.FREE_DAILY_LIMIT}/день).\n"
            "Оформи подписку Premium чтобы получать неограниченное количество заданий: /subscribe"
        )
        return

    template = plan.template
    task = await get_next_task(
        session,
        user_id      = message.chat.id,
        subject_id   = template.subject_id,
        target_level = template.target_level,
    )

    if task is None:
        await message.answer(
            "🏆 Поздравляю! Ты выполнил все доступные задания по этому предмету.\n"
            "Скоро появятся новые задания!"
        )
        return

    # Increment counter
    plan.tasks_sent_today += 1

    text = (
        f"📚 <b>Задание</b>\n"
        f"─────────────────\n"
        f"{task.title}\n\n"
        f"{task.body}"
    )
    await message.answer(text, reply_markup=task_answer_kb(task.id), parse_mode="HTML")


@router.callback_query(F.data.startswith("task_ans:"))
async def cb_task_answer(call: CallbackQuery, session: AsyncSession) -> None:
    parts = call.data.split(":")
    task_id   = int(parts[1])
    is_correct = parts[2] == "correct"

    await record_progress(session, call.from_user.id, task_id, is_correct=is_correct)

    if is_correct:
        await call.message.edit_reply_markup()
        await call.message.answer("✅ Отлично! Задание засчитано как выполненное.")
    else:
        task = await get_task(session, task_id)
        await call.message.edit_reply_markup()
        text = "❌ Неверно.\n"
        if task and task.answer:
            text += f"\n💡 Правильный ответ: <b>{task.answer}</b>"
        if task and task.hint:
            text += f"\n📎 Подсказка: {task.hint}"
        await call.message.answer(text, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("task_hint:"))
async def cb_task_hint(call: CallbackQuery, session: AsyncSession) -> None:
    task_id = int(call.data.split(":")[1])
    task    = await get_task(session, task_id)
    if task and task.hint:
        await call.answer(f"💡 {task.hint}", show_alert=True)
    else:
        await call.answer("Подсказка недоступна.", show_alert=True)


@router.callback_query(F.data.startswith("task_reveal:"))
async def cb_task_reveal(call: CallbackQuery, session: AsyncSession) -> None:
    task_id = int(call.data.split(":")[1])
    task    = await get_task(session, task_id)
    if task and task.answer:
        await call.answer(f"Ответ: {task.answer}", show_alert=True)
        await record_progress(session, call.from_user.id, task_id, is_correct=False)
    else:
        await call.answer("Ответ недоступен.", show_alert=True)
