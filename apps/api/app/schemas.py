import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.session import FocusSession
from app.models.village import Item, Placement


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


class VillageSummary(BaseModel):
    slug: str
    name: str
    xp: int
    level: int


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    timezone: str
    balance: int
    streak_days: int
    village: VillageSummary


class ItemOut(BaseModel):
    code: str
    name: str
    category: str
    layer: str
    price: int
    width: int
    height: int
    unlock_level: int

    @classmethod
    def from_model(cls, item: Item) -> "ItemOut":
        return cls(
            code=item.code,
            name=item.name,
            category=item.category,
            layer=item.layer,
            price=item.price,
            width=item.width,
            height=item.height,
            unlock_level=item.unlock_level,
        )


class InventoryOut(BaseModel):
    item_code: str
    qty: int


class PlacementOut(BaseModel):
    id: uuid.UUID
    item_code: str
    category: str
    layer: str
    x: int
    y: int
    rotation: int
    width: int
    height: int

    @classmethod
    def from_model(cls, placement: Placement) -> "PlacementOut":
        w, h = placement.footprint
        return cls(
            id=placement.id,
            item_code=placement.item.code,
            category=placement.item.category,
            layer=placement.layer,
            x=placement.x,
            y=placement.y,
            rotation=placement.rotation,
            width=w,
            height=h,
        )


class PublicVillageOut(BaseModel):
    slug: str
    name: str
    width: int
    height: int
    level: int
    xp: int
    placements: list[PlacementOut]


class VillageOut(PublicVillageOut):
    inventory: list[InventoryOut]
    balance: int
    next_level_xp: int | None


class VillageRename(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class PlacementIn(BaseModel):
    item_code: str = Field(max_length=40)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    rotation: int = Field(default=0, ge=0, le=3)


class PlacementMoveIn(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    rotation: int | None = Field(default=None, ge=0, le=3)


class PurchaseIn(BaseModel):
    item_code: str = Field(max_length=40)


class PurchaseOut(BaseModel):
    inventory: list[InventoryOut]
    balance: int


class MePatch(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class DevLoginIn(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=100)


class DispatchOut(BaseModel):
    timed_out: int
    abandoned: int
    scheduled: int
    sent: int
    failed: int


class VapidKeyOut(BaseModel):
    key: str


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=256)
    auth: str = Field(min_length=1, max_length=64)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1024)
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=256)


class PushSubscriptionOut(BaseModel):
    id: uuid.UUID


class NotificationPrefsOut(BaseModel):
    push: bool
    email_weekly: bool
    reminder_local_time: time | None


class NotificationPrefsPatch(BaseModel):
    push: bool | None = None
    email_weekly: bool | None = None
    reminder_local_time: time | None = None
