from db.models.user import User  # модель нужно создать
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_id(session: AsyncSession, telegram_id: int):
    return await session.get(User, telegram_id)


async def save_user(
    session: AsyncSession,
    telegram_id: int,
    username: str,
    name: str,
    birth_date,
    group_id: int,
):
    user = User(
        telegram_id=telegram_id,
        username=username,
        name=name,
        birth_date=birth_date,
        registered_from_group_id=group_id,
    )
    session.add(user)
    await session.commit()
