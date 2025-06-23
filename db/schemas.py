from pydantic import BaseModel
from datetime import date


class GroupAdminCreate(BaseModel):
    chat_id: int
    user_id: int


class UserCreate(BaseModel):
    telegram_id: int
    username: str | None
    name: str
    birth_date: date | None
    registered_from_group_id: int


class UserResponse(BaseModel):
    telegram_id: int
    username: str | None
    name: str
    birth_date: date | None
    registered_from_group_id: int
