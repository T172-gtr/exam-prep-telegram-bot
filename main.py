"""
Entry point — initialises DB, seeds data, starts polling.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BotCommand, BotCommandScopeDefault, BotCommandScopeChat,
)

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


PUBLIC_COMMANDS = [
    BotCommand(command="start",     description="Запустить бота / приветствие"),
    BotCommand(command="menu",      description="Главное меню"),
    BotCommand(command="profile",   description="Мой профиль"),
    BotCommand(command="progress",  description="Мой прогресс"),
    BotCommand(command="today",     description="Получить задание сейчас"),
    BotCommand(command="schedule",  description="Настроить рассылку"),
    BotCommand(command="subscribe", description="Подписка Premium"),
    BotCommand(command="help",      description="Справка по командам"),
]

ADMIN_EXTRA_COMMANDS = [
    BotCommand(command="admin",        description="Админ: панель"),
    BotCommand(command="admin_stats",  description="Админ: статистика по предметам"),
    BotCommand(command="admin_add_task", description="Админ: добавить задание"),
    BotCommand(command="admin_import", description="Админ: импорт заданий из JSON"),
]


async def _setup_bot_commands(bot: Bot) -> None:
    """Регистрирует список команд: публичные — всем, админские — только админам."""
    try:
        await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to set default commands: %s", exc)

    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.set_my_commands(
                PUBLIC_COMMANDS + ADMIN_EXTRA_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to set admin commands for %s: %s", admin_id, exc)


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

    # Commands menu (Telegram side)
    await _setup_bot_commands(bot)

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
