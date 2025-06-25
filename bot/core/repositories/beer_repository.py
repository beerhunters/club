from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, func
from db.models import BeerSelection, Event
from db.schemas import BeerSelectionCreate
from bot.logger import setup_logger
from typing import List, Optional, Dict, Tuple
import pendulum

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

    @staticmethod
    async def get_beer_stats(session: AsyncSession, user_id: int) -> Dict[str, int]:
        try:
            logger.debug(f"Fetching beer stats for user_id={user_id}")
            stmt = (
                select(BeerSelection.beer_choice, func.count(BeerSelection.beer_choice))
                .where(BeerSelection.user_id == user_id)
                .group_by(BeerSelection.beer_choice)
            )
            result = await session.execute(stmt)
            stats = {row[0]: row[1] for row in result.all()}
            logger.info(f"Fetched beer stats for user_id={user_id}: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Error fetching beer stats: {e}", exc_info=True)
            raise

    @staticmethod
    async def get_last_beer_choice(
        session: AsyncSession, user_id: int
    ) -> Optional[Tuple[str, str, str]]:
        try:
            logger.debug(f"Fetching last beer choice for user_id={user_id}")
            stmt = (
                select(
                    BeerSelection.beer_choice,
                    Event.name,
                    Event.event_date,
                    Event.event_time,
                )
                .join(Event, BeerSelection.event_id == Event.id)
                .where(BeerSelection.user_id == user_id)
                .order_by(BeerSelection.selected_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.first()
            if row:
                beer_choice, event_name, event_date, event_time = row
                event_datetime = pendulum.datetime(
                    event_date.year,
                    event_date.month,
                    event_date.day,
                    event_time.hour,
                    event_time.minute,
                    tz="Europe/Moscow",
                ).format("DD.MM.YYYY HH:mm")
                logger.debug(
                    f"Found last beer choice for user_id={user_id}: {beer_choice} at {event_name}"
                )
                return beer_choice, event_name, event_datetime
            logger.debug(f"No last beer choice found for user_id={user_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching last beer choice: {e}", exc_info=True)
            raise
