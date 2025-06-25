from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from db.models import BeerSelection
from db.schemas import BeerSelectionCreate
from bot.logger import setup_logger
from typing import Optional

logger = setup_logger(__name__)


class BeerRepository:
    @staticmethod
    async def create_beer_selection(
        session: AsyncSession, selection_data: BeerSelectionCreate
    ) -> BeerSelection:
        """Создаёт запись о выборе пива."""
        try:
            logger.info(
                f"Creating beer selection for user_id={selection_data.user_id}, event_id={selection_data.event_id}"
            )
            stmt = (
                insert(BeerSelection)
                .values(**selection_data.dict())
                .returning(BeerSelection)
            )
            result = await session.execute(stmt)
            selection = result.scalar_one()
            await session.commit()
            logger.info(f"Created beer selection id={selection.id}")
            return selection
        except Exception as e:
            logger.error(f"Error creating beer selection: {e}", exc_info=True)
            await session.rollback()
            raise

    @staticmethod
    async def get_user_selection(
        session: AsyncSession, user_id: int, event_id: int
    ) -> Optional[BeerSelection]:
        """Проверяет, сделал ли пользователь выбор пива для события."""
        try:
            logger.debug(
                f"Checking beer selection for user_id={user_id}, event_id={event_id}"
            )
            stmt = select(BeerSelection).where(
                BeerSelection.user_id == user_id, BeerSelection.event_id == event_id
            )
            result = await session.execute(stmt)
            selection = result.scalar_one_or_none()
            if selection:
                logger.debug(f"Found beer selection id={selection.id}")
            else:
                logger.debug(f"No beer selection found")
            return selection
        except Exception as e:
            logger.error(f"Error checking beer selection: {e}", exc_info=True)
            raise
