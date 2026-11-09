import uuid
from datetime import datetime

from pydantic import BaseModel

from src.schemas.enums import (
    IncidentStatus,
    MaterialType,
    QuantityUnit,
    WaterBodyType,
)
from src.schemas.location import Location


class IncidentCreate(BaseModel):
    location: Location
    water_body: WaterBodyType
    material: MaterialType
    material_detail: str | None = None
    quantity: float | None = None
    quantity_unit: QuantityUnit = QuantityUnit.gal
    quantity_gallons: float | None = None
    time_observed: datetime
    reporter_name: str
    reporter_phone: str
    notes: str | None = None
    buffer_radius_m: float | None = None


class Incident(IncidentCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    status: IncidentStatus

    model_config = {"from_attributes": True}


class IncidentSummary(BaseModel):
    """Lightweight incident representation for list endpoints."""

    id: uuid.UUID
    water_body: str
    material: str
    quantity_gallons: float | None = None
    status: str
    reporter_name: str
    time_observed: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
