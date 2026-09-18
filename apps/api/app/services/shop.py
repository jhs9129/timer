import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, NotFound
from app.models.reward import KIND_PURCHASE, CoinLedger
from app.models.user import User
from app.models.village import Inventory, Item, Village
from app.services import clock
from app.services.events import emit
from app.services.rewards import balance
from app.services.sessions import today_for
from app.services.villages import assert_can_edit, level_for


async def list_items(db: AsyncSession) -> list[Item]:
    result = await db.execute(
        select(Item).where(Item.active.is_(True)).order_by(Item.sort_order, Item.code)
    )
    return list(result.scalars().all())


async def purchase(db: AsyncSession, *, user: User, village: Village, item_code: str) -> Inventory:
    assert_can_edit(village, user)
    row = await db.execute(select(Item).where(Item.code == item_code, Item.active.is_(True)))
    item = row.scalar_one_or_none()
    if item is None:
        raise NotFound("item not found")
    level = await level_for(db, village.xp)
    if item.unlock_level > level.level:
        raise Conflict(f"item unlocks at level {item.unlock_level}")
    if await balance(db, user.id) < item.price:
        raise Conflict("not enough coins")

    now = clock.now()
    db.add(
        CoinLedger(
            user_id=user.id,
            delta=-item.price,
            kind=KIND_PURCHASE,
            ref_type="inventory_purchase",
            ref_id=uuid.uuid4(),
            local_date=today_for(user, now),
            created_at=now,
        )
    )
    inv_row = await db.execute(
        select(Inventory).where(Inventory.village_id == village.id, Inventory.item_id == item.id)
    )
    inv = inv_row.scalar_one_or_none()
    if inv is None:
        inv = Inventory(village_id=village.id, item_id=item.id, qty=0)
        db.add(inv)
    inv.qty += 1
    await db.flush()
    await db.refresh(inv, attribute_names=["item"])
    emit(
        db,
        "item.purchased",
        subject_type="inventory",
        subject_id=inv.id,
        actor_id=user.id,
        payload={"item_code": item.code, "price": item.price, "qty_after": inv.qty},
    )
    return inv
