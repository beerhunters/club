from sqlalchemy import Column, String, BigInteger, Date, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

from db.database import Base


class User(Base):
    __tablename__ = "users"
    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String(64), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    birth_date = Column(Date, nullable=True)
    registered_from_group_id = Column(BigInteger, nullable=False, index=True)
    __table_args__ = ({"schema": "public"},)


class GroupAdmin(Base):
    __tablename__ = "group_admins"
    chat_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), default=func.now())
    __table_args__ = ({"schema": "public"},)
