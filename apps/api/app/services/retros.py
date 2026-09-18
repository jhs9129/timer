import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, ValidationFailed
from app.models.notification import KIND_RETRO_PENDING
from app.models.retro import INTENT_MATCHES, Retrospective, RetroTag, Tag
from app.models.session import STATUS_COMPLETED, STATUS_ENDED, FocusSession
from app.models.user import User
from app.services import clock
from app.services.events import emit
from app.services.notifications import cancel_for_ref
from app.services.rewards import RewardResult, grant_session_reward
from app.services.villages import add_xp, village_for_user


async def submit_retro(
    db: AsyncSession,
    *,
    user: User,
    session: FocusSession,
    mood: int,
    intent_match: str | None,
    tags: list[str],
    note: str | None,
) -> tuple[Retrospective, RewardResult]:
    now = clock.now()
    if session.status != STATUS_ENDED:
        raise Conflict("retro requires an ended session")
    if not 1 <= mood <= 4:
        raise ValidationFailed("mood must be 1..4")
    if session.intent:
        if intent_match not in INTENT_MATCHES:
            raise ValidationFailed("intent_match is required when the session has an intent")
    else:
        intent_match = None

    existing = await db.execute(
        select(Retrospective.id).where(Retrospective.session_id == session.id)
    )
    if existing.scalar_one_or_none() is not None:
        raise Conflict("retro already submitted")

    retro = Retrospective(
        session_id=session.id,
        user_id=user.id,
        mood=mood,
        intent_match=intent_match,
        note=(note or None),
        submitted_at=now,
        updated_at=now,
    )
    db.add(retro)
    await db.flush()
    tag_rows = await _upsert_tags(db, user.id, tags)
    for tag in tag_rows:
        db.add(RetroTag(retro_id=retro.id, tag_id=tag.id))

    session.status = STATUS_COMPLETED
    session.updated_at = now
    await db.flush()

    emit(
        db,
        "retro.submitted",
        subject_type="retrospective",
        subject_id=retro.id,
        actor_id=user.id,
        payload={
            "session_id": str(session.id),
            "mood": mood,
            "intent_match": intent_match,
            "tag_count": len(tag_rows),
            "has_note": retro.note is not None,
        },
    )
    reward = await grant_session_reward(db, session)
    village = await village_for_user(db, user.id)
    await add_xp(db, village, session.focused_seconds // 60, actor_id=user.id)
    await cancel_for_ref(
        db,
        ref_type="focus_session",
        ref_id=session.id,
        reason="retro_submitted",
        kinds=(KIND_RETRO_PENDING,),
    )
    return retro, reward


async def _upsert_tags(db: AsyncSession, user_id: uuid.UUID, names: list[str]) -> list[Tag]:
    cleaned: list[str] = []
    for raw in names:
        name = raw.strip()[:40]
        if name and name not in cleaned:
            cleaned.append(name)
    if not cleaned:
        return []
    result = await db.execute(
        select(Tag).where(Tag.owner_user_id == user_id, Tag.name.in_(cleaned))
    )
    found = {tag.name: tag for tag in result.scalars().all()}
    now = clock.now()
    for name in cleaned:
        if name not in found:
            tag = Tag(owner_user_id=user_id, name=name, created_at=now)
            db.add(tag)
            found[name] = tag
    await db.flush()
    return [found[name] for name in cleaned]
