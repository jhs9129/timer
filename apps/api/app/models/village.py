import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_id

OWNER_USER = "user"
OWNER_GUILD = "guild"

CATEGORY_GROUND = "ground"
CATEGORIES = {"ground", "tree", "prop", "building"}

LAYER_GROUND = "ground"
LAYER_OBJECT = "object"


def layer_for_category(category: str) -> str:
    return LAYER_GROUND if category == CATEGORY_GROUND else LAYER_OBJECT


class Village(Base):
    __tablename__ = "villages"
    __table_args__ = (UniqueConstraint("owner_type", "owner_id", name="uq_villages_owner"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    owner_type: Mapped[str] = mapped_column(String(8))
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    width: Mapped[int] = mapped_column(SmallInteger, default=16)
    height: Mapped[int] = mapped_column(SmallInteger, default=16)
    xp: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class VillageLevel(Base):
    __tablename__ = "village_levels"

    level: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    xp_required: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int] = mapped_column(SmallInteger)
    height: Mapped[int] = mapped_column(SmallInteger)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(16))
    price: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(SmallInteger, default=1)
    height: Mapped[int] = mapped_column(SmallInteger, default=1)
    unlock_level: Mapped[int] = mapped_column(SmallInteger, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)

    @property
    def layer(self) -> str:
        return layer_for_category(self.category)


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("village_id", "item_id", name="uq_inventory_village_item"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    village_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("villages.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("items.id"))
    qty: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped[Item] = relationship(lazy="joined")


class Placement(Base):
    __tablename__ = "placements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    village_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("villages.id"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("items.id"))
    x: Mapped[int] = mapped_column(SmallInteger)
    y: Mapped[int] = mapped_column(SmallInteger)
    rotation: Mapped[int] = mapped_column(SmallInteger, default=0)
    layer: Mapped[str] = mapped_column(String(8))
    placed_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    item: Mapped[Item] = relationship(lazy="joined")

    @property
    def footprint(self) -> tuple[int, int]:
        return footprint(self.item, self.rotation)


def footprint(item: Item, rotation: int) -> tuple[int, int]:
    return (item.height, item.width) if rotation % 2 == 1 else (item.width, item.height)


def cells(x: int, y: int, w: int, h: int) -> set[tuple[int, int]]:
    return {(x + dx, y + dy) for dx in range(w) for dy in range(h)}
