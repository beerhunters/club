# db/models/group_admin.py
from sqlalchemy import Column, BigInteger, DateTime
from sqlalchemy.orm import declarative_base
import pendulum

Base = declarative_base()


class GroupAdmin(Base):
    __tablename__ = "group_admins"

    chat_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    added_at = Column(DateTime, default=pendulum.now)
