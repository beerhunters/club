from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.fsm.registration import Registration
from db.models.user import User
from db.services.user import save_user
from bot.logger import setup_logger
from datetime import datetime

router = Router()
logger = setup_logger("registration")


@router.message(Registration.name)
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.birth_date)
    await message.answer(
        "Когда у тебя день рождения? (ДД.ММ.ГГГГ, ДД.ММ или можно пропустить)"
    )


@router.message(Registration.birth_date)
async def get_birth_date(message: Message, state: FSMContext, session: AsyncSession):
    raw = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username
    birth_date = None

    if raw.lower() not in ["-", "нет", "пропустить"]:
        try:
            if raw.count(".") == 1:
                birth_date = datetime.strptime(raw, "%d.%m").replace(year=1900).date()
            elif raw.count(".") == 2:
                birth_date = datetime.strptime(raw, "%d.%m.%Y").date()
            else:
                raise ValueError
        except ValueError:
            await message.answer(
                "Формат неверный. Введи дату в формате ДД.ММ.ГГГГ или ДД.ММ, или напиши «пропустить»."
            )
            return

    user = User(
        telegram_id=user_id,
        username=username,
        name=data["name"],
        birth_date=birth_date,
        registered_from_group_id=data["group_id"],
    )
    await save_user(session, user)
    await message.answer("Спасибо! Ты зарегистрирован ✅")
    await state.clear()
    logger.info(f"Registered user {user_id}: {user}")
