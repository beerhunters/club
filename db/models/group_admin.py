# db/models/group_admin.py
from sqlalchemy import Column, BigInteger, DateTime, Index
from sqlalchemy.sql import func

from db.database import Base


class GroupAdmin(Base):
    __tablename__ = "group_admins"

    chat_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        Index("ix_group_admin_chat_user", "chat_id", "user_id", unique=True),
    )
