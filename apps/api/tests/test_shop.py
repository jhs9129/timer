from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import CoinLedger
from tests.conftest import FakeClock
from tests.helpers import earn_coins, event_types


async def test_catalog_lists_active_items_in_order(client: AsyncClient) -> None:
    res = await client.get("/shop/items")
    assert res.status_code == 200
    codes = [i["code"] for i in res.json()]
    assert codes[:3] == ["ground_grass", "ground_path", "ground_flowers"]
    assert "bldg_cafe" in codes
    lamp = next(i for i in res.json() if i["code"] == "prop_lamp")
    assert lamp["layer"] == "object" and lamp["price"] == 40


async def test_purchase_requires_enough_coins(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    await earn_coins(client, fake_clock, 30)
    res = await client.post("/shop/purchase", json={"item_code": "tree_oak"})  # 60 coins
    assert res.status_code == 409
    village = await client.get("/villages/me")
    assert village.json()["inventory"] == []
    assert village.json()["balance"] == 30
    ledger = await db.execute(select(CoinLedger).where(CoinLedger.kind == "purchase"))
    assert ledger.scalars().all() == []


async def test_purchase_debits_ledger_and_adds_inventory(
    client: AsyncClient, db: AsyncSession, fake_clock: FakeClock
) -> None:
    await earn_coins(client, fake_clock, 100)
    res = await client.post("/shop/purchase", json={"item_code": "tree_oak"})
    assert res.status_code == 200, res.text
    assert res.json() == {"inventory": [{"item_code": "tree_oak", "qty": 1}], "balance": 40}
    ledger = await db.execute(select(CoinLedger).where(CoinLedger.kind == "purchase"))
    row = ledger.scalar_one()
    assert row.delta == -60
    assert "item.purchased" in await event_types(db)
    again = await client.post("/shop/purchase", json={"item_code": "prop_lamp"})
    assert again.json() == {
        "inventory": [{"item_code": "tree_oak", "qty": 1}, {"item_code": "prop_lamp", "qty": 1}],
        "balance": 0,
    }


async def test_purchase_respects_unlock_level(client: AsyncClient, fake_clock: FakeClock) -> None:
    await earn_coins(client, fake_clock, 300)
    res = await client.post("/shop/purchase", json={"item_code": "prop_well"})  # level 2
    assert res.status_code == 409
    assert "level 2" in res.json()["error"]["message"]


async def test_purchase_unknown_item_is_404(client: AsyncClient, fake_clock: FakeClock) -> None:
    res = await client.post("/shop/purchase", json={"item_code": "nope"})
    assert res.status_code == 404
