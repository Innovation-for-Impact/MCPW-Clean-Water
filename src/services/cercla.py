"""CERCLA Reportable Quantities (RQ) lookup — 40 CFR 302.4.

Provides RQ thresholds for common spill materials. When a spill quantity
meets or exceeds the RQ for a substance, federal NRC notification is
required under CERCLA § 103(a).

This table covers the most common materials encountered in Macomb County
spill response. For a complete list, see EPA's 40 CFR 302.4 Table 302.4.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SubstanceRQ:
    """Reportable Quantity entry for a hazardous substance."""

    cas_number: str | None  # CAS registry number (None for categories)
    substance: str  # Common name
    rq_lbs: float  # Reportable quantity in pounds
    rq_gallons: float | None  # Approximate RQ in gallons (for liquids; None for solids/gases)
    category: str  # Maps to MaterialType enum value
    citation: str  # Regulatory citation


# Common substances encountered in Macomb County spill response
# Source: 40 CFR 302.4 Table 302.4
CERCLA_RQ_TABLE: list[SubstanceRQ] = [
    # Oil & Fuel
    SubstanceRQ("68476-34-6", "Diesel fuel (No. 2)", 25, 3.6, "oil_fuel", "40 CFR 302.4"),
    SubstanceRQ("8006-61-9", "Gasoline", 1, 0.14, "oil_fuel", "40 CFR 302.4"),
    SubstanceRQ("8012-95-1", "Petroleum oil (crude)", 1, 0.14, "oil_fuel", "40 CFR 302.4"),
    SubstanceRQ("64742-65-0", "Hydraulic oil", 1, 0.14, "oil_fuel", "40 CFR 302.4"),
    SubstanceRQ("8008-20-6", "Kerosene", 100, 14.3, "oil_fuel", "40 CFR 302.4"),
    SubstanceRQ(None, "Used/waste oil", 1, 0.14, "oil_fuel", "40 CFR 302.4; 40 CFR 279"),
    # Chemical / Hazmat
    SubstanceRQ("7664-93-9", "Sulfuric acid", 1000, None, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("7647-01-0", "Hydrochloric acid", 5000, None, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("1310-73-2", "Sodium hydroxide (caustic)", 1000, None, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("7664-41-7", "Ammonia", 100, None, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("7782-50-5", "Chlorine", 10, None, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("67-56-1", "Methanol", 5000, 757.0, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("1330-20-7", "Xylene", 100, 13.8, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("71-43-2", "Benzene", 10, 1.4, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("108-88-3", "Toluene", 1000, 138.0, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("7681-52-9", "Sodium hypochlorite (bleach)", 100, None, "chemical_hazmat", "40 CFR 302.4"),
    SubstanceRQ("57-12-5", "Cyanide", 10, None, "chemical_hazmat", "40 CFR 302.4"),
    # Sewage — not directly in 302.4, but triggers CWA § 311
    SubstanceRQ(None, "Raw sewage/sanitary overflow", 0, 0, "sewage", "CWA § 311; MDEQ Part 31"),
]


def lookup_rq(material_category: str, quantity_lbs: float | None = None) -> list[SubstanceRQ]:
    """Return all CERCLA substances matching a material category.

    If quantity_lbs is provided, only returns substances whose RQ is
    met or exceeded by the given quantity.
    """
    matches = [s for s in CERCLA_RQ_TABLE if s.category == material_category]
    if quantity_lbs is not None:
        matches = [s for s in matches if quantity_lbs >= s.rq_lbs]
    return matches


def check_federal_reporting_required(
    material_category: str,
    quantity_gallons: float | None = None,
    quantity_lbs: float | None = None,
) -> dict:
    """Check if a spill triggers federal CERCLA reporting requirements.

    Returns a dict with:
      - required: bool — whether any RQ is exceeded
      - triggered_substances: list of SubstanceRQ entries that are exceeded
      - note: human-readable summary
    """
    if material_category == "sewage":
        return {
            "required": True,
            "triggered_substances": [s for s in CERCLA_RQ_TABLE if s.category == "sewage"],
            "note": (
                "Sewage/sanitary overflows require notification under CWA § 311"
                " and MDEQ Part 31 regardless of quantity."
            ),
        }

    if quantity_gallons is None and quantity_lbs is None:
        return {
            "required": False,
            "triggered_substances": [],
            "note": "Quantity unknown — cannot determine if RQ is exceeded. Recommend reporting as precaution.",
        }

    # Convert gallons to approximate lbs for comparison (using ~7 lb/gal for petroleum)
    effective_lbs = quantity_lbs
    if effective_lbs is None and quantity_gallons is not None:
        effective_lbs = quantity_gallons * 7.0  # conservative estimate for petroleum

    triggered = lookup_rq(material_category, effective_lbs)
    if triggered:
        names = ", ".join(s.substance for s in triggered)
        return {
            "required": True,
            "triggered_substances": triggered,
            "note": f"Reportable quantity exceeded for: {names}. NRC notification required under CERCLA § 103(a).",
        }

    return {
        "required": False,
        "triggered_substances": [],
        "note": "Quantity below all CERCLA reportable quantity thresholds for this material category.",
    }
