from pydantic import BaseModel

from src.schemas.contact import Contact
from src.schemas.enums import MaterialType
from src.schemas.jurisdiction import Jurisdiction
from src.schemas.location import Location


class LookupRequest(BaseModel):
    location: Location
    material: MaterialType
    quantity_gallons: float | None = None
    buffer_radius_m: float | None = None


class LookupResult(BaseModel):
    jurisdictions: list[Jurisdiction]
    downstream_path: list[str]
    response_contacts: list[Contact]
    regulatory_contacts: list[Contact]
