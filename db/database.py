from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from shared.config import settings
from bot.logger import setup_logger
import asyncio

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

logger = setup_logger("db")


async def init_db(max_retries=5, delay=5):
    """Инициализирует базу данных с повторными попытками."""
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info(f"Registered tables: {list(Base.metadata.tables.keys())}")
            return
        except Exception as e:
            logger.error(f"Попытка {attempt}/{max_retries} не удалась: {e}")
            if attempt == max_retries:
                logger.error(f"Не удалось инициализировать базу данных: {e}")
                raise
            await asyncio.sleep(delay)
