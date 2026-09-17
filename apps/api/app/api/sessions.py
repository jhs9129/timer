import uuid
from datetime import date

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.errors import Conflict
from app.models.retro import Retrospective, RetroTag, Tag
from app.models.reward import KIND_SESSION_REWARD, CoinLedger
from app.models.session import STATUS_ENDED, FocusSession
from app.schemas import (
    DayOut,
    PauseIn,
    RetroIn,
    RetroOut,
    RetroResponse,
    RewardOut,
    SessionOut,
    StartIn,
)
from app.services import clock, sessions
from app.services.retros import submit_retro

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _retro_ids(db: AsyncSession, session_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not session_ids:
        return set()
    result = await db.execute(
        select(Retrospective.session_id).where(Retrospective.session_id.in_(session_ids))
    )
    return set(result.scalars().all())


async def _out(db: AsyncSession, session: FocusSession) -> SessionOut:
    has_retro = bool(await _retro_ids(db, [session.id]))
    return SessionOut.from_model(session, has_retro=has_retro)


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_session(body: StartIn, db: DbSession, user: CurrentUser) -> SessionOut:
    session = await sessions.start(
        db, user, mode=body.mode, target_seconds=body.target_seconds, intent=body.intent
    )
    return SessionOut.from_model(session)


@router.get(
    "/current",
    response_model=SessionOut,
    responses={204: {"description": "no active session"}},
)
async def current_session(db: DbSession, user: CurrentUser) -> SessionOut | Response:
    session = await sessions.get_active(db, user.id)
    if session is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return SessionOut.from_model(session)


@router.get("")
async def list_sessions(db: DbSession, user: CurrentUser, date: date | None = None) -> DayOut:
    day = date or sessions.today_for(user, clock.now())
    rows = await sessions.list_for_date(db, user.id, day)
    retro_ids = await _retro_ids(db, [row.id for row in rows])
    coins = await db.execute(
        select(CoinLedger.delta).where(
            CoinLedger.user_id == user.id,
            CoinLedger.kind == KIND_SESSION_REWARD,
            CoinLedger.local_date == day,
        )
    )
    outs = [SessionOut.from_model(row, has_retro=row.id in retro_ids) for row in rows]
    return DayOut(
        date=day,
        sessions=outs,
        focused_seconds=sum(out.focused_seconds for out in outs),
        coins_earned=sum(coins.scalars().all()),
    )


@router.post("/{session_id}/heartbeat")
async def heartbeat(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> SessionOut:
    session = await sessions.get_owned(db, user.id, session_id)
    sessions.heartbeat(session)
    return await _out(db, session)


@router.post("/{session_id}/pause")
async def pause(
    session_id: uuid.UUID, body: PauseIn, db: DbSession, user: CurrentUser
) -> SessionOut:
    session = await sessions.get_owned(db, user.id, session_id)
    sessions.pause(db, session, reason=body.reason, actor_id=user.id)
    return await _out(db, session)


@router.post("/{session_id}/resume")
async def resume(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> SessionOut:
    session = await sessions.get_owned(db, user.id, session_id)
    sessions.resume(db, session, actor_id=user.id)
    return await _out(db, session)


@router.post("/{session_id}/stop")
async def stop(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> SessionOut:
    session = await sessions.get_owned(db, user.id, session_id)
    sessions.stop(db, session, actor_id=user.id)
    return await _out(db, session)


@router.post("/{session_id}/retro", status_code=status.HTTP_201_CREATED)
async def retro(
    session_id: uuid.UUID, body: RetroIn, db: DbSession, user: CurrentUser
) -> RetroResponse:
    session = await sessions.get_owned(db, user.id, session_id)
    now = clock.now()
    if session.status == STATUS_ENDED and sessions.is_past_grace(session, user, now):
        sessions.abandon(db, session, now=now)
        await db.commit()
        raise Conflict("session was abandoned: its day ended before the retro")
    retro_row, reward = await submit_retro(
        db,
        user=user,
        session=session,
        mood=body.mood,
        intent_match=body.intent_match,
        tags=body.tags,
        note=body.note,
    )
    tag_names = await db.execute(
        select(Tag.name)
        .join(RetroTag, RetroTag.tag_id == Tag.id)
        .where(RetroTag.retro_id == retro_row.id)
    )
    return RetroResponse(
        retro=RetroOut(
            id=retro_row.id,
            session_id=retro_row.session_id,
            mood=retro_row.mood,
            intent_match=retro_row.intent_match,
            tags=list(tag_names.scalars().all()),
            note=retro_row.note,
            submitted_at=retro_row.submitted_at,
        ),
        reward=RewardOut(
            coins=reward.coins,
            base=reward.base,
            multiplier=reward.multiplier,
            cap_hit=reward.cap_hit,
            streak_days=reward.streak_days,
        ),
        session=SessionOut.from_model(session, has_retro=True),
    )
