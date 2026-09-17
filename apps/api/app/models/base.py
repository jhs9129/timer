import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


def new_id() -> uuid.UUID:
    return uuid.uuid4()
