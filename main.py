"""
Entry point — initialises DB, seeds data, starts polling.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from db.database import init_db
from db.seed import seed
from bot.handlers import get_main_router
from bot.middlewares import DbSessionMiddleware
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # ── DB init & seed ────────────────────────────────────────
    logger.info("Initialising database …")
    await init_db()
    logger.info("Seeding reference data …")
    await seed()

    # ── Bot setup ─────────────────────────────────────────────
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp  = Dispatcher()

    # Middleware (injects `session` into every handler)
    dp.update.middleware(DbSessionMiddleware())

    # Routers
    dp.include_router(get_main_router())

    # ── Scheduler ─────────────────────────────────────────────
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started (tz=%s).", settings.TIMEZONE)

    # ── Polling ───────────────────────────────────────────────
    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
