import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import join
from shared.config import settings
from bot.handlers.start import register_start
from bot.error_handler import setup_error_handler
from bot.logger import setup_logger

logger = setup_logger("bot")


async def main():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    register_start(dp)
    setup_error_handler(dp, bot)
    dp.include_router(join.router)

    logger.info("Запуск бота...")
    # Пример запуска polling с фильтром обновлений
    allowed_updates = ["message", "callback_query", "my_chat_member", "chat_member"]

    await dp.start_polling(bot, allowed_updates=allowed_updates)


if __name__ == "__main__":
    asyncio.run(main())
