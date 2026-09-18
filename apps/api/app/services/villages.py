import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, NotFound, ValidationFailed
from app.models.user import User
from app.models.village import (
    OWNER_USER,
    Inventory,
    Item,
    Placement,
    Village,
    VillageLevel,
    cells,
    footprint,
)
from app.services import clock
from app.services.events import emit


def _new_slug() -> str:
    return secrets.token_urlsafe(6).replace("-", "x").replace("_", "y").lower()


async def create_village(
    db: AsyncSession, *, owner_type: str, owner_id: uuid.UUID, name: str
) -> Village:
    now = clock.now()
    village = Village(
        owner_type=owner_type,
        owner_id=owner_id,
        slug=_new_slug(),
        name=name,
        created_at=now,
        updated_at=now,
    )
    db.add(village)
    await db.flush()
    emit(
        db,
        "village.created",
        subject_type="village",
        subject_id=village.id,
        actor_id=owner_id if owner_type == OWNER_USER else None,
        payload={"owner_type": owner_type, "slug": village.slug},
    )
    return village


async def village_for_user(db: AsyncSession, user_id: uuid.UUID) -> Village:
    result = await db.execute(
        select(Village).where(Village.owner_type == OWNER_USER, Village.owner_id == user_id)
    )
    return result.scalar_one()


async def get_by_slug(db: AsyncSession, slug: str) -> Village:
    result = await db.execute(select(Village).where(Village.slug == slug))
    village = result.scalar_one_or_none()
    if village is None:
        raise NotFound("village not found")
    return village


def assert_can_edit(village: Village, user: User) -> None:
    """The single place that decides edit rights. Guild ownership is added here in M5."""
    if village.owner_type != OWNER_USER or village.owner_id != user.id:
        raise NotFound("village not found")


async def level_for(db: AsyncSession, xp: int) -> VillageLevel:
    result = await db.execute(
        select(VillageLevel)
        .where(VillageLevel.xp_required <= xp)
        .order_by(VillageLevel.level.desc())
        .limit(1)
    )
    level = result.scalar_one_or_none()
    if level is None:
        raise RuntimeError("village_levels has no rows; run migrations")
    return level


async def next_level(db: AsyncSession, level: int) -> VillageLevel | None:
    result = await db.execute(
        select(VillageLevel).where(VillageLevel.level > level).order_by(VillageLevel.level).limit(1)
    )
    return result.scalar_one_or_none()


async def add_xp(db: AsyncSession, village: Village, minutes: int, actor_id: uuid.UUID) -> None:
    before = await level_for(db, village.xp)
    village.xp += minutes
    village.updated_at = clock.now()
    emit(
        db,
        "village.xp_added",
        subject_type="village",
        subject_id=village.id,
        actor_id=actor_id,
        payload={"minutes": minutes, "xp": village.xp},
    )
    after = await level_for(db, village.xp)
    if after.level > before.level:
        village.width = max(village.width, after.width)
        village.height = max(village.height, after.height)
        emit(
            db,
            "village.level_up",
            subject_type="village",
            subject_id=village.id,
            actor_id=actor_id,
            payload={
                "from_level": before.level,
                "to_level": after.level,
                "width": village.width,
                "height": village.height,
            },
        )


async def inventory_of(db: AsyncSession, village_id: uuid.UUID) -> list[Inventory]:
    result = await db.execute(
        select(Inventory)
        .join(Item)
        .where(Inventory.village_id == village_id)
        .order_by(Item.sort_order)
    )
    return list(result.scalars().unique().all())


async def placements_of(db: AsyncSession, village_id: uuid.UUID) -> list[Placement]:
    result = await db.execute(
        select(Placement).where(Placement.village_id == village_id).order_by(Placement.placed_at)
    )
    return list(result.scalars().unique().all())


async def _inventory_row(
    db: AsyncSession, village_id: uuid.UUID, item_id: uuid.UUID
) -> Inventory | None:
    result = await db.execute(
        select(Inventory).where(Inventory.village_id == village_id, Inventory.item_id == item_id)
    )
    return result.scalar_one_or_none()


def _assert_in_bounds(village: Village, x: int, y: int, w: int, h: int) -> None:
    if x < 0 or y < 0 or x + w > village.width or y + h > village.height:
        raise ValidationFailed("placement is out of bounds")


async def _assert_free(
    db: AsyncSession,
    village: Village,
    layer: str,
    wanted: set[tuple[int, int]],
    exclude_id: uuid.UUID | None = None,
) -> None:
    for other in await placements_of(db, village.id):
        if other.layer != layer or other.id == exclude_id:
            continue
        w, h = other.footprint
        if wanted & cells(other.x, other.y, w, h):
            raise Conflict("placement overlaps another item")


async def place(
    db: AsyncSession,
    *,
    user: User,
    village: Village,
    item_code: str,
    x: int,
    y: int,
    rotation: int,
) -> Placement:
    assert_can_edit(village, user)
    item_row = await db.execute(select(Item).where(Item.code == item_code))
    item = item_row.scalar_one_or_none()
    if item is None:
        raise NotFound("item not found")
    inv = await _inventory_row(db, village.id, item.id)
    if inv is None or inv.qty <= 0:
        raise Conflict("item is not in the inventory")
    w, h = footprint(item, rotation)
    _assert_in_bounds(village, x, y, w, h)
    await _assert_free(db, village, item.layer, cells(x, y, w, h))
    now = clock.now()
    placement = Placement(
        village_id=village.id,
        item_id=item.id,
        x=x,
        y=y,
        rotation=rotation,
        layer=item.layer,
        placed_at=now,
        updated_at=now,
    )
    inv.qty -= 1
    db.add(placement)
    await db.flush()
    await db.refresh(placement, attribute_names=["item"])
    village.updated_at = now
    emit(
        db,
        "placement.changed",
        subject_type="placement",
        subject_id=placement.id,
        actor_id=user.id,
        payload={"action": "place", "item_code": item.code, "x": x, "y": y, "rotation": rotation},
    )
    return placement


async def _owned_placement(
    db: AsyncSession, village: Village, placement_id: uuid.UUID
) -> Placement:
    result = await db.execute(
        select(Placement).where(Placement.id == placement_id, Placement.village_id == village.id)
    )
    placement = result.scalar_one_or_none()
    if placement is None:
        raise NotFound("placement not found")
    return placement


async def move(
    db: AsyncSession,
    *,
    user: User,
    village: Village,
    placement_id: uuid.UUID,
    x: int,
    y: int,
    rotation: int | None,
) -> Placement:
    assert_can_edit(village, user)
    placement = await _owned_placement(db, village, placement_id)
    new_rotation = placement.rotation if rotation is None else rotation
    w, h = footprint(placement.item, new_rotation)
    _assert_in_bounds(village, x, y, w, h)
    await _assert_free(db, village, placement.layer, cells(x, y, w, h), exclude_id=placement.id)
    placement.x, placement.y, placement.rotation = x, y, new_rotation
    placement.updated_at = clock.now()
    village.updated_at = placement.updated_at
    emit(
        db,
        "placement.changed",
        subject_type="placement",
        subject_id=placement.id,
        actor_id=user.id,
        payload={
            "action": "move",
            "item_code": placement.item.code,
            "x": x,
            "y": y,
            "rotation": new_rotation,
        },
    )
    return placement


async def remove(
    db: AsyncSession, *, user: User, village: Village, placement_id: uuid.UUID
) -> None:
    assert_can_edit(village, user)
    placement = await _owned_placement(db, village, placement_id)
    inv = await _inventory_row(db, village.id, placement.item_id)
    if inv is None:
        inv = Inventory(village_id=village.id, item_id=placement.item_id, qty=0)
        db.add(inv)
    inv.qty += 1
    emit(
        db,
        "placement.changed",
        subject_type="placement",
        subject_id=placement.id,
        actor_id=user.id,
        payload={
            "action": "remove",
            "item_code": placement.item.code,
            "x": placement.x,
            "y": placement.y,
            "rotation": placement.rotation,
        },
    )
    await db.delete(placement)
    village.updated_at = clock.now()
    await db.flush()
