import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id

KIND_SESSION_REWARD = "session_reward"
KIND_PURCHASE = "purchase"
KIND_ADJUSTMENT = "adjustment"


class RewardConfig(Base):
    __tablename__ = "reward_config"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    effective_from: Mapped[datetime] = mapped_column(index=True)
    rate_per_minute: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    daily_cap: Mapped[int] = mapped_column(Integer)
    streak_multipliers: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime]


class CoinLedger(Base):
    __tablename__ = "coin_ledger"
    __table_args__ = (UniqueConstraint("kind", "ref_id", name="uq_coin_ledger_kind_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    ref_type: Mapped[str] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    local_date: Mapped[date]
    created_at: Mapped[datetime]
