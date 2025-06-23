from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError
from db.models import User
from db.schemas import UserCreate
from bot.logger import setup_logger

logger = setup_logger(__name__)


class UserRepository:
    @staticmethod
    async def get_user_by_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Получает пользователя по telegram_id."""
        try:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except Exception as e:
            logger.error(
                f"Ошибка получения пользователя по telegram_id {telegram_id}: {e}"
            )
            raise

    @staticmethod
    async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
        """Создает нового пользователя в базе данных."""
        try:
            stmt = insert(User).values(**user_data.model_dump()).returning(User)
            result = await session.execute(stmt)
            user = result.scalar_one()
            await session.commit()
            return user
        except IntegrityError as e:
            logger.error(f"Ошибка целостности при создании пользователя: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def user_exists(session: AsyncSession, telegram_id: int) -> bool:
        """Проверяет, существует ли пользователь по telegram_id."""
        try:
            stmt = select(User.telegram_id).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(
                f"Ошибка проверки существования пользователя {telegram_id}: {e}"
            )
            raise
