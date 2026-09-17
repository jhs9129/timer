import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import Conflict, NotFound, ValidationFailed
from app.models.session import (
    ACTIVE_STATUSES,
    END_STOP,
    MODE_COUNTDOWN,
    MODES,
    PAUSE_REASONS,
    PAUSE_TIMEOUT,
    STATUS_ABANDONED,
    STATUS_ENDED,
    STATUS_PAUSED,
    STATUS_RUNNING,
    FocusSession,
    SessionSegment,
)
from app.models.user import User
from app.services import clock
from app.services.events import emit
from app.services.localdate import local_date_for


def today_for(user: User, now: datetime) -> date:
    return local_date_for(now, user.timezone, get_settings().day_boundary_hour)


async def get_active(db: AsyncSession, user_id: uuid.UUID) -> FocusSession | None:
    result = await db.execute(
        select(FocusSession).where(
            FocusSession.user_id == user_id, FocusSession.status.in_(ACTIVE_STATUSES)
        )
    )
    session = result.scalar_one_or_none()
    if session is not None:
        apply_timeout(db, session, clock.now())
    return session


async def get_owned(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> FocusSession:
    result = await db.execute(
        select(FocusSession).where(FocusSession.id == session_id, FocusSession.user_id == user_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFound("session not found")
    apply_timeout(db, session, clock.now())
    return session


async def list_for_date(db: AsyncSession, user_id: uuid.UUID, day: date) -> list[FocusSession]:
    result = await db.execute(
        select(FocusSession)
        .where(FocusSession.user_id == user_id, FocusSession.local_date == day)
        .order_by(FocusSession.started_at)
    )
    sessions = list(result.scalars().all())
    now = clock.now()
    for session in sessions:
        apply_timeout(db, session, now)
    return sessions


def apply_timeout(db: AsyncSession, session: FocusSession, now: datetime) -> bool:
    """Lazy heartbeat-timeout check. Returns True if the session was paused by it."""
    if session.status != STATUS_RUNNING:
        return False
    segment = session.open_segment
    if segment is None:
        return False
    timeout = timedelta(seconds=get_settings().heartbeat_timeout_seconds)
    if now - segment.last_seen_at <= timeout:
        return False
    _close_segment(segment, at=segment.last_seen_at, reason=PAUSE_TIMEOUT)
    session.status = STATUS_PAUSED
    session.pause_reason = PAUSE_TIMEOUT
    session.updated_at = now
    emit(
        db,
        "session.paused",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=None,
        payload={"reason": PAUSE_TIMEOUT, "focused_seconds_so_far": session.closed_seconds()},
        occurred_at=segment.last_seen_at,
    )
    return True


async def start(
    db: AsyncSession,
    user: User,
    *,
    mode: str,
    target_seconds: int | None,
    intent: str | None,
) -> FocusSession:
    if mode not in MODES:
        raise ValidationFailed("unknown mode")
    if mode == MODE_COUNTDOWN and not target_seconds:
        raise ValidationFailed("countdown requires target_seconds")
    if await get_active(db, user.id) is not None:
        raise Conflict("an active session already exists")
    now = clock.now()
    session = FocusSession(
        user_id=user.id,
        mode=mode,
        target_seconds=target_seconds if mode == MODE_COUNTDOWN else None,
        intent=intent or None,
        status=STATUS_RUNNING,
        local_date=today_for(user, now),
        started_at=now,
        focused_seconds=0,
        created_at=now,
        updated_at=now,
    )
    session.segments.append(SessionSegment(started_at=now, last_seen_at=now))
    db.add(session)
    await db.flush()
    emit(
        db,
        "session.started",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=user.id,
        payload={
            "mode": mode,
            "target_seconds": session.target_seconds,
            "has_intent": session.intent is not None,
        },
    )
    return session


def heartbeat(session: FocusSession) -> FocusSession:
    if session.status in (STATUS_ENDED, "completed", STATUS_ABANDONED):
        raise Conflict("session is no longer active")
    if session.status != STATUS_RUNNING:
        return session  # paused (possibly by timeout): report state, client decides
    segment = session.open_segment
    if segment is None:
        raise Conflict("running session has no open segment")
    now = clock.now()
    segment.last_seen_at = now
    session.updated_at = now
    return session


def pause(db: AsyncSession, session: FocusSession, *, reason: str, actor_id: uuid.UUID) -> None:
    if reason not in PAUSE_REASONS:
        raise ValidationFailed("unknown pause reason")
    if session.status != STATUS_RUNNING:
        raise Conflict("session is not running")
    segment = session.open_segment
    now = clock.now()
    if segment is not None:
        _close_segment(segment, at=now, reason=reason)
    session.status = STATUS_PAUSED
    session.pause_reason = reason
    session.updated_at = now
    emit(
        db,
        "session.paused",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=actor_id,
        payload={"reason": reason, "focused_seconds_so_far": session.closed_seconds()},
    )


def resume(db: AsyncSession, session: FocusSession, *, actor_id: uuid.UUID) -> None:
    if session.status != STATUS_PAUSED:
        raise Conflict("session is not paused")
    now = clock.now()
    last = session.segments[-1] if session.segments else None
    paused_seconds = int((now - last.ended_at).total_seconds()) if last and last.ended_at else 0
    session.segments.append(SessionSegment(started_at=now, last_seen_at=now))
    session.status = STATUS_RUNNING
    session.pause_reason = None
    session.updated_at = now
    emit(
        db,
        "session.resumed",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=actor_id,
        payload={"paused_seconds": paused_seconds},
    )


def stop(db: AsyncSession, session: FocusSession, *, actor_id: uuid.UUID) -> None:
    if session.status not in ACTIVE_STATUSES:
        raise Conflict("session is not active")
    now = clock.now()
    segment = session.open_segment
    if segment is not None:
        _close_segment(segment, at=now, reason=END_STOP)
    session.focused_seconds = session.closed_seconds()
    session.status = STATUS_ENDED
    session.pause_reason = None
    session.ended_at = now
    session.updated_at = now
    emit(
        db,
        "session.stopped",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=actor_id,
        payload={
            "focused_seconds": session.focused_seconds,
            "segment_count": len(session.segments),
        },
    )


def abandon(db: AsyncSession, session: FocusSession, *, now: datetime) -> None:
    last_status = session.status
    segment = session.open_segment
    if segment is not None:
        _close_segment(segment, at=segment.last_seen_at, reason=PAUSE_TIMEOUT)
    session.focused_seconds = session.closed_seconds()
    session.status = STATUS_ABANDONED
    session.pause_reason = None
    session.updated_at = now
    emit(
        db,
        "session.abandoned",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=None,
        payload={"last_status": last_status, "focused_seconds": session.focused_seconds},
        occurred_at=now,
    )


def is_past_grace(session: FocusSession, user: User, now: datetime) -> bool:
    """True when the session's day is over and the retro grace period has elapsed."""
    if session.local_date >= today_for(user, now):
        return False
    grace = timedelta(seconds=get_settings().abandon_grace_seconds)
    return now - session.updated_at > grace


def _close_segment(segment: SessionSegment, *, at: datetime, reason: str) -> None:
    segment.ended_at = at
    segment.end_reason = reason
    if segment.last_seen_at > at:
        segment.last_seen_at = at
