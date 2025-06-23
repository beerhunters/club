from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, insert, func
from sqlalchemy.exc import IntegrityError
from db.models import GroupAdmin
from db.schemas import GroupAdminCreate
from bot.logger import setup_logger

logger = setup_logger(__name__)


class GroupAdminRepository:
    @staticmethod
    async def create_group_admin(
        session: AsyncSession, group_admin_data: GroupAdminCreate
    ) -> GroupAdmin:
        """Creates a new group admin record in the database."""
        try:
            stmt = (
                insert(GroupAdmin)
                .values(**group_admin_data.model_dump())
                .returning(GroupAdmin)
            )
            result = await session.execute(stmt)
            group_admin = result.scalar_one()
            await session.commit()
            return group_admin
        except IntegrityError as e:
            logger.error(f"Integrity error creating group admin: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error creating group admin: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_group_admin_by_chat_id(
        session: AsyncSession, chat_id: int
    ) -> Optional[GroupAdmin]:
        """Retrieves a group admin record by chat ID."""
        try:
            stmt = select(GroupAdmin).where(GroupAdmin.chat_id == chat_id)
            result = await session.execute(stmt)
            group_admin = result.scalar_one_or_none()
            return group_admin
        except Exception as e:
            logger.error(f"Error getting group admin by chat_id {chat_id}: {e}")
            raise

    @staticmethod
    async def get_group_admins_by_user_id(
        session: AsyncSession, user_id: int
    ) -> List[GroupAdmin]:
        """Retrieves all group admin records for a specific user_id."""
        try:
            stmt = select(GroupAdmin).where(GroupAdmin.user_id == user_id)
            result = await session.execute(stmt)
            group_admins = result.scalars().all()
            return list(group_admins)
        except Exception as e:
            logger.error(f"Error getting group admins by user_id {user_id}: {e}")
            raise

    @staticmethod
    async def delete_group_admin(session: AsyncSession, chat_id: int) -> bool:
        """Deletes a group admin record by chat ID."""
        try:
            stmt = delete(GroupAdmin).where(GroupAdmin.chat_id == chat_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount is not None and result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting group admin {chat_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def group_admin_exists(session: AsyncSession, chat_id: int) -> bool:
        """Checks if a group admin record exists by chat ID."""
        try:
            stmt = select(func.count(GroupAdmin.chat_id)).where(
                GroupAdmin.chat_id == chat_id
            )
            result = await session.execute(stmt)
            count = result.scalar_one()
            return count > 0
        except Exception as e:
            logger.error(f"Error checking group admin exists {chat_id}: {e}")
            raise
