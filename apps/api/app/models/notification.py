import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, SmallInteger, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id

CONSENT_PUSH = "push"
CONSENT_EMAIL_WEEKLY = "email_weekly"
CONSENT_KINDS = {CONSENT_PUSH, CONSENT_EMAIL_WEEKLY}

KIND_COUNTDOWN = "countdown_reached"
KIND_RETRO_PENDING = "retro_pending"
KIND_DAILY = "daily_reminder"
KIND_WEEKLY = "weekly_summary"

CHANNEL_PUSH = "push"
CHANNEL_EMAIL = "email"


class Consent(Base):
    __tablename__ = "consents"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(primary_key=True)
    revoked_at: Mapped[datetime | None]


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(1024), unique=True)
    p256dh: Mapped[str] = mapped_column(String(256))
    auth: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]


class ScheduledNotification(Base):
    __tablename__ = "scheduled_notifications"
    __table_args__ = (
        Index(
            "ix_scheduled_notifications_pending_due",
            "due_at",
            postgresql_where=text("sent_at IS NULL AND cancelled_at IS NULL"),
        ),
        Index("ix_scheduled_notifications_ref", "ref_type", "ref_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    channel: Mapped[str] = mapped_column(String(8))
    due_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    dedupe_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    sent_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    last_error: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime]

    @property
    def pending(self) -> bool:
        return self.sent_at is None and self.cancelled_at is None
