from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base dos modelos ORM. O schema é versionado pelas migrações SQL (Alembic)."""

    # Todos os timestamps do banco são TIMESTAMPTZ (UTC).
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}
