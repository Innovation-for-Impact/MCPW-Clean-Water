from pydantic import BaseModel, Field

from src.schemas.contact import Contact
from src.schemas.enums import MaterialType
from src.schemas.jurisdiction import Jurisdiction
from src.schemas.location import Location


class LookupRequest(BaseModel):
    location: Location
    material: MaterialType
    quantity_gallons: float | None = None
    buffer_radius_m: float | None = Field(default=None, gt=0, le=10000)


class DrainInfo(BaseModel):
    drain_id: str
    name: str
    tier: str
    conveyance_owner: str
    conveyance_type: str
    distance_m: float


class WaterInfo(BaseModel):
    name: str | None
    nhd_comid: int | None
    distance_m: float


class InterceptPointInfo(BaseModel):
    name: str
    source: str
    plan_sheet: str | None


class MajorDrainInfo(BaseModel):
    drain_id: str
    name: str
    tier: str


class SpatialFlags(BaseModel):
    beach_downstream: bool = False
    intake_downstream: bool = False
    outside_county: bool = False
    excluded_procedure: bool = False


class LookupResult(BaseModel):
    jurisdictions: list[Jurisdiction]
    drain: DrainInfo | None = None
    nearest_water: WaterInfo | None = None
    first_major_drain_downstream: MajorDrainInfo | None = None
    next_intercept_point: InterceptPointInfo | None = None
    downstream_path: list[str]
    upstream_counties: list[str] = []
    flags: SpatialFlags = SpatialFlags()
    response_contacts: list[Contact]
    regulatory_contacts: list[Contact]
