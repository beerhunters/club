# import asyncio
# from aiogram import Bot, Dispatcher
# from aiogram.client.default import DefaultBotProperties
# from aiogram.enums import ParseMode
#
# from aiogram.fsm.storage.redis import RedisStorage
# from aiogram.types.bot_command import BotCommand
# from redis.asyncio import Redis
#
# from bot.handlers import start, join, registration, event
# from bot.middlewares.db import DBSessionMiddleware
# from db.database import init_db
# from shared.config import settings
# from bot.error_handler import setup_error_handler
# from bot.logger import setup_logger
#
# logger = setup_logger("bot")
#
#
# async def main():
#     logger.info("Запуск бота...")
#
#     # Initialize database tables
#     await init_db()
#     logger.info("Database tables created")
#
#     # Redis-хранилище FSM
#     redis = Redis.from_url(settings.REDIS_URL)
#     storage = RedisStorage(redis=redis)
#
#     bot = Bot(
#         token=settings.BOT_TOKEN,
#         default=DefaultBotProperties(parse_mode=ParseMode.HTML),
#     )
#     dp = Dispatcher(storage=storage)
#
#     setup_error_handler(dp, bot)
#     dp.include_routers(start.router, join.router, registration.router, event.router)
#     dp.message.middleware(DBSessionMiddleware())
#     dp.callback_query.middleware(DBSessionMiddleware())
#
#     # Пример запуска polling с фильтром обновлений
#     allowed_updates = ["message", "callback_query", "my_chat_member", "chat_member"]
#
#     # Команды в интерфейсе Telegram
#     await bot.set_my_commands(
#         [
#             BotCommand(command="start", description="Run, drink, repeat!"),
#         ]
#     )
#
#     await dp.start_polling(bot, allowed_updates=allowed_updates)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.logger import setup_logger
from bot.middlewares.db import DBSessionMiddleware
from bot.handlers import start, registration, event, join
from bot.error_handler import setup_error_handler
from shared.config import settings
from db.database import init_db

logger = setup_logger("bot")


async def main():
    """Основная функция запуска бота"""
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db()
        logger.info("База данных инициализирована")

        # Настройка Redis для FSM
        redis = Redis.from_url(settings.REDIS_URL)
        storage = RedisStorage(redis=redis)

        # Создание бота и диспетчера
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        dp = Dispatcher(storage=storage)

        # Регистрация middleware
        dp.message.middleware(DBSessionMiddleware())
        dp.callback_query.middleware(DBSessionMiddleware())
        dp.my_chat_member.middleware(DBSessionMiddleware())

        # Регистрация роутеров
        dp.include_router(start.router)
        dp.include_router(registration.router)
        dp.include_router(event.router)
        dp.include_router(join.router)

        # Настройка обработчика ошибок
        setup_error_handler(dp, bot)

        # Запуск поллинга
        allowed_updates = ["message", "callback_query", "my_chat_member", "chat_member"]

        logger.info("Бот запущен")
        await dp.start_polling(bot, allowed_updates=allowed_updates)

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise
    finally:
        # Закрытие соединений
        if "redis" in locals():
            await redis.close()
        if "bot" in locals():
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
