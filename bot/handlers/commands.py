"""
General commands: /profile, /progress, /today.
Also handles reply keyboard shortcuts.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db.service import (
    get_user, get_active_plan, count_progress,
    get_grade, get_exam_type, get_subject,
    get_or_create_subscription,
)
from bot.handlers.tasks import send_today_task

router = Router()


# ── /profile ─────────────────────────────────────────────────

@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    user = await get_user(session, message.from_user.id)
    if user is None or not user.onboarded:
        await message.answer("Профиль не создан. Используй /start чтобы начать.")
        return

    grade    = await get_grade(session, user.grade_id)     if user.grade_id     else None
    exam     = await get_exam_type(session, user.exam_type_id) if user.exam_type_id else None
    subject  = await get_subject(session, user.subject_id) if user.subject_id   else None
    sub      = await get_or_create_subscription(session, user.id)

    level_labels = {
        "low":    "🔵 Низкий",
        "medium": "🟢 Средний",
        "high":   "🟠 Высокий",
        "max":    "🔴 Максимальный",
    }
    sub_status = "💎 Premium" if sub.is_active and sub.plan_type != "free" else "🆓 Бесплатно"

    lines = [
        f"👤 <b>Профиль</b>",
        f"Имя: {user.full_name or '—'}",
        f"Класс: {grade.label if grade else '—'}",
        f"Экзамен: {exam.name if exam else '—'}",
        f"Предмет: {subject.name if subject else '—'}",
        f"Уровень: {level_labels.get(user.target_level, '—')}",
        f"Время/день: {user.daily_minutes or '—'} мин",
        f"Подписка: {sub_status}",
    ]
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /progress ─────────────────────────────────────────────────

@router.message(Command("progress"))
@router.message(F.text == "📊 Прогресс")
async def cmd_progress(message: Message, session: AsyncSession) -> None:
    stats = await count_progress(session, message.from_user.id)
    plan  = await get_active_plan(session, message.from_user.id)

    total   = stats["total"]
    correct = stats["correct"]
    pct     = round(correct / total * 100) if total else 0

    plan_info = ""
    if plan:
        plan_info = (
            f"\n\n📋 Активный план: <b>{plan.template.title.split('·')[0].strip()}</b>\n"
            f"День {plan.current_day} из {plan.template.total_days}"
        )

    await message.answer(
        f"📊 <b>Прогресс</b>\n\n"
        f"Всего заданий выполнено: <b>{total}</b>\n"
        f"Из них верно: <b>{correct}</b> ({pct}%)"
        f"{plan_info}",
        parse_mode="HTML",
    )


# ── /today ────────────────────────────────────────────────────

@router.message(Command("today"))
@router.message(F.text == "📚 Задание на сегодня")
async def cmd_today(message: Message, session: AsyncSession) -> None:
    await send_today_task(message, session)
