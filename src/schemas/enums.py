from enum import Enum


class WaterBodyType(str, Enum):
    lake_st_clair = "lake_st_clair"
    clinton_river = "clinton_river"
    tributary = "tributary"
    county_drain = "county_drain"
    storm_sewer = "storm_sewer"
    unknown = "unknown"


class MaterialType(str, Enum):
    oil_fuel = "oil_fuel"
    chemical_hazmat = "chemical_hazmat"
    sewage = "sewage"
    unknown_other = "unknown_other"


class QuantityUnit(str, Enum):
    gal = "gal"
    bbl = "bbl"
    L = "L"
    lb = "lb"


class IncidentStatus(str, Enum):
    open = "open"
    closed = "closed"
    under_review = "under_review"


class ContactRole(str, Enum):
    response = "response"
    regulatory = "regulatory"


class UserRole(str, Enum):
    responder = "responder"
    viewer = "viewer"
    admin = "admin"
