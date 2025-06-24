import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")
    REDIS_URL = os.getenv("REDIS_URL")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "bot.log")
    async_engine = create_async_engine(DATABASE_URL, echo=False)


settings = Settings()
