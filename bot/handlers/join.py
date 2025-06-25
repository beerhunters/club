from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession
from bot.core.repositories.group_admin_repository import GroupAdminRepository
from db.schemas import GroupAdminCreate
from bot.texts import GROUP_ADMIN_REMOVED
from bot.logger import setup_logger

router = Router()
logger = setup_logger("group_join")


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot, session: AsyncSession):
    logger.info("Получено обновление my_chat_member")
    try:
        bot_user = await bot.me()
        if event.new_chat_member.user.id != bot_user.id:
            logger.info(
                f"Обновление касается другого пользователя: {event.new_chat_member.user.id}"
            )
            return

        chat_id = event.chat.id
        admin_id = event.from_user.id
        new_status = event.new_chat_member.status
        old_status = event.old_chat_member.status

        # Проверяем, является ли пользователь администратором
        try:
            member = await bot.get_chat_member(chat_id, admin_id)
            if member.status not in [
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ]:
                logger.warning(
                    f"Пользователь {admin_id} не является администратором в чате {chat_id}"
                )
                return
        except TelegramForbiddenError as e:
            logger.warning(
                f"Не удалось проверить статус администратора {admin_id} в чате {chat_id}: {e}"
            )
            return

        if new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            if old_status in [
                ChatMemberStatus.LEFT,
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.KICKED,
            ]:
                logger.info(
                    f"Бот стал администратором в чате {chat_id}, добавил {admin_id}"
                )
                group_admin_data = GroupAdminCreate(chat_id=chat_id, user_id=admin_id)
                await GroupAdminRepository.create_group_admin(
                    session=session, group_admin_data=group_admin_data
                )
                logger.info(f"Сохранен администратор {admin_id} для чата {chat_id}")
        elif new_status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
        ]:
            logger.info(f"Бот потерял права администратора в чате {chat_id}")
            if await GroupAdminRepository.delete_group_admin(session, chat_id):
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=GROUP_ADMIN_REMOVED,
                    )
                except TelegramForbiddenError as e:
                    logger.warning(
                        f"Не удалось отправить сообщение в чат {chat_id}: {e}"
                    )
        else:
            logger.info(
                f"Изменение прав бота не подходит под критерий. Статусы: {old_status} -> {new_status}"
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке события my_chat_member: {e}", exc_info=True)
