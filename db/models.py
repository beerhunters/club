from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Date,
    DateTime,
    func,
    ForeignKey,
    Index,
)

from db.database import Base


class GroupAdmin(Base):
    __tablename__ = "group_admins"
    chat_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), default=func.now())
    __table_args__ = (
        Index("idx_group_admin_chat_user", "chat_id", "user_id"),
        {"schema": "public"},
    )


class User(Base):
    __tablename__ = "users"
    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String(64), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    birth_date = Column(Date, nullable=True)
    registered_from_group_id = Column(
        BigInteger,
        ForeignKey("public.group_admins.chat_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    registered_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    __table_args__ = (
        Index("idx_user_group_registered", "registered_from_group_id", "registered_at"),
        {"schema": "public"},
    )
