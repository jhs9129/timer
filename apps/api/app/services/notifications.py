import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.base import new_id
from app.models.notification import (
    CHANNEL_EMAIL,
    CHANNEL_PUSH,
    CONSENT_EMAIL_WEEKLY,
    CONSENT_PUSH,
    KIND_DAILY,
    KIND_WEEKLY,
    Consent,
    PushSubscription,
    ScheduledNotification,
)
from app.models.user import User
from app.services import clock
from app.services.events import emit
from app.services.localdate import local_date_for
from app.services.senders import Senders
from app.services.summary import render_weekly, weekly_summary

# ---------------------------------------------------------------- scheduling


def schedule(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    channel: str,
    due_at: datetime,
    payload: dict[str, Any] | None = None,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
) -> ScheduledNotification:
    row = ScheduledNotification(
        id=new_id(),  # assigned now so the event below can reference it before flush
        user_id=user_id,
        kind=kind,
        channel=channel,
        due_at=due_at,
        payload=payload or {},
        ref_type=ref_type,
        ref_id=ref_id,
        dedupe_key=dedupe_key,
        created_at=clock.now(),
    )
    db.add(row)
    emit(
        db,
        "notification.scheduled",
        subject_type="scheduled_notification",
        subject_id=row.id,
        actor_id=user_id,
        payload={"kind": kind, "channel": channel, "due_at": due_at.isoformat()},
    )
    return row


async def has_dedupe(db: AsyncSession, key: str) -> bool:
    result = await db.execute(
        select(ScheduledNotification.id).where(ScheduledNotification.dedupe_key == key)
    )
    return result.scalar_one_or_none() is not None


async def _pending_rows(
    db: AsyncSession,
    *,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    kinds: tuple[str, ...] | None = None,
    channel: str | None = None,
) -> list[ScheduledNotification]:
    stmt = select(ScheduledNotification).where(
        ScheduledNotification.sent_at.is_(None), ScheduledNotification.cancelled_at.is_(None)
    )
    if ref_type is not None:
        stmt = stmt.where(ScheduledNotification.ref_type == ref_type)
    if ref_id is not None:
        stmt = stmt.where(ScheduledNotification.ref_id == ref_id)
    if user_id is not None:
        stmt = stmt.where(ScheduledNotification.user_id == user_id)
    if kinds:
        stmt = stmt.where(ScheduledNotification.kind.in_(kinds))
    if channel is not None:
        stmt = stmt.where(ScheduledNotification.channel == channel)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _cancel(db: AsyncSession, row: ScheduledNotification, reason: str, now: datetime) -> None:
    row.cancelled_at = now
    emit(
        db,
        "notification.cancelled",
        subject_type="scheduled_notification",
        subject_id=row.id,
        actor_id=row.user_id,
        payload={"kind": row.kind, "reason": reason},
    )


async def cancel_for_ref(
    db: AsyncSession,
    *,
    ref_type: str,
    ref_id: uuid.UUID,
    reason: str,
    kinds: tuple[str, ...] | None = None,
) -> int:
    now = clock.now()
    rows = await _pending_rows(db, ref_type=ref_type, ref_id=ref_id, kinds=kinds)
    for row in rows:
        _cancel(db, row, reason, now)
    return len(rows)


async def cancel_pending_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    reason: str,
    channel: str | None = None,
    kinds: tuple[str, ...] | None = None,
) -> int:
    now = clock.now()
    rows = await _pending_rows(db, user_id=user_id, channel=channel, kinds=kinds)
    for row in rows:
        _cancel(db, row, reason, now)
    return len(rows)


# ---------------------------------------------------------------- consents


async def has_consent(db: AsyncSession, user_id: uuid.UUID, kind: str) -> bool:
    result = await db.execute(
        select(Consent)
        .where(Consent.user_id == user_id, Consent.kind == kind)
        .order_by(Consent.granted_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    return latest is not None and latest.revoked_at is None


async def set_consent(db: AsyncSession, user: User, kind: str, granted: bool) -> bool:
    """Returns True if the state changed."""
    current = await has_consent(db, user.id, kind)
    if current == granted:
        return False
    now = clock.now()
    if granted:
        db.add(Consent(user_id=user.id, kind=kind, granted_at=now, revoked_at=None))
    else:
        result = await db.execute(
            select(Consent).where(
                Consent.user_id == user.id, Consent.kind == kind, Consent.revoked_at.is_(None)
            )
        )
        for row in result.scalars().all():
            row.revoked_at = now
    emit(
        db,
        "consent.changed",
        subject_type="user",
        subject_id=user.id,
        actor_id=user.id,
        payload={"kind": kind, "granted": granted},
    )
    return True


# ---------------------------------------------------------------- push subscriptions


async def active_subscriptions(db: AsyncSession, user_id: uuid.UUID) -> list[PushSubscription]:
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.revoked_at.is_(None)
        )
    )
    return list(result.scalars().all())


async def upsert_subscription(
    db: AsyncSession, *, user: User, endpoint: str, p256dh: str, auth: str, user_agent: str | None
) -> PushSubscription:
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    sub = result.scalar_one_or_none()
    now = clock.now()
    if sub is None:
        sub = PushSubscription(
            user_id=user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=user_agent,
            created_at=now,
        )
        db.add(sub)
    else:
        sub.user_id, sub.p256dh, sub.auth = user.id, p256dh, auth
        sub.user_agent = user_agent
        sub.revoked_at = None
    await db.flush()
    emit(
        db,
        "push_subscription.changed",
        subject_type="push_subscription",
        subject_id=sub.id,
        actor_id=user.id,
        payload={"action": "add"},
    )
    return sub


def _revoke(db: AsyncSession, sub: PushSubscription, action: str, now: datetime) -> None:
    sub.revoked_at = now
    emit(
        db,
        "push_subscription.changed",
        subject_type="push_subscription",
        subject_id=sub.id,
        actor_id=sub.user_id,
        payload={"action": action},
    )


async def remove_subscription(db: AsyncSession, *, user: User, endpoint: str) -> bool:
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == user.id,
            PushSubscription.revoked_at.is_(None),
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return False
    _revoke(db, sub, "remove", clock.now())
    return True


async def revoke_all_subscriptions(db: AsyncSession, user_id: uuid.UUID) -> int:
    now = clock.now()
    subs = await active_subscriptions(db, user_id)
    for sub in subs:
        _revoke(db, sub, "revoke", now)
    return len(subs)


# ---------------------------------------------------------------- recurring


def _in_window(local: datetime, hour: int, minute: int, window_minutes: int) -> bool:
    start = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return start <= local < start + timedelta(minutes=window_minutes)


async def schedule_recurring(db: AsyncSession, now: datetime, limit: int) -> int:
    """Create due rows for daily reminders and weekly summaries. Idempotent via dedupe_key."""
    settings = get_settings()
    created = 0
    users = await db.execute(select(User))
    for user in users.scalars().all():
        if created >= limit:
            break
        local = now.astimezone(ZoneInfo(user.timezone))
        today: date = local_date_for(now, user.timezone, settings.day_boundary_hour)

        reminder = user.reminder_local_time
        if (
            reminder is not None
            and _in_window(local, reminder.hour, reminder.minute, settings.reminder_window_minutes)
            and await has_consent(db, user.id, CONSENT_PUSH)
        ):
            key = f"daily:{user.id}:{today.isoformat()}"
            if not await has_dedupe(db, key):
                schedule(
                    db,
                    user_id=user.id,
                    kind=KIND_DAILY,
                    channel=CHANNEL_PUSH,
                    due_at=now,
                    payload={"title": "오늘의 몰두", "body": "짧게라도 시작해 볼까요?", "url": "/"},
                    dedupe_key=key,
                )
                created += 1

        if (
            local.weekday() == settings.weekly_summary_weekday
            and _in_window(local, settings.weekly_summary_hour, 0, settings.reminder_window_minutes)
            and await has_consent(db, user.id, CONSENT_EMAIL_WEEKLY)
        ):
            iso_year, iso_week, _ = local.date().isocalendar()
            key = f"weekly:{user.id}:{iso_year}-W{iso_week:02d}"
            if not await has_dedupe(db, key):
                summary = await weekly_summary(db, user.id, local.date())
                schedule(
                    db,
                    user_id=user.id,
                    kind=KIND_WEEKLY,
                    channel=CHANNEL_EMAIL,
                    due_at=now,
                    payload={"summary": summary.as_payload()},
                    dedupe_key=key,
                )
                created += 1
    return created


# ---------------------------------------------------------------- delivery


async def deliver_due(
    db: AsyncSession, senders: Senders, now: datetime, limit: int
) -> tuple[int, int]:
    settings = get_settings()
    result = await db.execute(
        select(ScheduledNotification, User)
        .join(User, User.id == ScheduledNotification.user_id)
        .where(
            ScheduledNotification.due_at <= now,
            ScheduledNotification.sent_at.is_(None),
            ScheduledNotification.cancelled_at.is_(None),
            ScheduledNotification.attempts < settings.notification_max_attempts,
        )
        .order_by(ScheduledNotification.due_at)
        .limit(limit)
    )
    sent = failed = 0
    for row, user in result.all():
        ok, error = await _deliver_one(db, senders, row, user, now)
        if ok:
            row.sent_at = now
            row.last_error = None
            sent += 1
        else:
            row.attempts += 1
            row.last_error = error
            failed += 1
        emit(
            db,
            "notification.sent",
            subject_type="scheduled_notification",
            subject_id=row.id,
            actor_id=None,
            payload={"kind": row.kind, "channel": row.channel, "ok": ok, "error": error},
            occurred_at=now,
        )
    return sent, failed


async def _deliver_one(
    db: AsyncSession, senders: Senders, row: ScheduledNotification, user: User, now: datetime
) -> tuple[bool, str | None]:
    settings = get_settings()
    if row.channel == CHANNEL_EMAIL:
        subject, text, html = render_weekly(user.display_name, row.payload.get("summary", {}))
        res = await senders.email.send(to=user.email, subject=subject, text=text, html=html)
        return res.ok, res.error

    subs = await active_subscriptions(db, user.id)
    if not subs:
        row.attempts = settings.notification_max_attempts - 1  # final failure, no retries
        return False, "no subscription"
    errors: list[str] = []
    any_ok = False
    for sub in subs:
        res = await senders.push.send(sub, row.payload)
        if res.ok:
            any_ok = True
        else:
            errors.append(res.error or "unknown")
            if res.gone:
                _revoke(db, sub, "revoke", now)
    if any_ok:
        return True, None
    return False, "; ".join(errors)[:250]
