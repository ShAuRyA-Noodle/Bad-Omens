"""SQLAlchemy declarative base + common column mixins.

All ORM models in :mod:`app.db.models` inherit from :class:`Base`.
The :class:`UUIDPrimaryKey` and :class:`Timestamped` mixins give every
table a random UUID primary key and ``created_at`` / ``updated_at``
columns, which we want on almost every table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Consistent naming convention for constraints — makes Alembic diffs
# stable and predictable.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Declarative base — every model inherits from this."""

    metadata = metadata_obj
    type_annotation_map: dict[type, Any] = {}


def _now() -> datetime:
    """UTC 'now' that SQLAlchemy default= can call on each insert."""
    return datetime.now(tz=timezone.utc)


class UUIDPrimaryKey:
    """Mixin adding a random UUIDv4 ``id`` column as primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class Timestamped:
    """Mixin adding ``created_at`` and ``updated_at`` columns (UTC)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )


__all__ = [
    "Base",
    "Timestamped",
    "UUIDPrimaryKey",
    "metadata_obj",
]
