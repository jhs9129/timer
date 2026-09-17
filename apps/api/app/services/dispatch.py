from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.session import (
    STATUS_ENDED,
    STATUS_PAUSED,
    STATUS_RUNNING,
    FocusSession,
    SessionSegment,
)
from app.models.user import User
from app.services import clock
from app.services.sessions import abandon, apply_timeout, today_for


async def run_dispatch(db: AsyncSession) -> dict[str, int]:
    """One cron tick. Must finish well inside the 30s cron timeout."""
    settings = get_settings()
    now = clock.now()
    limit = settings.dispatch_batch_size

    stale_before = now - timedelta(seconds=settings.heartbeat_timeout_seconds)
    stale = await db.execute(
        select(FocusSession)
        .join(SessionSegment, SessionSegment.session_id == FocusSession.id)
        .where(
            FocusSession.status == STATUS_RUNNING,
            SessionSegment.ended_at.is_(None),
            SessionSegment.last_seen_at < stale_before,
        )
        .limit(limit)
    )
    timed_out = 0
    for session in stale.scalars().unique().all():
        if apply_timeout(db, session, now):
            timed_out += 1

    grace_before = now - timedelta(seconds=settings.abandon_grace_seconds)
    candidates = await db.execute(
        select(FocusSession, User)
        .join(User, User.id == FocusSession.user_id)
        .where(
            FocusSession.status.in_((STATUS_PAUSED, STATUS_ENDED)),
            FocusSession.updated_at < grace_before,
        )
        .order_by(FocusSession.updated_at)
        .limit(limit)
    )
    abandoned = 0
    for session, user in candidates.all():
        if session.local_date < today_for(user, now):
            abandon(db, session, now=now)
            abandoned += 1

    await db.flush()
    return {"timed_out": timed_out, "abandoned": abandoned}
