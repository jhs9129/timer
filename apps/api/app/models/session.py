import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_id

MODE_STOPWATCH = "stopwatch"
MODE_COUNTDOWN = "countdown"
MODES = {MODE_STOPWATCH, MODE_COUNTDOWN}

STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_ENDED = "ended"
STATUS_COMPLETED = "completed"
STATUS_ABANDONED = "abandoned"
ACTIVE_STATUSES = (STATUS_RUNNING, STATUS_PAUSED)

PAUSE_USER = "user"
PAUSE_IDLE = "idle"
PAUSE_TIMEOUT = "timeout"
PAUSE_REASONS = {PAUSE_USER, PAUSE_IDLE}

END_STOP = "stop"


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        Index(
            "ix_focus_sessions_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('running', 'paused')"),
        ),
        Index("ix_focus_sessions_user_local_date", "user_id", "local_date"),
        Index("ix_focus_sessions_status_updated_at", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    target_seconds: Mapped[int | None] = mapped_column(Integer)
    intent: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16))
    pause_reason: Mapped[str | None] = mapped_column(String(16))
    local_date: Mapped[date]
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
    focused_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    segments: Mapped[list["SessionSegment"]] = relationship(
        back_populates="session",
        order_by="SessionSegment.started_at",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    @property
    def open_segment(self) -> "SessionSegment | None":
        for segment in self.segments:
            if segment.ended_at is None:
                return segment
        return None

    def closed_seconds(self) -> int:
        total = 0
        for segment in self.segments:
            if segment.ended_at is not None:
                total += int((segment.ended_at - segment.started_at).total_seconds())
        return total


class SessionSegment(Base):
    __tablename__ = "session_segments"
    __table_args__ = (
        Index(
            "ix_session_segments_one_open_per_session",
            "session_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index(
            "ix_session_segments_open_last_seen",
            "last_seen_at",
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("focus_sessions.id"), index=True)
    started_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
    end_reason: Mapped[str | None] = mapped_column(String(16))

    session: Mapped[FocusSession] = relationship(back_populates="segments")
