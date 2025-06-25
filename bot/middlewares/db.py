from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_async_session_maker
import asyncio


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        loop = asyncio.get_event_loop()
        session_maker = get_async_session_maker(loop)
        async with session_maker() as session:
            data["session"] = session
            return await handler(event, data)
