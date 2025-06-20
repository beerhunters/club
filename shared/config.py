import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    ERROR_CHAT_ID = os.getenv("ERROR_CHAT_ID")
    REDIS_URL = os.getenv("REDIS_URL")


settings = Settings()
