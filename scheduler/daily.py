"""
APScheduler-based dispatcher.

Поведение:
- В 00:00 (по TIMEZONE) сбрасываются дневные счётчики и продвигаются дни планов.
- Каждую минуту проверяется, не наступило ли время рассылки для пользователя.
  Время хранится в `users.notify_times` (CSV, формат HH:MM). Если текущее
  локальное время совпадает с любым из значений, пользователю отправляется
  следующее задание из любого активного плана.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from sqlalchemy import select

from config import settings
from db.database import async_session
from db.service import (
    get_all_subscribed_users, get_active_plans, get_next_task,
    update_user_profile, get_or_create_subscription,
)
from db.models import UserPlan
from bot.keyboards import task_answer_kb

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Сброс счётчиков и продвижение дня
# ──────────────────────────────────────────────────────────────

async def _reset_daily_counters() -> None:
    async with async_session() as session:
        async with session.begin():
            res = await session.execute(
                select(UserPlan).where(UserPlan.is_active == True)
            )
            for plan in res.scalars().all():
                plan.tasks_sent_today = 0
                # template уже подгружен через relationship lazy, но в async
                # сессии безопаснее обратиться через id
                await session.refresh(plan, attribute_names=["template"])
                plan.current_day = min(plan.current_day + 1, plan.template.total_days)
    logger.info("Daily counters reset.")


# ──────────────────────────────────────────────────────────────
# Поминутная проверка — кому пора слать задание
# ──────────────────────────────────────────────────────────────

async def _tick(bot: Bot) -> None:
    tz = ZoneInfo(settings.TIMEZONE)
    now = datetime.now(tz).strftime("%H:%M")

    async with async_session() as session:
        users = await get_all_subscribed_users(session)

    for user in users:
        times = [t.strip() for t in (user.notify_times or "08:00").split(",") if t.strip()]
        if now not in times:
            continue

        try:
            async with async_session() as session:
                async with session.begin():
                    sub = await get_or_create_subscription(session, user.id)
                    is_premium = sub.is_active and sub.plan_type != "free"

                    plans = await get_active_plans(session, user.id)
                    if not plans:
                        continue

                    total_today = sum(p.tasks_sent_today for p in plans)
                    if not is_premium and total_today >= settings.FREE_DAILY_LIMIT:
                        continue

                    chosen_plan = None
                    chosen_task = None
                    for plan in plans:
                        task = await get_next_task(
                            session,
                            user_id      = user.id,
                            subject_id   = plan.template.subject_id,
                            target_level = plan.template.target_level,
                        )
                        if task is not None:
                            chosen_plan, chosen_task = plan, task
                            break
                    if chosen_task is None:
                        continue

                    chosen_plan.tasks_sent_today += 1
                    await update_user_profile(session, user.id,
                                               active_task_id=chosen_task.id)

                    text_parts = [
                        f"🌅 <b>Задание · {chosen_plan.template.subject.name}</b>",
                        "─────────────────",
                        f"<b>{chosen_task.title}</b>",
                        "",
                        chosen_task.body,
                    ]
                    if chosen_task.source_url:
                        text_parts.append("")
                        text_parts.append(f"🔗 Источник: {chosen_task.source_url}")
                    text_parts.append("")
                    text_parts.append("✍️ Пришли ответ текстом — я проверю автоматически.")
                    text = "\n".join(text_parts)

                    photo = chosen_task.image_file_id or chosen_task.image_url
                    try:
                        if photo:
                            await bot.send_photo(
                                user.id, photo,
                                caption=text,
                                parse_mode="HTML",
                                reply_markup=task_answer_kb(chosen_task.id),
                            )
                        else:
                            await bot.send_message(
                                user.id, text,
                                parse_mode="HTML",
                                reply_markup=task_answer_kb(chosen_task.id),
                            )
                    except Exception as exc:
                        logger.warning("Send photo failed, fallback text for user %s: %s",
                                       user.id, exc)
                        await bot.send_message(
                            user.id, text,
                            parse_mode="HTML",
                            reply_markup=task_answer_kb(chosen_task.id),
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tick failed for user %s: %s", user.id, exc)


# ──────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

    scheduler.add_job(
        _reset_daily_counters,
        trigger=CronTrigger(hour=0, minute=0, timezone=settings.TIMEZONE),
        id="reset_daily_counters",
        replace_existing=True,
    )

    # Поминутный тик — рассылает по индивидуальным временам.
    scheduler.add_job(
        _tick,
        args=[bot],
        trigger=CronTrigger(minute="*", timezone=settings.TIMEZONE),
        id="per_minute_dispatch",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    return scheduler
