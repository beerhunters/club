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
        """Создает новую запись администратора группы в базе данных."""
        chat_id = group_admin_data.chat_id
        user_id = group_admin_data.user_id
        try:
            # Проверяем, существует ли запись
            if await GroupAdminRepository.group_admin_exists(session, chat_id):
                logger.info(f"Запись для группы chat_id={chat_id} уже существует")
                return await GroupAdminRepository.get_group_admin_by_chat_id(
                    session, chat_id
                )

            stmt = (
                insert(GroupAdmin)
                .values(**group_admin_data.model_dump())
                .returning(GroupAdmin)
            )
            result = await session.execute(stmt)
            group_admin = result.scalar_one()
            await session.commit()
            logger.info(
                f"Создан администратор группы: chat_id={group_admin.chat_id}, user_id={group_admin.user_id}"
            )
            return group_admin
        except IntegrityError as e:
            logger.warning(
                f"Повторная попытка создания записи для chat_id={chat_id}: {e}"
            )
            await session.rollback()
            existing_admin = await GroupAdminRepository.get_group_admin_by_chat_id(
                session, chat_id
            )
            if existing_admin:
                return existing_admin
            raise
        except Exception as e:
            logger.error(
                f"Ошибка при создании администратора группы для chat_id={chat_id}: {e}",
                exc_info=True,
            )
            await session.rollback()
            raise

    @staticmethod
    async def get_group_admin_by_chat_id(
        session: AsyncSession, chat_id: int
    ) -> Optional[GroupAdmin]:
        """Получает запись администратора группы по chat_id."""
        try:
            stmt = select(GroupAdmin).where(GroupAdmin.chat_id == chat_id)
            result = await session.execute(stmt)
            group_admin = result.scalar_one_or_none()
            if group_admin:
                logger.info(
                    f"Найден администратор для группы {chat_id}: user_id={group_admin.user_id}"
                )
            else:
                logger.info(f"Администратор для группы {chat_id} не найден")
            return group_admin
        except Exception as e:
            logger.error(
                f"Ошибка при получении администратора для группы {chat_id}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    async def get_group_admins_by_user_id(
        session: AsyncSession, user_id: int
    ) -> List[GroupAdmin]:
        """Получает все записи администраторов групп для указанного user_id."""
        try:
            stmt = select(GroupAdmin).where(GroupAdmin.user_id == user_id)
            result = await session.execute(stmt)
            group_admins = result.scalars().all()
            logger.info(
                f"Найдено {len(group_admins)} групп для администратора user_id={user_id}"
            )
            return list(group_admins)
        except Exception as e:
            logger.error(
                f"Ошибка при получении групп для администратора user_id={user_id}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    async def delete_group_admin(session: AsyncSession, chat_id: int) -> bool:
        """Удаляет запись администратора группы по chat_id."""
        try:
            stmt = delete(GroupAdmin).where(GroupAdmin.chat_id == chat_id)
            result = await session.execute(stmt)
            await session.commit()
            success = result.rowcount is not None and result.rowcount > 0
            logger.info(
                f"Удаление администратора группы {chat_id}: {'успешно' if success else 'не найдено'}"
            )
            return success
        except Exception as e:
            logger.error(
                f"Ошибка при удалении администратора группы {chat_id}: {e}",
                exc_info=True,
            )
            await session.rollback()
            raise

    @staticmethod
    async def group_admin_exists(session: AsyncSession, chat_id: int) -> bool:
        """Проверяет, существует ли запись администратора группы по chat_id."""
        try:
            stmt = select(func.count(GroupAdmin.chat_id)).where(
                GroupAdmin.chat_id == chat_id
            )
            result = await session.execute(stmt)
            count = result.scalar_one()
            exists = count > 0
            logger.info(
                f"Проверка существования группы {chat_id}: {'существует' if exists else 'не существует'}"
            )
            return exists
        except Exception as e:
            logger.error(
                f"Ошибка при проверке существования группы {chat_id}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    async def is_user_admin(session: AsyncSession, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором любой группы."""
        try:
            group_admins = await GroupAdminRepository.get_group_admins_by_user_id(
                session, user_id
            )
            is_admin = len(group_admins) > 0
            logger.info(
                f"Проверка администратора user_id={user_id}: {'является админом' if is_admin else 'не является админом'}"
            )
            return is_admin
        except Exception as e:
            logger.error(
                f"Ошибка при проверке администратора user_id={user_id}: {e}",
                exc_info=True,
            )
            raise

    @staticmethod
    async def get_admin_chat_id(session: AsyncSession, user_id: int) -> int | None:
        """Возвращает chat_id группы, где пользователь является администратором."""
        try:
            logger.info(f"Получение admin chat_id для user_id={user_id}")
            result = await session.execute(
                select(GroupAdmin.chat_id).where(GroupAdmin.user_id == user_id).limit(1)
            )
            chat_id = result.scalar()
            if chat_id:
                logger.info(
                    f"Найден администратор user_id={user_id} для chat_id={chat_id}"
                )
            else:
                logger.warning(f"Для user_id={user_id} не найден admin chat_id")
            return chat_id
        except Exception as e:
            logger.error(
                f"Error getting admin chat_id for user {user_id}: {e}", exc_info=True
            )
            raise
