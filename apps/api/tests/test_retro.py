from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import CoinLedger
from tests.conftest import DEFAULT_START, FakeClock
from tests.helpers import event_types, focus_and_stop, retro, start


async def test_retro_completes_session_and_grants_coins(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    sid = await focus_and_stop(client, fake_clock, 10)
    res = await retro(client, sid, mood=4, tags=["deep work", "spec"], note="good")
    assert res["session"]["status"] == "completed"
    assert res["session"]["has_retro"] is True
    assert res["reward"] == {
        "coins": 10,
        "base": 10,
        "multiplier": 1.0,
        "cap_hit": False,
        "streak_days": 1,
    }
    assert res["retro"]["tags"] == ["deep work", "spec"]
    ledger = await db.execute(select(CoinLedger))
    row = ledger.scalar_one()
    assert row.delta == 10 and row.kind == "session_reward"
    me = await client.get("/me")
    assert me.json()["balance"] == 10
    assert me.json()["streak_days"] == 1
    assert await event_types(db, sid) == [
        "session.started",
        "session.stopped",
        "reward.granted",
    ]
    all_types = await event_types(db)
    assert "retro.submitted" in all_types and "village.xp_added" in all_types


async def test_retro_on_running_session_conflicts(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    body = await start(client)
    res = await client.post(f"/sessions/{body['id']}/retro", json={"mood": 3})
    assert res.status_code == 409


async def test_intent_match_required_only_with_intent(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    with_intent = await focus_and_stop(client, fake_clock, 1, intent="write tests")
    res = await client.post(f"/sessions/{with_intent}/retro", json={"mood": 3})
    assert res.status_code == 422
    ok = await retro(client, with_intent, mood=3, intent_match="partly")
    assert ok["retro"]["intent_match"] == "partly"

    without_intent = await focus_and_stop(client, fake_clock, 1)
    ok2 = await retro(client, without_intent, mood=2, intent_match="yes")
    assert ok2["retro"]["intent_match"] is None


async def test_duplicate_retro_conflicts_and_ledger_has_one_row(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    sid = await focus_and_stop(client, fake_clock, 5)
    await retro(client, sid)
    res = await client.post(f"/sessions/{sid}/retro", json={"mood": 3})
    assert res.status_code == 409
    count = await db.execute(select(func.count()).select_from(CoinLedger))
    assert count.scalar_one() == 1


async def test_daily_cap_limits_coins(client: AsyncClient, fake_clock: FakeClock) -> None:
    first = await focus_and_stop(client, fake_clock, 200)
    r1 = await retro(client, first)
    assert r1["reward"]["coins"] == 200 and r1["reward"]["cap_hit"] is False
    second = await focus_and_stop(client, fake_clock, 200)
    r2 = await retro(client, second)
    assert r2["reward"]["coins"] == 100 and r2["reward"]["cap_hit"] is True
    third = await focus_and_stop(client, fake_clock, 10)
    r3 = await retro(client, third)
    assert r3["reward"]["coins"] == 0 and r3["reward"]["cap_hit"] is True
    me = await client.get("/me")
    assert me.json()["balance"] == 300


async def test_three_day_streak_applies_multiplier(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    rewards = []
    for day in range(3):
        fake_clock.set(DEFAULT_START + timedelta(days=day))
        sid = await focus_and_stop(client, fake_clock, 10)
        rewards.append((await retro(client, sid))["reward"])
    assert [r["streak_days"] for r in rewards] == [1, 2, 3]
    assert [r["multiplier"] for r in rewards] == [1.0, 1.0, 1.1]
    assert rewards[2]["coins"] == 11
    me = await client.get("/me")
    assert me.json()["streak_days"] == 3


async def test_retro_adds_village_xp(client: AsyncClient, fake_clock: FakeClock) -> None:
    sid = await focus_and_stop(client, fake_clock, 25)
    await retro(client, sid)
    me = await client.get("/me")
    assert me.json()["village"]["xp"] == 25


async def test_retro_after_day_boundary_and_grace_abandons(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    sid = await focus_and_stop(client, fake_clock, 10)
    # Next local day (05:00 Asia/Seoul == 20:00 UTC same date), well past the 30 min grace.
    fake_clock.set(datetime(2026, 9, 17, 20, 0, tzinfo=UTC))
    res = await client.post(f"/sessions/{sid}/retro", json={"mood": 3})
    assert res.status_code == 409
    day = await client.get("/sessions", params={"date": "2026-09-17"})
    assert day.json()["sessions"][0]["status"] == "abandoned"
    assert (await event_types(db, sid))[-1] == "session.abandoned"


async def test_retro_within_grace_after_boundary_still_works(
    client: AsyncClient, fake_clock: FakeClock
) -> None:
    # Stop at 03:50 local (18:50 UTC), retro at 04:10 local: past boundary, within grace.
    fake_clock.set(datetime(2026, 9, 16, 18, 40, tzinfo=UTC))
    sid = await focus_and_stop(client, fake_clock, 10)
    fake_clock.set(datetime(2026, 9, 16, 19, 10, tzinfo=UTC))
    res = await retro(client, sid)
    assert res["session"]["status"] == "completed"
    assert res["session"]["local_date"] == "2026-09-16"
