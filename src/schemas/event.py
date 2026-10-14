import uuid
from datetime import datetime

from pydantic import BaseModel

from src.schemas.contact import Contact
from src.schemas.enums import IncidentStatus, MaterialType, WaterBodyType
from src.schemas.jurisdiction import Jurisdiction
from src.schemas.location import Location


class IncidentEvent(BaseModel):
    event_id: uuid.UUID
    event_type: str
    event_version: str = "1.0"
    timestamp: datetime
    incident_id: uuid.UUID
    location: Location
    material: MaterialType
    material_detail: str | None = None
    quantity_gallons: float | None = None
    water_body: WaterBodyType
    jurisdictions: list[Jurisdiction]
    contacts: list[Contact]
    status: IncidentStatus

    model_config = {"from_attributes": True}
