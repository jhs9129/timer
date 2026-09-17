import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.session import FocusSession


class SessionOut(BaseModel):
    id: uuid.UUID
    mode: str
    target_seconds: int | None
    intent: str | None
    status: str
    pause_reason: str | None
    local_date: date
    started_at: datetime
    ended_at: datetime | None
    focused_seconds: int
    running_since: datetime | None
    has_retro: bool

    @classmethod
    def from_model(cls, session: FocusSession, *, has_retro: bool = False) -> "SessionOut":
        open_segment = session.open_segment
        return cls(
            id=session.id,
            mode=session.mode,
            target_seconds=session.target_seconds,
            intent=session.intent,
            status=session.status,
            pause_reason=session.pause_reason,
            local_date=session.local_date,
            started_at=session.started_at,
            ended_at=session.ended_at,
            focused_seconds=session.closed_seconds()
            if session.ended_at is None
            else session.focused_seconds,
            running_since=open_segment.started_at if open_segment else None,
            has_retro=has_retro,
        )


class StartIn(BaseModel):
    mode: Literal["stopwatch", "countdown"]
    target_seconds: int | None = Field(default=None, gt=0, le=8 * 60 * 60)
    intent: str | None = Field(default=None, max_length=120)


class PauseIn(BaseModel):
    reason: Literal["user", "idle"]


class DayOut(BaseModel):
    date: date
    sessions: list[SessionOut]
    focused_seconds: int
    coins_earned: int


class RetroIn(BaseModel):
    mood: int = Field(ge=1, le=4)
    intent_match: Literal["yes", "partly", "no"] | None = None
    tags: list[str] = Field(default_factory=list, max_length=10)
    note: str | None = Field(default=None, max_length=300)


class RetroOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    mood: int
    intent_match: str | None
    tags: list[str]
    note: str | None
    submitted_at: datetime


class RewardOut(BaseModel):
    coins: int
    base: int
    multiplier: float
    cap_hit: bool
    streak_days: int


class RetroResponse(BaseModel):
    retro: RetroOut
    reward: RewardOut
    session: SessionOut


class VillageOut(BaseModel):
    slug: str
    name: str
    xp: int


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    timezone: str
    balance: int
    streak_days: int
    village: VillageOut


class MePatch(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class DevLoginIn(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=100)


class DispatchOut(BaseModel):
    timed_out: int
    abandoned: int
