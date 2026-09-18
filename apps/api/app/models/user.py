import uuid
from datetime import datetime, time

from sqlalchemy import String, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64))
    reminder_local_time: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
