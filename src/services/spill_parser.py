"""Backend spill parser — extracts structured incident fields from free text.

Parses a one-line spill description like:
  "about 50 gallons of diesel in the Clinton River near Mount Clemens"
into a partial IncidentCreate dict with whatever fields can be extracted.

This is the Python equivalent of the frontend spillParser.ts.
The frontend can call POST /incidents/parse to use this server-side.
"""

import re
from datetime import UTC, datetime, timedelta

from src.services.units import categorize_material, convert_to_gallons

# ---------------------------------------------------------------------------
# Water body patterns
# ---------------------------------------------------------------------------
_WATER_BODY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\blake\s*st\.?\s*clair\b", re.I), "lake_st_clair"),
    (re.compile(r"\bclinton\s+river\b", re.I), "clinton_river"),
    # Named county drains (from MCPWO protocol / Environmental Action Report)
    (re.compile(r"\b(vermander|big\s+beaver|chapaton)\b", re.I), "county_drain"),
    (re.compile(r"\b(county\s+drain|drain\s+district)\b", re.I), "county_drain"),
    # Named tributaries/creeks in Macomb County
    (re.compile(r"\b(red\s+run|plum\s+brook|bear\s+creek|north\s+branch)\b", re.I), "tributary"),
    (re.compile(r"\b(tributary|creek|brook|stream|ditch)\b", re.I), "tributary"),
    # Storm sewer / MS4 (per MCPWO protocol: County Municipal Separate Storm Sewer Systems)
    (re.compile(r"\b(storm\s+(drain|sewer)|storm\s*water|stormwater|MS4|catch\s+basin)\b", re.I), "storm_sewer"),
]

# ---------------------------------------------------------------------------
# Quantity patterns
# ---------------------------------------------------------------------------
_QUANTITY_RE = re.compile(
    r"(?:about|approximately|approx\.?|~|around|less\s+than|more\s+than|over|nearly)?\s*"
    r"(\d[\d,]*(?:\.\d+)?)\s*"
    r"(gal(?:lons?)?|bbl|barrels?|liters?|litres?|lbs?|pounds?|L(?![a-z]))",
    re.I,
)

_UNIT_NORMALIZE: dict[str, str] = {
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "bbl": "bbl",
    "barrel": "bbl",
    "barrels": "bbl",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "l": "L",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
}

# ---------------------------------------------------------------------------
# Location patterns — Macomb County municipalities
# ---------------------------------------------------------------------------
_MACOMB_PLACES = [
    "Mount Clemens",
    "Mt. Clemens",
    "Mt Clemens",
    "Sterling Heights",
    "Clinton Township",
    "Shelby Township",
    "Macomb Township",
    "Harrison Township",
    "Chesterfield Township",
    "St. Clair Shores",
    "Roseville",
    "Warren",
    "Fraser",
    "Eastpointe",
    "Center Line",
    "Utica",
    "New Baltimore",
    "Romeo",
    "Richmond",
    "Armada",
    "Memphis",
    "New Haven",
    "Ray Township",
    "Lenox Township",
    "Bruce Township",
    "Washington Township",
]

_PLACE_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _MACOMB_PLACES) + r")\b",
    re.I,
)

# Coordinate pattern: decimal degrees
_COORD_RE = re.compile(
    r"(-?\d{1,3}\.\d{2,8})\s*[,\s]+\s*(-?\d{1,3}\.\d{2,8})",
)

# ---------------------------------------------------------------------------
# Time patterns
# ---------------------------------------------------------------------------
_RELATIVE_TIME_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\b(\d+)\s+hours?\s+ago\b", re.I), 0),  # group(1) = hours
    (re.compile(r"\b(\d+)\s+minutes?\s+ago\b", re.I), 0),  # handled separately
    (re.compile(r"\bthis\s+morning\b", re.I), -1),  # sentinel: use 8am today
    (re.compile(r"\byesterday\b", re.I), -2),  # sentinel: use yesterday noon
    (re.compile(r"\bjust\s+now\b", re.I), -3),  # sentinel: use now
]

# ---------------------------------------------------------------------------
# Material detail extraction — specific substance name
# ---------------------------------------------------------------------------
_DETAIL_SUBSTANCES = [
    # Oil/petroleum — per MCPWO protocol OPA 90 routing & Environmental Action Report
    "diesel",
    "gasoline",
    "motor oil",
    "heating oil",
    "jet fuel",
    "crude oil",
    "fuel oil",
    "hydraulic fluid",
    "kerosene",
    "lubricant",
    "grease",
    "oil sheen",
    "oil plume",
    # Chemical/hazmat — per MCPWO protocol County HAZMAT team routing
    "antifreeze",
    "paint",
    "solvent",
    "pesticide",
    "herbicide",
    "fertilizer",
    "ammonia",
    "chlorine",
    "bleach",
    "caustic",
    "acid",
    # Sewage — per MCPWO protocol Operations/Flow Manager + MDEQ PEAS routing
    "sewage",
    "wastewater",
    "septic",
    "effluent",
    "biosolid",
    "sewer overflow",
]

_DETAIL_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _DETAIL_SUBSTANCES) + r")\b",
    re.I,
)


def parse_spill_text(text: str) -> dict:
    """Parse a free-text spill description into structured fields.

    Returns a dict with whatever fields could be extracted. Keys match
    IncidentCreate field names. Missing fields are omitted (not None).
    """
    result: dict = {}

    # --- Water body ---
    for pattern, water_body in _WATER_BODY_PATTERNS:
        if pattern.search(text):
            result["water_body"] = water_body
            break

    # --- Material ---
    material = categorize_material(text)
    if material != "unknown_other":
        result["material"] = material
    else:
        # Still set it — the reporter can override
        result["material"] = "unknown_other"

    # Material detail (specific substance)
    detail_match = _DETAIL_RE.search(text)
    if detail_match:
        result["material_detail"] = detail_match.group(1).lower()

    # --- Quantity ---
    qty_match = _QUANTITY_RE.search(text)
    if qty_match:
        raw_qty = float(qty_match.group(1).replace(",", ""))
        raw_unit = qty_match.group(2).lower()
        unit = _UNIT_NORMALIZE.get(raw_unit, "gal")
        result["quantity"] = raw_qty
        result["quantity_unit"] = unit
        try:
            result["quantity_gallons"] = convert_to_gallons(raw_qty, unit)
        except ValueError:
            pass

    # --- Location ---
    # Check for coordinates first
    coord_match = _COORD_RE.search(text)
    if coord_match:
        val1 = float(coord_match.group(1))
        val2 = float(coord_match.group(2))
        # Determine which is lat/lon based on Macomb County bounds
        # lat: 42.4-42.8, lon: -83.2 to -82.6
        if 42.0 <= val1 <= 43.0 and -84.0 <= val2 <= -82.0:
            result["location"] = {"lat": val1, "lon": val2}
        elif 42.0 <= val2 <= 43.0 and -84.0 <= val1 <= -82.0:
            result["location"] = {"lat": val2, "lon": val1}

    # Check for place names (for address hint)
    place_match = _PLACE_RE.search(text)
    if place_match:
        result["address_hint"] = place_match.group(1)

    # --- Time ---
    time_result = _parse_time(text)
    if time_result:
        result["time_observed"] = time_result.isoformat()

    return result


def _parse_time(text: str) -> datetime | None:
    """Extract time from text. Returns datetime or None."""
    now = datetime.now(UTC)

    # "X hours ago"
    hours_match = re.search(r"\b(\d+)\s+hours?\s+ago\b", text, re.I)
    if hours_match:
        hours = int(hours_match.group(1))
        return now - timedelta(hours=hours)

    # "X minutes ago"
    mins_match = re.search(r"\b(\d+)\s+minutes?\s+ago\b", text, re.I)
    if mins_match:
        mins = int(mins_match.group(1))
        return now - timedelta(minutes=mins)

    # "this morning"
    if re.search(r"\bthis\s+morning\b", text, re.I):
        return now.replace(hour=8, minute=0, second=0, microsecond=0)

    # "yesterday"
    if re.search(r"\byesterday\b", text, re.I):
        return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)

    # "just now"
    if re.search(r"\bjust\s+now\b", text, re.I):
        return now

    return None
