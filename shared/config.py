import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from db.database import get_async_engine

load_dotenv()


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")
    REDIS_URL = os.getenv("REDIS_URL")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "bot.log")

    def get_async_engine(self, loop=None):
        return get_async_engine(loop)


settings = Settings()
