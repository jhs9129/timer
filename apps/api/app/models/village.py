import uuid
from datetime import datetime

from sqlalchemy import BigInteger, SmallInteger, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id

OWNER_USER = "user"
OWNER_GUILD = "guild"


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
