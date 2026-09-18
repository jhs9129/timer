import uuid

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.user import User
from app.models.village import Village
from app.schemas import (
    InventoryOut,
    PlacementIn,
    PlacementMoveIn,
    PlacementOut,
    PublicVillageOut,
    VillageOut,
    VillageRename,
)
from app.services import clock, villages
from app.services.rewards import balance

router = APIRouter(tags=["villages"])


async def build_public(db: AsyncSession, village: Village) -> PublicVillageOut:
    level = await villages.level_for(db, village.xp)
    placements = await villages.placements_of(db, village.id)
    return PublicVillageOut(
        slug=village.slug,
        name=village.name,
        width=village.width,
        height=village.height,
        level=level.level,
        xp=village.xp,
        placements=[PlacementOut.from_model(p) for p in placements],
    )


async def build_village(db: AsyncSession, village: Village, user: User) -> VillageOut:
    public = await build_public(db, village)
    level = await villages.level_for(db, village.xp)
    nxt = await villages.next_level(db, level.level)
    inventory = await villages.inventory_of(db, village.id)
    return VillageOut(
        **public.model_dump(),
        inventory=[InventoryOut(item_code=i.item.code, qty=i.qty) for i in inventory if i.qty > 0],
        balance=await balance(db, user.id),
        next_level_xp=nxt.xp_required if nxt else None,
    )


@router.get("/villages/me")
async def my_village(db: DbSession, user: CurrentUser) -> VillageOut:
    village = await villages.village_for_user(db, user.id)
    return await build_village(db, village, user)


@router.patch("/villages/me")
async def rename_village(body: VillageRename, db: DbSession, user: CurrentUser) -> VillageOut:
    village = await villages.village_for_user(db, user.id)
    villages.assert_can_edit(village, user)
    village.name = body.name.strip()
    village.updated_at = clock.now()
    await db.flush()
    return await build_village(db, village, user)


@router.post("/villages/me/placements", status_code=status.HTTP_201_CREATED)
async def place_item(body: PlacementIn, db: DbSession, user: CurrentUser) -> PlacementOut:
    village = await villages.village_for_user(db, user.id)
    placement = await villages.place(
        db,
        user=user,
        village=village,
        item_code=body.item_code,
        x=body.x,
        y=body.y,
        rotation=body.rotation,
    )
    return PlacementOut.from_model(placement)


@router.patch("/villages/me/placements/{placement_id}")
async def move_item(
    placement_id: uuid.UUID, body: PlacementMoveIn, db: DbSession, user: CurrentUser
) -> PlacementOut:
    village = await villages.village_for_user(db, user.id)
    placement = await villages.move(
        db,
        user=user,
        village=village,
        placement_id=placement_id,
        x=body.x,
        y=body.y,
        rotation=body.rotation,
    )
    return PlacementOut.from_model(placement)


@router.delete("/villages/me/placements/{placement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(placement_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    village = await villages.village_for_user(db, user.id)
    await villages.remove(db, user=user, village=village, placement_id=placement_id)


@router.get("/v/{slug}")
async def public_village(slug: str, db: DbSession) -> PublicVillageOut:
    village = await villages.get_by_slug(db, slug)
    return await build_public(db, village)
