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


class DrainTier(str, Enum):
    tier_1 = "1"  # Large drain with response plan (e.g. Red Run)
    tier_2 = "2"  # Large/intercounty drain without plan (e.g. Bear Creek, Plum Brook)
    tier_3 = "3"  # Other county drains, open or enclosed
    tier_4 = "4"  # Not a county asset (roads-dept, municipal, private)


class ConveyanceOwner(str, Enum):
    county_drain = "county_drain"
    county_storm = "county_storm"
    county_sewer = "county_sewer"
    roads_dept = "roads_dept"
    municipal_ms4 = "municipal_ms4"
    private = "private"
    unknown = "unknown"


class ConveyanceType(str, Enum):
    open = "open"
    enclosed = "enclosed"
    sanitary = "sanitary"
    combined = "combined"
