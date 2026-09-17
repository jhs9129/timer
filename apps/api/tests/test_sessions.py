from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeClock
from tests.helpers import event_types, focus, start, stop


async def test_start_creates_running_session_with_open_segment(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    body = await start(client, intent="write the spec")
    assert body["status"] == "running"
    assert body["running_since"] == fake_clock.current.isoformat().replace("+00:00", "Z")
    assert body["focused_seconds"] == 0
    assert body["local_date"] == "2026-09-17"
    assert await event_types(db, body["id"]) == ["session.started"]


async def test_second_start_conflicts_while_active(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    await start(client)
    res = await client.post("/sessions", json={"mode": "stopwatch"})
    assert res.status_code == 409


async def test_countdown_requires_target(client: AsyncClient, fake_clock: FakeClock) -> None:
    res = await client.post("/sessions", json={"mode": "countdown"})
    assert res.status_code == 422


async def test_stop_after_60s_counts_60s(client: AsyncClient, fake_clock: FakeClock) -> None:
    body = await start(client)
    fake_clock.advance(30)
    await client.post(f"/sessions/{body['id']}/heartbeat")
    fake_clock.advance(30)
    ended = await stop(client, body["id"])
    assert ended["status"] == "ended"
    assert ended["focused_seconds"] == 60
    assert ended["running_since"] is None


async def test_pause_freezes_time_and_resume_continues(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    body = await start(client)
    sid = body["id"]
    fake_clock.advance(40)
    paused = await client.post(f"/sessions/{sid}/pause", json={"reason": "user"})
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["pause_reason"] == "user"
    fake_clock.advance(600)
    current = await client.get("/sessions/current")
    assert current.json()["focused_seconds"] == 40
    resumed = await client.post(f"/sessions/{sid}/resume")
    assert resumed.json()["status"] == "running"
    fake_clock.advance(20)
    ended = await stop(client, sid)
    assert ended["focused_seconds"] == 60
    assert await event_types(db, sid) == [
        "session.started",
        "session.paused",
        "session.resumed",
        "session.stopped",
    ]


async def test_heartbeat_timeout_pauses_and_counts_until_last_seen(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    body = await start(client)
    sid = body["id"]
    fake_clock.advance(30)
    await client.post(f"/sessions/{sid}/heartbeat")
    fake_clock.advance(200)  # > 90s timeout
    current = await client.get("/sessions/current")
    assert current.status_code == 200
    assert current.json()["status"] == "paused"
    assert current.json()["pause_reason"] == "timeout"
    assert current.json()["focused_seconds"] == 30
    late = await client.post(f"/sessions/{sid}/heartbeat")
    assert late.status_code == 200
    assert late.json()["status"] == "paused"


async def test_ended_session_rejects_further_transitions(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    body = await start(client)
    sid = body["id"]
    await stop(client, sid)
    for path, payload in [
        ("heartbeat", None),
        ("pause", {"reason": "user"}),
        ("resume", None),
        ("stop", None),
    ]:
        res = await client.post(f"/sessions/{sid}/{path}", json=payload)
        assert res.status_code == 409, path


async def test_local_date_before_boundary_is_previous_day(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    fake_clock.set(datetime(2026, 9, 16, 18, 59, tzinfo=UTC))  # 03:59 Asia/Seoul on 09-17
    body = await start(client)
    assert body["local_date"] == "2026-09-16"


async def test_other_users_session_is_not_found(
    client: AsyncClient, other_client: AsyncClient, fake_clock: FakeClock
) -> None:
    body = await start(client)
    res = await other_client.post(f"/sessions/{body['id']}/stop")
    assert res.status_code == 404


async def test_current_is_204_without_active_session(client: AsyncClient) -> None:
    res = await client.get("/sessions/current")
    assert res.status_code == 204


async def test_list_by_date_returns_sessions_and_totals(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    first = await start(client)
    await focus(client, fake_clock, first["id"], 120)
    await stop(client, first["id"])
    second = await start(client)
    await focus(client, fake_clock, second["id"], 60)
    await stop(client, second["id"])
    res = await client.get("/sessions", params={"date": "2026-09-17"})
    assert res.status_code == 200
    day = res.json()
    assert [s["id"] for s in day["sessions"]] == [first["id"], second["id"]]
    assert day["focused_seconds"] == 180
    assert day["coins_earned"] == 0
    empty = await client.get("/sessions", params={"date": "2026-09-16"})
    assert empty.json()["sessions"] == []
