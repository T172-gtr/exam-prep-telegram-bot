"""
Middleware that injects an async DB session into every handler's data dict.
Usage in handlers: async def handler(message, session: AsyncSession, ...)
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from db.database import async_session


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            async with session.begin():
                data["session"] = session
                return await handler(event, data)
