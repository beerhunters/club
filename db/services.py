from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import User, GroupAdmin
from db.schemas import UserCreate, GroupAdminCreate


async def get_user_by_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
    user = User(
        telegram_id=user_data.telegram_id,
        username=user_data.username,
        name=user_data.name,
        birth_date=user_data.birth_date,
        registered_from_group_id=user_data.registered_from_group_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def save_group_admin(
    session: AsyncSession, chat_id: int, user_id: int
) -> GroupAdmin:
    exists = await session.scalar(
        select(GroupAdmin).where(
            GroupAdmin.chat_id == chat_id, GroupAdmin.user_id == user_id
        )
    )
    if not exists:
        admin = GroupAdmin(chat_id=chat_id, user_id=user_id)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin
    return exists
