# db/services/group_admin.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.group_admin import GroupAdmin


async def save_group_admin(session: AsyncSession, chat_id: int, user_id: int):
    exists = await session.scalar(
        select(GroupAdmin).where(GroupAdmin.chat_id == chat_id)
    )
    if not exists:
        session.add(GroupAdmin(chat_id=chat_id, user_id=user_id))
        await session.commit()
