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

Base = declarative_base()


def get_async_engine(loop=None):
    """Создаёт асинхронный движок SQLAlchemy с указанным циклом событий."""
    if loop is None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    return create_async_engine(DATABASE_URL, echo=False, connect_args={"loop": loop})


def get_async_session_maker(loop=None):
    """Создаёт фабрику сессий для указанного цикла событий."""
    engine = get_async_engine(loop)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db(loop=None, max_retries=5, delay=5):
    """Инициализирует базу данных с повторными попытками."""
    engine = get_async_engine(loop)
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
        finally:
            await engine.dispose()


async def get_async_session(loop=None):
    """Генератор асинхронной сессии базы данных для использования с async for."""
    session_maker = get_async_session_maker(loop)
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Ошибка в сессии базы данных: {e}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_context(loop=None) -> AsyncSession:
    """Контекстный менеджер для асинхронной сессии базы данных."""
    session_maker = get_async_session_maker(loop)
    session = session_maker()
    try:
        async with session:
            yield session
    except Exception as e:
        logger.error(f"Ошибка в сессии базы данных: {e}", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()
