import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_occurred_at", "occurred_at"),
        Index("ix_events_type_occurred_at", "event_type", "occurred_at"),
        Index("ix_events_actor_occurred_at", "actor_id", "occurred_at"),
        Index("ix_events_subject", "subject_type", "subject_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(48))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime]
    ingested_at: Mapped[datetime] = mapped_column(server_default=func.now())
