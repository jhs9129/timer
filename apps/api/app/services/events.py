import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.services import clock


def emit(
    db: AsyncSession,
    event_type: str,
    *,
    subject_type: str,
    subject_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    """Append an event in the caller's transaction. Every state change must call this."""
    event = Event(
        event_type=event_type,
        actor_id=actor_id,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=payload or {},
        occurred_at=occurred_at or clock.now(),
    )
    db.add(event)
    return event
