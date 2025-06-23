# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# from sqlalchemy.orm import sessionmaker, declarative_base
#
# from bot.logger import setup_logger
# from shared.config import settings
#
# DATABASE_URL = settings.DATABASE_URL
#
# engine = create_async_engine(DATABASE_URL, echo=False)
# AsyncSessionLocal = sessionmaker(
#     bind=engine, class_=AsyncSession, expire_on_commit=False
# )
# Base = declarative_base()
#
# logger = setup_logger("db")
#
#
# async def init_db():
#     try:
#         logger.info(f"Registered tables: {list(Base.metadata.tables.keys())}")
#         async with engine.begin() as conn:
#             # Import models after Base to register them
#             from db.models.group_admin import GroupAdmin
#
#             await conn.run_sync(Base.metadata.create_all)
#         logger.info("Database initialization complete")
#     except Exception as e:
#         logger.error(f"Failed to initialize database: {e}")
#         raise
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from bot.logger import setup_logger
from shared.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)

async_session_maker = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

logger = setup_logger("db")


async def init_db():
    try:
        logger.info(f"Registered tables: {list(Base.metadata.tables.keys())}")
        async with engine.begin() as conn:
            from db.models.group_admin import GroupAdmin
            from db.models.user import User  # если есть другие модели

            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
