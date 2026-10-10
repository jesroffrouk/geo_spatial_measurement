from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileInfo(BaseModel):
    """Response for POST /api/files/ and GET /api/files/{id}/."""

    model_config = ConfigDict(from_attributes=True)

    file_id: str = Field(validation_alias="id")
    filename: str
    status: str
    crs: str | None
    feature_count: int
    warnings: list[str]
    created_at: datetime


class FeatureMeasurement(BaseModel):
    """One feature inside GET /api/files/{id}/measurements/."""

    model_config = ConfigDict(from_attributes=True)

    index: int
    geometry_type: str | None
    geometry: dict[str, Any] | None
    crs: str | None
    properties: dict[str, Any]
    area_sq_m: float | None
    length_m: float | None
    measured_in: str | None
    note: str | None


class MeasurementsResponse(BaseModel):
    """Response for GET /api/files/{id}/measurements/."""

    model_config = ConfigDict(from_attributes=True)

    file_id: str = Field(validation_alias="id")
    crs: str | None
    feature_count: int
    features: list[FeatureMeasurement]
