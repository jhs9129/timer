from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeClock
from tests.helpers import event_types, focus, start, stop

HEADERS = {"X-Cron-Secret": "test-cron-secret"}


async def _dispatch(client: AsyncClient) -> dict[str, int]:
    res = await client.post("/internal/dispatch", headers=HEADERS)
    assert res.status_code == 200, res.text
    data: dict[str, int] = res.json()
    return data


async def test_dispatch_rejects_bad_secret(client: AsyncClient, fake_clock: FakeClock) -> None:
    body = await start(client)
    fake_clock.advance(500)
    res = await client.post("/internal/dispatch", headers={"X-Cron-Secret": "nope"})
    assert res.status_code == 401
    res2 = await client.post("/internal/dispatch")
    assert res2.status_code == 401
    # Nothing changed on the server side beyond the lazy check the read itself triggers.
    current = await client.get("/sessions/current")
    assert current.json()["id"] == body["id"]


async def test_dispatch_times_out_stale_running_sessions(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    body = await start(client)
    fake_clock.advance(30)
    await client.post(f"/sessions/{body['id']}/heartbeat")
    fake_clock.advance(120)
    counts = await _dispatch(client)
    assert (counts["timed_out"], counts["abandoned"]) == (1, 0)
    current = await client.get("/sessions/current")
    assert current.json()["status"] == "paused"
    assert current.json()["pause_reason"] == "timeout"
    assert current.json()["focused_seconds"] == 30


async def test_dispatch_abandons_ended_session_after_boundary_and_grace(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    body = await start(client)
    await focus(client, fake_clock, body["id"], 600)
    await stop(client, body["id"])
    fake_clock.set(datetime(2026, 9, 17, 20, 0, tzinfo=UTC))  # 05:00 next local day
    counts = await _dispatch(client)
    assert (counts["timed_out"], counts["abandoned"]) == (0, 1)
    day = await client.get("/sessions", params={"date": "2026-09-17"})
    session = day.json()["sessions"][0]
    assert session["status"] == "abandoned"
    assert session["focused_seconds"] == 600
    assert (await event_types(db, body["id"]))[-1] == "session.abandoned"
    # Idempotent: a second tick finds nothing.
    again = await _dispatch(client)
    assert (again["timed_out"], again["abandoned"]) == (0, 0)


async def test_dispatch_keeps_live_running_session_across_boundary(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    fake_clock.set(datetime(2026, 9, 17, 18, 30, tzinfo=UTC))  # 03:30 local
    body = await start(client)
    await focus(client, fake_clock, body["id"], 3600)  # heartbeats through the 04:00 boundary
    counts = await _dispatch(client)
    assert (counts["timed_out"], counts["abandoned"]) == (0, 0)
    current = await client.get("/sessions/current")
    assert current.json()["status"] == "running"
    assert current.json()["local_date"] == "2026-09-17"  # started 03:30 local on 09-18


async def test_dispatch_spares_recently_ended_session_past_boundary(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    fake_clock.set(datetime(2026, 9, 16, 18, 50, tzinfo=UTC))  # 03:50 local
    body = await start(client)
    await focus(client, fake_clock, body["id"], 300)
    await stop(client, body["id"])  # 03:55 local, local_date 09-16
    fake_clock.set(
        datetime(2026, 9, 16, 19, 10, tzinfo=UTC)
    )  # 04:10 local: boundary passed, grace not
    counts = await _dispatch(client)
    assert (counts["timed_out"], counts["abandoned"]) == (0, 0)
    fake_clock.set(datetime(2026, 9, 16, 19, 40, tzinfo=UTC))  # 04:40 local: grace passed
    counts = await _dispatch(client)
    assert (counts["timed_out"], counts["abandoned"]) == (0, 1)
