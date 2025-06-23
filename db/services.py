from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import User, GroupAdmin, Event
from db.schemas import UserCreate, GroupAdminCreate, EventCreate
from typing import List, Optional


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


async def get_group_admin_by_user_id(
    session: AsyncSession, user_id: int
) -> Optional[GroupAdmin]:
    result = await session.execute(
        select(GroupAdmin).where(GroupAdmin.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_event(session: AsyncSession, event_data: EventCreate) -> Event:
    event = Event(
        name=event_data.name,
        event_date=event_data.event_date,
        event_time=event_data.event_time,
        latitude=event_data.latitude,
        longitude=event_data.longitude,
        location_name=event_data.location_name,
        description=event_data.description,
        image_file_id=event_data.image_file_id,
        has_beer_choice=event_data.has_beer_choice,
        beer_option_1=event_data.beer_option_1,
        beer_option_2=event_data.beer_option_2,
        created_by=event_data.created_by,
        chat_id=event_data.chat_id,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def get_users_by_group_id(session: AsyncSession, group_id: int) -> List[User]:
    result = await session.execute(
        select(User).where(User.registered_from_group_id == group_id)
    )
    return result.scalars().all()
