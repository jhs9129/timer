import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.services.villages import add_xp, village_for_user
from tests.conftest import FakeClock
from tests.helpers import buy, earn_coins, event_types, place


async def test_my_village_has_level_size_and_no_placements(client: AsyncClient) -> None:
    res = await client.get("/villages/me")
    assert res.status_code == 200
    body = res.json()
    assert body["level"] == 1 and body["width"] == 16 and body["height"] == 16
    assert body["placements"] == [] and body["inventory"] == []
    assert body["next_level_xp"] == 600
    assert body["balance"] == 0


async def test_place_requires_inventory(client: AsyncClient, fake_clock: FakeClock) -> None:
    res = await client.post(
        "/villages/me/placements", json={"item_code": "tree_oak", "x": 0, "y": 0}
    )
    assert res.status_code == 409


async def test_place_out_of_bounds_is_422(client: AsyncClient, fake_clock: FakeClock) -> None:
    await earn_coins(client, fake_clock, 60)
    await buy(client, "tree_oak")
    res = await client.post(
        "/villages/me/placements", json={"item_code": "tree_oak", "x": 16, "y": 0}
    )
    assert res.status_code == 422


async def test_overlap_is_checked_per_layer(client: AsyncClient, fake_clock: FakeClock) -> None:
    await earn_coins(client, fake_clock, 300)
    await buy(client, "ground_grass")
    await buy(client, "tree_oak")
    await buy(client, "tree_pine")
    await place(client, "ground_grass", 3, 3)
    tree = await place(client, "tree_oak", 3, 3)  # ground below is fine
    assert tree["layer"] == "object"
    clash = await client.post(
        "/villages/me/placements", json={"item_code": "tree_pine", "x": 3, "y": 3}
    )
    assert clash.status_code == 409
    village = await client.get("/villages/me")
    assert village.json()["inventory"] == [{"item_code": "tree_pine", "qty": 1}]


async def _grant_xp(client: AsyncClient, minutes: int) -> None:
    """Raise village XP through the service (the path a retro uses) without 1800 heartbeats."""
    user_id = uuid.UUID((await client.get("/me")).json()["id"])
    async with SessionLocal() as s:
        village = await village_for_user(s, user_id)
        await add_xp(s, village, minutes, actor_id=user_id)
        await s.commit()


async def test_rotation_swaps_footprint(client: AsyncClient, fake_clock: FakeClock) -> None:
    await _grant_xp(client, 1800)  # level 3 unlocks the cafe
    await earn_coins(client, fake_clock, 300)
    await earn_coins(client, fake_clock, 300, day_offset=1)
    await earn_coins(client, fake_clock, 300, day_offset=2)
    await buy(client, "bldg_cafe")  # 3x2, 900 coins
    body = await place(client, "bldg_cafe", 0, 0, rotation=1)
    assert (body["width"], body["height"]) == (2, 3)
    await buy_more_and_check_cells(client, fake_clock)


async def buy_more_and_check_cells(client: AsyncClient, fake_clock: FakeClock) -> None:
    await earn_coins(client, fake_clock, 60, day_offset=3)
    await buy(client, "tree_oak")
    # (1,2) is inside the rotated 2x3 footprint; (2,0) is outside it.
    clash = await client.post(
        "/villages/me/placements", json={"item_code": "tree_oak", "x": 1, "y": 2}
    )
    assert clash.status_code == 409
    ok = await client.post(
        "/villages/me/placements", json={"item_code": "tree_oak", "x": 2, "y": 0}
    )
    assert ok.status_code == 201


async def test_remove_returns_item_to_inventory(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    await earn_coins(client, fake_clock, 60)
    await buy(client, "tree_oak")
    placed = await place(client, "tree_oak", 5, 5)
    res = await client.delete(f"/villages/me/placements/{placed['id']}")
    assert res.status_code == 204
    village = await client.get("/villages/me")
    assert village.json()["placements"] == []
    assert village.json()["inventory"] == [{"item_code": "tree_oak", "qty": 1}]
    assert (await event_types(db, placed["id"])) == ["placement.changed", "placement.changed"]


async def test_move_ignores_self_but_not_others(client: AsyncClient, fake_clock: FakeClock) -> None:
    await earn_coins(client, fake_clock, 120)
    await buy(client, "tree_oak")
    await buy(client, "tree_pine")
    oak = await place(client, "tree_oak", 1, 1)
    await place(client, "tree_pine", 2, 2)
    same = await client.patch(f"/villages/me/placements/{oak['id']}", json={"x": 1, "y": 1})
    assert same.status_code == 200
    moved = await client.patch(f"/villages/me/placements/{oak['id']}", json={"x": 4, "y": 4})
    assert moved.status_code == 200 and moved.json()["x"] == 4
    clash = await client.patch(f"/villages/me/placements/{oak['id']}", json={"x": 2, "y": 2})
    assert clash.status_code == 409


async def test_other_users_placement_is_404(
    client: AsyncClient, other_client: AsyncClient, fake_clock: FakeClock
) -> None:
    await earn_coins(client, fake_clock, 60)
    await buy(client, "tree_oak")
    oak = await place(client, "tree_oak", 1, 1)
    res = await other_client.patch(f"/villages/me/placements/{oak['id']}", json={"x": 2, "y": 2})
    assert res.status_code == 404
    res2 = await other_client.delete(f"/villages/me/placements/{oak['id']}")
    assert res2.status_code == 404


async def test_level_up_expands_grid_and_keeps_placements(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    await earn_coins(client, fake_clock, 60)
    await buy(client, "tree_oak")
    oak = await place(client, "tree_oak", 15, 15)
    await _grant_xp(client, 540)  # 60 from the session + 540 = 600
    level2 = (await client.get("/villages/me")).json()
    assert level2["level"] == 2 and level2["width"] == 16
    await _grant_xp(client, 1200)  # 1800
    level3 = (await client.get("/villages/me")).json()
    assert level3["level"] == 3 and (level3["width"], level3["height"]) == (20, 20)
    assert [p["id"] for p in level3["placements"]] == [oak["id"]]
    assert level3["next_level_xp"] == 4200
    assert (await event_types(db)).count("village.level_up") == 2


async def test_public_village_needs_no_login_and_hides_private_fields(
    client: AsyncClient, anon_client: AsyncClient, fake_clock: FakeClock
) -> None:
    await earn_coins(client, fake_clock, 60)
    await buy(client, "tree_oak")
    await place(client, "tree_oak", 0, 0)
    slug = (await client.get("/me")).json()["village"]["slug"]
    res = await anon_client.get(f"/v/{slug}")
    assert res.status_code == 200
    body = res.json()
    assert body["placements"][0]["item_code"] == "tree_oak"
    assert "inventory" not in body and "balance" not in body
    missing = await anon_client.get("/v/nope")
    assert missing.status_code == 404
