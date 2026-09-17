import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.village import OWNER_USER, Village
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


async def add_xp(db: AsyncSession, village: Village, minutes: int, actor_id: uuid.UUID) -> None:
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
