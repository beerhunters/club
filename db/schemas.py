from pydantic import BaseModel
from datetime import date, datetime, time
from typing import Optional


class GroupAdminCreate(BaseModel):
    chat_id: int
    user_id: int


class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str]
    name: str
    birth_date: Optional[date]
    registered_from_group_id: int


class UserResponse(BaseModel):
    telegram_id: int
    username: str | None
    name: str
    birth_date: date | None
    registered_from_group_id: int
    registered_at: datetime


class EventCreate(BaseModel):
    name: str
    event_date: date
    event_time: time
    latitude: Optional[float]
    longitude: Optional[float]
    location_name: Optional[str]
    description: Optional[str]
    image_file_id: Optional[str]
    has_beer_choice: bool
    beer_option_1: Optional[str]
    beer_option_2: Optional[str]
    created_by: int
    chat_id: int
    celery_task_id: Optional[str]
    notification_time: Optional[datetime]


class EventResponse(BaseModel):
    id: int
    name: str
    event_date: date
    event_time: str
    latitude: Optional[float]
    longitude: Optional[float]
    location_name: Optional[str]
    description: Optional[str]
    image_file_id: Optional[str]
    has_beer_choice: bool
    beer_option_1: Optional[str]
    beer_option_2: Optional[str]
    created_by: int
    chat_id: int
    created_at: datetime
    notification_time: datetime | None


class BeerSelectionCreate(BaseModel):
    user_id: int
    event_id: int
    chat_id: int
    beer_choice: str


class BeerSelectionResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    chat_id: int
    beer_choice: str
    selected_at: datetime

    class Config:
        from_attributes = True
