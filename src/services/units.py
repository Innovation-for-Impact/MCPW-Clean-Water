"""Unit conversion and material categorization for spill intake.

Converts between quantity units and normalizes to gallons (the standard
unit used by rules engine thresholds). Also maps free-text material
descriptions to the MaterialType enum for WS2 intake parsing.
"""

import re

# Conversion factors TO gallons
_TO_GALLONS: dict[str, float] = {
    "gal": 1.0,
    "bbl": 42.0,  # US petroleum barrel
    "L": 0.264172,
    "lb": 0.12,  # approximate for petroleum products (~7.1 lb/gal → 1/7.1 ≈ 0.14; using 0.12 as conservative)
}

# Conversion factors FROM gallons
_FROM_GALLONS: dict[str, float] = {unit: 1.0 / factor for unit, factor in _TO_GALLONS.items()}

# Material keyword patterns → MaterialType enum values
_MATERIAL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\b(oil|fuel|diesel|gasoline|petrol|kerosene|hydraulic fluid|motor oil|jet fuel)\b", re.I),
        "oil_fuel",
    ),
    (
        re.compile(
            r"\b(chemical|hazmat|hazardous|solvent|acid|caustic|pesticide|herbicide|ammonia|chlorine|bleach)\b", re.I
        ),
        "chemical_hazmat",
    ),
    (re.compile(r"\b(sewage|wastewater|sanitary|septic|effluent|fecal|biosolid)\b", re.I), "sewage"),
]


def convert_to_gallons(quantity: float, from_unit: str) -> float:
    """Convert a quantity from the given unit to gallons.

    Raises ValueError if the unit is not recognized.
    """
    factor = _TO_GALLONS.get(from_unit)
    if factor is None:
        raise ValueError(f"Unknown unit: {from_unit}. Supported: {list(_TO_GALLONS.keys())}")
    return round(quantity * factor, 4)


def convert_from_gallons(gallons: float, to_unit: str) -> float:
    """Convert gallons to another unit.

    Raises ValueError if the unit is not recognized.
    """
    factor = _FROM_GALLONS.get(to_unit)
    if factor is None:
        raise ValueError(f"Unknown unit: {to_unit}. Supported: {list(_FROM_GALLONS.keys())}")
    return round(gallons * factor, 4)


def convert_units(quantity: float, from_unit: str, to_unit: str) -> float:
    """Convert a quantity between any two supported units."""
    gallons = convert_to_gallons(quantity, from_unit)
    return convert_from_gallons(gallons, to_unit)


def categorize_material(text: str) -> str:
    """Categorize free-text material description into a MaterialType value.

    Returns the first matching category, or 'unknown_other' if no match.
    """
    for pattern, category in _MATERIAL_PATTERNS:
        if pattern.search(text):
            return category
    return "unknown_other"
