from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Domain models are added from M1 onward (see docs/03-data-model.md)."""
