from aiogram import Router, Bot, types
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.user_repository import UserRepository
from bot.core.repositories.group_admin_repository import GroupAdminRepository
from bot.texts import (
    START_SIMPLE_TEXT,
    START_ALREADY_REGISTERED,
    START_REGISTER_BUTTON,
    INVALID_LINK_FORMAT,
    GREET_NAME,
    ALREADY_REGISTERED_IN_GROUP,
    REGISTER_IN_PRIVATE,
    START_MESSAGE,
)
from bot.fsm.registration import Registration
from shared.decorators import private_chat_only
from bot.logger import setup_logger

router = Router()
logger = setup_logger("start")


def get_command_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🍺 Выбрать пиво", callback_data="cmd_beer"))
    builder.add(InlineKeyboardButton(text="👤 Профиль", callback_data="cmd_profile"))
    builder.adjust(2)
    return builder.as_markup()


async def start_command(
    chat_id: int,
    user_id: int,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    group_id: int = None,
    is_private: bool = True,
):
    logger.info(
        f"Starting /start or cmd_start for user_id={user_id}, group_id={group_id}, is_private={is_private}"
    )
    try:
        user = await UserRepository.get_user_by_id(session, user_id)

        # Проверяем, зарегистрирован ли пользователь в указанной группе (для групп)
        if not is_private and group_id:
            if user and user.registered_from_group_id == group_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text=ALREADY_REGISTERED_IN_GROUP,
                )
                await state.clear()
                return

        # Если пользователь зарегистрирован, показываем меню
        if user:
            await bot.send_message(
                chat_id=chat_id,
                text=START_MESSAGE,
                reply_markup=get_command_keyboard(),
            )
            await state.clear()
            return

        # Обработка диплинка в личных сообщениях
        if is_private and group_id:
            if await GroupAdminRepository.group_admin_exists(session, group_id):
                await state.set_state(Registration.name)
                await state.update_data(group_id=group_id)
                logger.info(
                    f"Пользователь {user_id} начал регистрацию из группы {group_id}"
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=GREET_NAME,
                )
            else:
                logger.warning(f"Group {group_id} is not registered as GroupAdmin")
                await bot.send_message(
                    chat_id=chat_id,
                    text=INVALID_LINK_FORMAT,
                )
                await state.clear()
            return

        # В группе: показываем диплинк для регистрации
        if not is_private:
            bot_user = await bot.get_me()
            deeplink = f"https://t.me/{bot_user.username}?start=registration_{chat_id}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=START_REGISTER_BUTTON, url=deeplink)],
                ],
            )
            await bot.send_message(
                chat_id=chat_id,
                text=REGISTER_IN_PRIVATE,
                reply_markup=keyboard,
            )
            await state.clear()
            return

        # В личных сообщениях без диплинка: предлагаем зарегистрироваться
        await bot.send_message(
            chat_id=chat_id,
            text="🎲",
        )
        await state.clear()
    except Exception as e:
        logger.error(
            f"Error in start_command for user_id={user_id}: {e}", exc_info=True
        )
        await bot.send_message(
            chat_id=chat_id,
            text=START_SIMPLE_TEXT,
        )
        await state.clear()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id
    text_parts = message.text.split(maxsplit=1)
    logger.info(f"/start от {user_id}, текст: {message.text}")
    group_id = None

    if len(text_parts) > 1 and text_parts[1].startswith("registration_"):
        try:
            group_id = int(text_parts[1].split("_")[1])
        except (IndexError, ValueError):
            logger.warning(f"Invalid registration link: {message.text}")
            await start_command(
                chat_id=message.chat.id,
                user_id=user_id,
                bot=message.bot,
                state=state,
                session=session,
                is_private=message.chat.type == "private",
            )
            return

    await start_command(
        chat_id=message.chat.id,
        user_id=user_id,
        bot=message.bot,
        state=state,
        session=session,
        group_id=group_id,
        is_private=message.chat.type == "private",
    )


@router.callback_query(lambda c: c.data == "cmd_start")
@private_chat_only(response_probability=0.5)
async def start_callback_handler(
    callback_query: types.CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    state: FSMContext,
):
    try:
        await callback_query.answer()
        await start_command(
            chat_id=callback_query.message.chat.id,
            user_id=callback_query.from_user.id,
            bot=bot,
            state=state,
            session=session,
            is_private=True,
        )
    except Exception as e:
        logger.error(f"Error in start_callback_handler: {e}", exc_info=True)
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=START_SIMPLE_TEXT,
        )
        await state.clear()
