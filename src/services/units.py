"""Unit conversion and material categorization for spill intake.

Converts between quantity units and normalizes to gallons (the standard
unit used by rules engine thresholds). Material categorization loads
keywords from shared/material-categories.json (shared with frontend WS2).
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Conversion factors TO gallons
_TO_GALLONS: dict[str, float] = {
    "gal": 1.0,
    "bbl": 42.0,  # US petroleum barrel
    "L": 0.264172,
    "lb": 1 / 7.0,  # approximate for petroleum products (~7 lb/gal); matches cercla.py
}

# Conversion factors FROM gallons
_FROM_GALLONS: dict[str, float] = {unit: 1.0 / factor for unit, factor in _TO_GALLONS.items()}

# Load material categories from shared JSON
_CATEGORIES_PATH = Path(__file__).resolve().parent.parent.parent / "shared" / "material-categories.json"
_MATERIAL_CATEGORIES: dict[str, list[str]] = {}
if _CATEGORIES_PATH.exists():
    _raw = json.loads(_CATEGORIES_PATH.read_text())
    # Key order is significant — first matching category wins in categorize_material()
    _MATERIAL_CATEGORIES = {k: v for k, v in _raw.items() if not k.startswith("_") and isinstance(v, list)}
else:
    logger.warning("material-categories.json not found at %s — all materials will be 'unknown_other'", _CATEGORIES_PATH)

# Build regex patterns from the JSON keywords
_MATERIAL_PATTERNS: list[tuple[re.Pattern, str]] = []
for category, keywords in _MATERIAL_CATEGORIES.items():
    if keywords:
        escaped = [re.escape(k) for k in keywords]
        pattern = re.compile(r"\b(" + "|".join(escaped) + r")\b", re.I)
        _MATERIAL_PATTERNS.append((pattern, category))


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

    Matches against keywords in shared/material-categories.json.
    Returns the first matching category, or 'unknown_other' if no match.
    """
    for pattern, category in _MATERIAL_PATTERNS:
        if pattern.search(text):
            return category
    return "unknown_other"


def get_material_categories() -> dict[str, list[str]]:
    """Return the full material categories mapping (for API exposure)."""
    return dict(_MATERIAL_CATEGORIES)
