from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    BigInteger,
    Date,
    DateTime,
    func,
    ForeignKey,
    Index,
    Time,
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


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=False)
    event_time = Column(Time, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_name = Column(String(500), nullable=True)
    description = Column(String(1000), nullable=True)
    image_file_id = Column(String, nullable=True)
    has_beer_choice = Column(Boolean, default=False)
    beer_option_1 = Column(String(100), nullable=True)
    beer_option_2 = Column(String(100), nullable=True)
    created_by = Column(BigInteger, nullable=False)
    chat_id = Column(
        BigInteger,
        ForeignKey("public.group_admins.chat_id", ondelete="CASCADE"),
        nullable=False,
    )
    celery_task_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    __table_args__ = (
        Index("idx_event_chat_date", "chat_id", "event_date"),
        {"schema": "public"},
    )


class BeerSelection(Base):
    __tablename__ = "beer_selections"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        BigInteger,
        ForeignKey("public.users.telegram_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id = Column(
        Integer,
        ForeignKey("public.events.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_id = Column(
        BigInteger,
        ForeignKey("public.group_admins.chat_id", ondelete="CASCADE"),
        nullable=False,
    )
    beer_choice = Column(String(100), nullable=False)
    selected_at = Column(DateTime(timezone=True), default=func.now())
    __table_args__ = (
        Index("idx_beer_selection_user_event", "user_id", "event_id", unique=True),
        {"schema": "public"},
    )
