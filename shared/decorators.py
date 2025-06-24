import random
from functools import wraps
from typing import Callable, Any
from aiogram.types import Message, CallbackQuery
from aiogram import Bot


def private_chat_only(response_probability: float = 0.5, responses: list[str] = None):
    """
    Декоратор, который разрешает выполнение обработчика только в приватных чатах.
    В группах/каналах с вероятностью response_probability отправляет случайный ответ
    из списка responses или игнорирует.

    Args:
        response_probability (float): Вероятность отправки ответа (0.0 - 1.0).
        responses (list[str]): Список возможных ответов. Если None, используется стандартный список.
    """
    if responses is None:
        responses = [
            "Эта команда работает только в личных сообщениях! 😊",
            "Пожалуйста, используй меня в приватном чате. 🙏",
            "Я не работаю в группах, напиши мне в личку! ✉️",
        ]

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(*args, **kwargs) -> Any:
            # Извлекаем Message или CallbackQuery из аргументов
            event = next(
                (arg for arg in args if isinstance(arg, (Message, CallbackQuery))), None
            )
            if not event:
                return await handler(*args, **kwargs)

            bot: Bot = kwargs.get("bot") or next(
                (arg for arg in args if isinstance(arg, Bot)), None
            )
            if not bot:
                return await handler(*args, **kwargs)

            chat = event.chat if isinstance(event, Message) else event.message.chat
            if chat.type == "private":
                return await handler(*args, **kwargs)
            else:
                if random.random() < response_probability:
                    response = random.choice(responses)
                    if isinstance(event, Message):
                        await bot.send_message(chat_id=chat.id, text=response)
                    elif isinstance(event, CallbackQuery):
                        await bot.send_message(chat_id=chat.id, text=response)
                        await event.answer()
                return None

        return wrapper

    return decorator


def group_chat_only(response_probability: float = 0.5, responses: list[str] = None):
    """
    Декоратор, который разрешает выполнение обработчика только в групповых чатах или каналах.
    В приватных чатах с вероятностью response_probability отправляет случайный ответ
    из списка responses или игнорирует.

    Args:
        response_probability (float): Вероятность отправки ответа (0.0 - 1.0).
        responses (list[str]): Список возможных ответов. Если None, используется стандартный список.
    """
    if responses is None:
        responses = [
            "Эта команда работает только в группах или каналах! 😊",
            "Пожалуйста, используй меня в группе. 🙏",
            "Я не работаю в личных сообщениях, добавь меня в группу! 👥",
        ]

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(*args, **kwargs) -> Any:
            # Извлекаем Message или CallbackQuery из аргументов
            event = next(
                (arg for arg in args if isinstance(arg, (Message, CallbackQuery))), None
            )
            if not event:
                return await handler(*args, **kwargs)

            bot: Bot = kwargs.get("bot") or next(
                (arg for arg in args if isinstance(arg, Bot)), None
            )
            if not bot:
                return await handler(*args, **kwargs)

            chat = event.chat if isinstance(event, Message) else event.message.chat
            if chat.type in ("group", "supergroup", "channel"):
                return await handler(*args, **kwargs)
            else:
                if random.random() < response_probability:
                    response = random.choice(responses)
                    if isinstance(event, Message):
                        await bot.send_message(chat_id=chat.id, text=response)
                    elif isinstance(event, CallbackQuery):
                        await bot.send_message(chat_id=chat.id, text=response)
                        await event.answer()
                return None

        return wrapper

    return decorator
