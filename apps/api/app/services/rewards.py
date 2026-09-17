import math
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import KIND_SESSION_REWARD, CoinLedger, RewardConfig
from app.models.session import STATUS_COMPLETED, FocusSession
from app.services import clock
from app.services.events import emit


@dataclass(frozen=True)
class RewardResult:
    coins: int
    base: int
    multiplier: float
    cap_hit: bool
    streak_days: int


async def current_config(db: AsyncSession) -> RewardConfig:
    result = await db.execute(
        select(RewardConfig).order_by(RewardConfig.effective_from.desc()).limit(1)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise RuntimeError("reward_config has no rows; run migrations")
    return config


def multiplier_for(streak_days: int, multipliers: dict[str, object]) -> float:
    best_threshold = 0
    best = 1.0
    for key, value in multipliers.items():
        threshold = int(key)
        if threshold <= streak_days and threshold >= best_threshold:
            best_threshold = threshold
            best = float(str(value))
    return best


async def completed_dates(db: AsyncSession, user_id: uuid.UUID) -> set[date]:
    result = await db.execute(
        select(FocusSession.local_date)
        .where(FocusSession.user_id == user_id, FocusSession.status == STATUS_COMPLETED)
        .distinct()
    )
    return set(result.scalars().all())


async def streak_days(db: AsyncSession, user_id: uuid.UUID, today: date) -> int:
    """Consecutive days ending at `today` with at least one completed session."""
    dates = await completed_dates(db, user_id)
    streak = 0
    day = today
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


async def paid_on(db: AsyncSession, user_id: uuid.UUID, day: date) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(CoinLedger.delta), 0)).where(
            CoinLedger.user_id == user_id,
            CoinLedger.kind == KIND_SESSION_REWARD,
            CoinLedger.local_date == day,
        )
    )
    return int(result.scalar_one())


async def balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(CoinLedger.delta), 0)).where(CoinLedger.user_id == user_id)
    )
    return int(result.scalar_one())


async def grant_session_reward(db: AsyncSession, session: FocusSession) -> RewardResult:
    """Idempotent: (kind, ref_id) is unique, so a second grant for a session fails loudly."""
    config = await current_config(db)
    minutes = session.focused_seconds // 60
    base = math.floor(minutes * float(config.rate_per_minute))
    streak = await streak_days(db, session.user_id, session.local_date)
    multiplier = multiplier_for(streak, config.streak_multipliers)
    raw = math.floor(base * multiplier)
    remaining = max(0, config.daily_cap - await paid_on(db, session.user_id, session.local_date))
    coins = max(0, min(raw, remaining))
    cap_hit = raw > remaining
    db.add(
        CoinLedger(
            user_id=session.user_id,
            delta=coins,
            kind=KIND_SESSION_REWARD,
            ref_type="focus_session",
            ref_id=session.id,
            local_date=session.local_date,
            created_at=clock.now(),
        )
    )
    emit(
        db,
        "reward.granted",
        subject_type="focus_session",
        subject_id=session.id,
        actor_id=session.user_id,
        payload={
            "coins": coins,
            "base": base,
            "multiplier": multiplier,
            "cap_hit": cap_hit,
            "streak_days": streak,
        },
    )
    return RewardResult(
        coins=coins, base=base, multiplier=multiplier, cap_hit=cap_hit, streak_days=streak
    )
