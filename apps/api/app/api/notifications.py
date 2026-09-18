from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.errors import NotFound
from app.models.notification import CHANNEL_PUSH, CONSENT_EMAIL_WEEKLY, CONSENT_PUSH
from app.models.user import User
from app.schemas import (
    NotificationPrefsOut,
    NotificationPrefsPatch,
    PushSubscriptionIn,
    PushSubscriptionOut,
    VapidKeyOut,
)
from app.services import clock, notifications

router = APIRouter(tags=["notifications"])


@router.get("/push/vapid-public-key")
async def vapid_public_key() -> VapidKeyOut:
    return VapidKeyOut(key=get_settings().vapid_public_key)


@router.post("/push/subscriptions", status_code=status.HTTP_201_CREATED)
async def add_subscription(
    body: PushSubscriptionIn, db: DbSession, user: CurrentUser
) -> PushSubscriptionOut:
    sub = await notifications.upsert_subscription(
        db,
        user=user,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        user_agent=body.user_agent,
    )
    # Subscribing from the browser is an explicit act of consent.
    await notifications.set_consent(db, user, CONSENT_PUSH, True)
    return PushSubscriptionOut(id=sub.id)


@router.delete("/push/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def remove_subscription(
    db: DbSession, user: CurrentUser, endpoint: str = Query(min_length=1)
) -> None:
    if not await notifications.remove_subscription(db, user=user, endpoint=endpoint):
        raise NotFound("subscription not found")


async def build_prefs(db: AsyncSession, user: User) -> NotificationPrefsOut:
    return NotificationPrefsOut(
        push=await notifications.has_consent(db, user.id, CONSENT_PUSH),
        email_weekly=await notifications.has_consent(db, user.id, CONSENT_EMAIL_WEEKLY),
        reminder_local_time=user.reminder_local_time,
    )


@router.get("/me/notifications")
async def get_prefs(db: DbSession, user: CurrentUser) -> NotificationPrefsOut:
    return await build_prefs(db, user)


@router.patch("/me/notifications")
async def patch_prefs(
    body: NotificationPrefsPatch, db: DbSession, user: CurrentUser
) -> NotificationPrefsOut:
    if body.push is not None:
        changed = await notifications.set_consent(db, user, CONSENT_PUSH, body.push)
        if changed and not body.push:
            await notifications.revoke_all_subscriptions(db, user.id)
            await notifications.cancel_pending_for_user(
                db, user_id=user.id, reason="push_consent_revoked", channel=CHANNEL_PUSH
            )
    if body.email_weekly is not None:
        await notifications.set_consent(db, user, CONSENT_EMAIL_WEEKLY, body.email_weekly)
    if "reminder_local_time" in body.model_fields_set:
        user.reminder_local_time = body.reminder_local_time
        user.updated_at = clock.now()
    await db.flush()
    return await build_prefs(db, user)
