from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.errors import ValidationFailed
from app.models.user import User
from app.schemas import MeOut, MePatch, VillageOut
from app.services import clock
from app.services.localdate import is_valid_timezone
from app.services.rewards import balance, streak_days
from app.services.sessions import today_for
from app.services.villages import village_for_user

router = APIRouter(tags=["me"])


async def build_me(db: AsyncSession, user: User) -> MeOut:
    village = await village_for_user(db, user.id)
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        timezone=user.timezone,
        balance=await balance(db, user.id),
        streak_days=await streak_days(db, user.id, today_for(user, clock.now())),
        village=VillageOut(slug=village.slug, name=village.name, xp=village.xp),
    )


@router.get("/me")
async def get_me(db: DbSession, user: CurrentUser) -> MeOut:
    return await build_me(db, user)


@router.patch("/me")
async def patch_me(body: MePatch, db: DbSession, user: CurrentUser) -> MeOut:
    if body.timezone is not None:
        if not is_valid_timezone(body.timezone):
            raise ValidationFailed("unknown timezone")
        user.timezone = body.timezone
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    user.updated_at = clock.now()
    await db.flush()
    return await build_me(db, user)
