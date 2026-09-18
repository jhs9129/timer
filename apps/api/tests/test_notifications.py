from datetime import UTC, datetime, timedelta
from typing import Any, cast

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import PushSubscription, ScheduledNotification
from app.services.senders import RecordingSender, Senders, SendResult
from tests.conftest import DEFAULT_START, FakeClock
from tests.helpers import event_types, focus, focus_and_stop, retro, start, stop

HEADERS = {"X-Cron-Secret": "test-cron-secret"}
ENDPOINT = "https://push.example/abc"
SUB: dict[str, Any] = {"endpoint": ENDPOINT, "keys": {"p256dh": "p", "auth": "a"}}


async def _rows(db: AsyncSession, kind: str | None = None) -> list[ScheduledNotification]:
    # populate_existing: the test session's identity map must not hide server-side changes.
    stmt = (
        select(ScheduledNotification)
        .order_by(ScheduledNotification.created_at)
        .execution_options(populate_existing=True)
    )
    if kind:
        stmt = stmt.where(ScheduledNotification.kind == kind)
    return list((await db.execute(stmt)).scalars().all())


async def _dispatch(client: AsyncClient) -> dict[str, int]:
    res = await client.post("/internal/dispatch", headers=HEADERS)
    assert res.status_code == 200, res.text
    return cast(dict[str, int], res.json())


def _push(senders: Senders) -> RecordingSender:
    return cast(RecordingSender, senders.push)


def _email(senders: Senders) -> RecordingSender:
    return cast(RecordingSender, senders.email)


# ----------------------------------------------------------------- scheduling


async def test_countdown_schedules_and_stop_cancels(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    body = await start(client, mode="countdown", target_seconds=1500)
    rows = await _rows(db, "countdown_reached")
    assert len(rows) == 1
    assert rows[0].due_at == fake_clock.current + timedelta(seconds=1500)
    assert rows[0].channel == "push" and rows[0].pending
    await focus(client, fake_clock, body["id"], 120)
    await stop(client, body["id"])
    rows = await _rows(db, "countdown_reached")
    assert rows[0].cancelled_at is not None
    assert "notification.cancelled" in await event_types(db)


async def test_stop_schedules_retro_pending_and_retro_cancels(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    sid = await focus_and_stop(client, fake_clock, 5)
    rows = await _rows(db, "retro_pending")
    assert len(rows) == 1 and rows[0].due_at == fake_clock.current + timedelta(minutes=30)
    await retro(client, sid)
    rows = await _rows(db, "retro_pending")
    assert rows[0].cancelled_at is not None


async def test_abandon_cancels_everything(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    await focus_and_stop(client, fake_clock, 5)
    fake_clock.set(datetime(2026, 9, 17, 20, 0, tzinfo=UTC))  # next local day, past grace
    await _dispatch(client)
    rows = await _rows(db)
    assert rows and all(r.cancelled_at is not None for r in rows)


# ----------------------------------------------------------------- subscriptions


async def test_subscription_upsert_and_delete(client: AsyncClient, db: AsyncSession) -> None:
    res = await client.post("/push/subscriptions", json=SUB)
    assert res.status_code == 201
    again = await client.post(
        "/push/subscriptions", json={**SUB, "keys": {"p256dh": "p2", "auth": "a2"}}
    )
    assert again.status_code == 201 and again.json()["id"] == res.json()["id"]
    subs = list((await db.execute(select(PushSubscription))).scalars().all())
    assert len(subs) == 1 and subs[0].p256dh == "p2"
    prefs = await client.get("/me/notifications")
    assert prefs.json()["push"] is True
    gone = await client.delete("/push/subscriptions", params={"endpoint": ENDPOINT})
    assert gone.status_code == 204
    await db.refresh(subs[0])
    assert subs[0].revoked_at is not None
    missing = await client.delete("/push/subscriptions", params={"endpoint": "nope"})
    assert missing.status_code == 404


# ----------------------------------------------------------------- delivery


async def test_due_push_is_delivered_once(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock, senders: Senders
) -> None:
    await client.post("/push/subscriptions", json=SUB)
    body = await start(client, mode="countdown", target_seconds=120)
    fake_clock.advance(60)
    await client.post(f"/sessions/{body['id']}/heartbeat")
    assert (await _dispatch(client))["sent"] == 0  # not due yet
    assert _push(senders).calls == []
    fake_clock.advance(60)
    await client.post(f"/sessions/{body['id']}/heartbeat")
    counts = await _dispatch(client)
    assert counts["sent"] == 1 and counts["failed"] == 0
    call = _push(senders).calls[0]
    assert call["payload"]["title"] == "목표 시간에 도달했어요"
    assert call["subscription"].endpoint == ENDPOINT
    row = (await _rows(db, "countdown_reached"))[0]
    assert row.sent_at == fake_clock.current
    assert (await _dispatch(client))["sent"] == 0  # idempotent
    assert len(_push(senders).calls) == 1
    sent_events = [e for e in await event_types(db) if e == "notification.sent"]
    assert len(sent_events) == 1


async def test_failed_push_retries_up_to_max_attempts(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock, senders: Senders
) -> None:
    _push(senders).result = SendResult(ok=False, error="boom")
    await client.post("/push/subscriptions", json=SUB)
    await focus_and_stop(client, fake_clock, 1)  # retro_pending due in 30 min
    fake_clock.advance(31 * 60)
    for _ in range(7):
        await _dispatch(client)
    row = (await _rows(db, "retro_pending"))[0]
    assert row.sent_at is None and row.attempts == 5 and row.last_error == "boom"
    assert len(_push(senders).calls) == 5


async def test_gone_endpoint_revokes_subscription(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock, senders: Senders
) -> None:
    _push(senders).result = SendResult(ok=False, error="410 gone", gone=True)
    await client.post("/push/subscriptions", json=SUB)
    await focus_and_stop(client, fake_clock, 1)
    fake_clock.advance(31 * 60)
    counts = await _dispatch(client)
    assert counts["failed"] == 1
    sub = (await db.execute(select(PushSubscription))).scalar_one()
    assert sub.revoked_at is not None
    counts = await _dispatch(client)  # no subscription left: final failure, no retry
    assert counts["failed"] == 1
    row = (await _rows(db, "retro_pending"))[0]
    assert row.last_error == "no subscription" and row.attempts == 5
    assert (await _dispatch(client))["failed"] == 0


# ----------------------------------------------------------------- recurring


async def test_daily_reminder_fires_once_per_day(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock, senders: Senders
) -> None:
    await client.post("/push/subscriptions", json=SUB)
    res = await client.patch("/me/notifications", json={"reminder_local_time": "10:00"})
    assert res.status_code == 200 and res.json()["reminder_local_time"] == "10:00:00"
    fake_clock.set(DEFAULT_START)  # 10:00 KST
    counts = await _dispatch(client)
    assert counts["scheduled"] == 1 and counts["sent"] == 1
    fake_clock.advance(120)
    counts = await _dispatch(client)
    assert counts["scheduled"] == 0 and counts["sent"] == 0
    fake_clock.set(DEFAULT_START + timedelta(days=1, minutes=3))
    counts = await _dispatch(client)
    assert counts["scheduled"] == 1 and counts["sent"] == 1
    assert len(_push(senders).calls) == 2
    assert _push(senders).calls[0]["payload"]["title"] == "오늘의 몰두"


async def test_weekly_summary_email_for_consenting_users(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock, senders: Senders
) -> None:
    # 2026-09-17 is a Thursday. Earn on Thu/Fri, then tick on Monday 08:00 KST.
    await focus_and_stop(client, fake_clock, 30)
    await retro(client, (await focus_and_stop(client, fake_clock, 10)))
    fake_clock.advance(24 * 3600)
    await retro(client, (await focus_and_stop(client, fake_clock, 20)))
    monday = datetime(2026, 9, 20, 23, 0, tzinfo=UTC)  # 2026-09-21 08:00 KST
    fake_clock.set(monday)
    assert (await _dispatch(client))["scheduled"] == 0  # no consent yet
    await client.patch("/me/notifications", json={"email_weekly": True})
    counts = await _dispatch(client)
    assert counts["scheduled"] == 1 and counts["sent"] == 1
    call: dict[str, Any] = _email(senders).calls[0]
    assert "지난주 몰두 요약" in call["subject"]
    assert "0시간 30분" in call["text"]  # only completed sessions: 10 + 20 minutes
    assert "완료한 세션: 2회" in call["text"]
    assert "얻은 코인: 30" in call["text"]
    fake_clock.advance(300)
    assert (await _dispatch(client))["scheduled"] == 0  # dedupe within the week


# ----------------------------------------------------------------- prefs


async def test_bad_reminder_time_is_422(client: AsyncClient) -> None:
    res = await client.patch("/me/notifications", json={"reminder_local_time": "25:99"})
    assert res.status_code == 422


async def test_revoking_push_consent_cancels_pending_and_revokes_subs(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    await client.post("/push/subscriptions", json=SUB)
    await focus_and_stop(client, fake_clock, 1)  # retro_pending scheduled
    res = await client.patch("/me/notifications", json={"push": False})
    assert res.status_code == 200 and res.json()["push"] is False
    row = (await _rows(db, "retro_pending"))[0]
    assert row.cancelled_at is not None
    sub = (await db.execute(select(PushSubscription))).scalar_one()
    assert sub.revoked_at is not None
    assert "consent.changed" in await event_types(db)
