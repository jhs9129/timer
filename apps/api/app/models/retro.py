import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, SmallInteger, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id

INTENT_MATCHES = {"yes", "partly", "no"}


class Retrospective(Base):
    __tablename__ = "retrospectives"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("focus_sessions.id"), unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    mood: Mapped[int] = mapped_column(SmallInteger)
    intent_match: Mapped[str | None] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(String(300))
    submitted_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_tags_owner_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime]


class RetroTag(Base):
    __tablename__ = "retro_tags"

    retro_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("retrospectives.id"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tags.id"), primary_key=True)
