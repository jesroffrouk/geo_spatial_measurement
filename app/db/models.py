from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class File(Base):
    """One row per uploaded file."""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(primary_key=True)
    filename: Mapped[str]
    status: Mapped[str]
    crs: Mapped[str | None]
    feature_count: Mapped[int]
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    features: Mapped[list["Feature"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="Feature.index",
    )


class Feature(Base):
    """One row per feature (polygon, line, point...) inside a file."""

    __tablename__ = "features"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    index: Mapped[int]
    geometry_type: Mapped[str | None]
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    crs: Mapped[str | None]
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    area_sq_m: Mapped[float | None]
    length_m: Mapped[float | None]
    measured_in: Mapped[str | None]
    note: Mapped[str | None]

    file: Mapped["File"] = relationship(back_populates="features")
