"""
Async SQLAlchemy engine and session factory.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from .models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# Минимальная "ручная" миграция для dev-SQLite, чтобы не требовать Alembic
# при добавлении новых колонок к существующим таблицам.
_ADD_COLUMNS_SQL = [
    # tasks
    ("tasks", "correct_answer",     "TEXT"),
    ("tasks", "acceptable_answers", "TEXT"),
    ("tasks", "explanation",        "TEXT"),
    ("tasks", "image_url",          "VARCHAR(1024)"),
    ("tasks", "image_file_id",      "VARCHAR(512)"),
    ("tasks", "source_url",         "VARCHAR(1024)"),
    # users
    ("users", "notify_count",   "INTEGER DEFAULT 1"),
    ("users", "notify_times",   "VARCHAR(64) DEFAULT '08:00'"),
    ("users", "active_task_id", "INTEGER"),
]


async def _migrate_sqlite(conn) -> None:
    """Добавляет недостающие колонки в существующие таблицы.

    Используется только для SQLite (dev/MVP). Для prod добавьте Alembic.
    """
    if not str(engine.url).startswith("sqlite"):
        return
    for table, column, ddl in _ADD_COLUMNS_SQL:
        try:
            res = await conn.execute(text(f'PRAGMA table_info("{table}")'))
            existing = {row[1] for row in res.fetchall()}
            if column not in existing:
                await conn.execute(text(
                    f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl}'
                ))
                logger.info("Added column %s.%s", table, column)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Migration skipped for %s.%s: %s", table, column, exc)


async def init_db() -> None:
    """Create all tables (idempotent) + apply lightweight column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_sqlite(conn)
