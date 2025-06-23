# db/models/user.py
from sqlalchemy import Column, BigInteger, String, Date, Index
from db.database import Base


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String(64), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    birth_date = Column(Date, nullable=True)
    registered_from_group_id = Column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        Index("ix_users_group_id_username", "registered_from_group_id", "username"),
    )
