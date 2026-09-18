from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from tests.conftest import FakeClock


async def start(client: AsyncClient, **body: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"mode": "stopwatch"}
    payload.update(body)
    res = await client.post("/sessions", json=payload)
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


async def focus(client: AsyncClient, fake_clock: FakeClock, session_id: str, seconds: int) -> None:
    """Advance the fake clock while sending heartbeats, as a live client would."""
    step = 60  # under the 90s timeout
    remaining = seconds
    while remaining > 0:
        chunk = min(step, remaining)
        fake_clock.advance(chunk)
        res = await client.post(f"/sessions/{session_id}/heartbeat")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "running", res.text
        remaining -= chunk


async def stop(client: AsyncClient, session_id: str) -> dict[str, Any]:
    res = await client.post(f"/sessions/{session_id}/stop")
    assert res.status_code == 200, res.text
    data: dict[str, Any] = res.json()
    return data


async def focus_and_stop(
    client: AsyncClient, fake_clock: FakeClock, minutes: int, **start_body: Any
) -> str:
    body = await start(client, **start_body)
    await focus(client, fake_clock, body["id"], minutes * 60)
    await stop(client, body["id"])
    return str(body["id"])


async def retro(client: AsyncClient, session_id: str, **body: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"mood": 3}
    payload.update(body)
    res = await client.post(f"/sessions/{session_id}/retro", json=payload)
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


async def earn_coins(
    client: AsyncClient, fake_clock: FakeClock, minutes: int, *, day_offset: int = 0
) -> int:
    """Earn `minutes` coins the real way: focus, stop, retro. Returns the coins granted."""
    if day_offset:
        fake_clock.advance(day_offset * 24 * 3600)
    sid = await focus_and_stop(client, fake_clock, minutes)
    result = await retro(client, sid)
    coins: int = result["reward"]["coins"]
    return coins


async def buy(client: AsyncClient, item_code: str) -> dict[str, Any]:
    res = await client.post("/shop/purchase", json={"item_code": item_code})
    assert res.status_code == 200, res.text
    data: dict[str, Any] = res.json()
    return data


async def place(
    client: AsyncClient, item_code: str, x: int, y: int, *, rotation: int = 0
) -> dict[str, Any]:
    res = await client.post(
        "/villages/me/placements",
        json={"item_code": item_code, "x": x, "y": y, "rotation": rotation},
    )
    assert res.status_code == 201, res.text
    data: dict[str, Any] = res.json()
    return data


async def event_types(db: AsyncSession, subject_id: str | None = None) -> list[str]:
    stmt = select(Event.event_type).order_by(Event.occurred_at, Event.ingested_at)
    if subject_id is not None:
        stmt = stmt.where(Event.subject_id == subject_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
