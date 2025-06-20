# db/schemas/group_admin.py
from pydantic import BaseModel
from datetime import datetime


class GroupAdminCreate(BaseModel):
    chat_id: int
    user_id: int
