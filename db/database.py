from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from bot.logger import setup_logger
import asyncio
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()
logger = setup_logger("db")
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:secret@postgres:5432/myapp"
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


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


async def get_async_session():
    """Генератор асинхронной сессии базы данных для использования с async for."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Ошибка в сессии базы данных: {e}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_context() -> AsyncSession:
    """Контекстный менеджер для асинхронной сессии базы данных для использования с async with."""
    session = async_session_maker()
    try:
        async with session:
            yield session
    except Exception as e:
        logger.error(f"Ошибка в сессии базы данных: {e}", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()
