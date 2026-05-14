"""
APScheduler-based daily task dispatcher.

At 08:00 Moscow time (configurable via TIMEZONE env var):
  1. Resets tasks_sent_today counters
  2. Advances current_day for active plans
  3. Sends a task to every user who has an active plan
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from aiogram.types import Message

from config import settings
from db.database import async_session
from db.service import get_all_subscribed_users, get_active_plan, get_next_task
from db.models import UserPlan

logger = logging.getLogger(__name__)


async def _reset_daily_counters() -> None:
    """Reset tasks_sent_today for all active plans (runs at midnight)."""
    async with async_session() as session:
        async with session.begin():
            from sqlalchemy import select
            res = await session.execute(
                select(UserPlan).where(UserPlan.is_active == True)
            )
            for plan in res.scalars().all():
                plan.tasks_sent_today = 0
                plan.current_day = min(plan.current_day + 1, plan.template.total_days)
    logger.info("Daily counters reset.")


async def _send_daily_tasks(bot: Bot) -> None:
    """Send one task to each subscribed user."""
    async with async_session() as session:
        users = await get_all_subscribed_users(session)

    for user in users:
        try:
            async with async_session() as session:
                async with session.begin():
                    plan = await get_active_plan(session, user.id)
                    if plan is None:
                        continue
                    task = await get_next_task(
                        session,
                        user_id      = user.id,
                        subject_id   = plan.template.subject_id,
                        target_level = plan.template.target_level,
                    )
                    if task is None:
                        continue

                    plan.tasks_sent_today += 1

                    from bot.keyboards import task_answer_kb
                    text = (
                        f"🌅 <b>Задание дня (день {plan.current_day})</b>\n"
                        f"─────────────────\n"
                        f"{task.title}\n\n"
                        f"{task.body}"
                    )
                    await bot.send_message(
                        user.id, text,
                        reply_markup=task_answer_kb(task.id),
                        parse_mode="HTML",
                    )
        except Exception as exc:
            logger.warning("Failed to send task to user %s: %s", user.id, exc)

    logger.info("Daily tasks sent to %d users.", len(users))


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Create and return configured scheduler (call .start() separately)."""
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

    # Reset counters at midnight
    scheduler.add_job(
        _reset_daily_counters,
        trigger=CronTrigger(hour=0, minute=0, timezone=settings.TIMEZONE),
        id="reset_daily_counters",
        replace_existing=True,
    )

    # Send daily tasks at 08:00
    scheduler.add_job(
        _send_daily_tasks,
        args=[bot],
        trigger=CronTrigger(hour=8, minute=0, timezone=settings.TIMEZONE),
        id="send_daily_tasks",
        replace_existing=True,
    )

    return scheduler
