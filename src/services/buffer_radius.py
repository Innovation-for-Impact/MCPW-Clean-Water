"""Buffer radius computation from spill quantity.

Computes the spatial buffer radius (in meters) for a spill based on
its quantity in gallons. Used by:
- WS1: map buffer overlay
- WS2: auto-fill buffer_radius_m in intake form
- WS3: spatial query buffer for jurisdiction lookup

The lookup table uses tiered thresholds based on EPA guidance for
initial spill response zones. Values are conservative defaults;
actual spread depends on terrain, flow, and material properties.
"""

# (max_gallons, radius_meters) — ordered ascending by threshold
# None as max_gallons means "unlimited" (catch-all)
_BUFFER_TABLE: list[tuple[float | None, float]] = [
    (1, 50),  # < 1 gal: minor drip, 50m buffer
    (10, 100),  # 1-10 gal: small spill, 100m
    (50, 250),  # 10-50 gal: moderate spill, 250m
    (100, 500),  # 50-100 gal: significant spill, 500m
    (500, 1000),  # 100-500 gal: large spill, 1km
    (1000, 2000),  # 500-1000 gal: major spill, 2km
    (None, 5000),  # 1000+ gal: catastrophic, 5km
]

# Default buffer when quantity is unknown
DEFAULT_BUFFER_M = 500.0


def compute_buffer_radius(quantity_gallons: float | None) -> float:
    """Compute buffer radius in meters from quantity in gallons.

    Returns DEFAULT_BUFFER_M (500m) if quantity is None or zero.
    """
    if quantity_gallons is None or quantity_gallons <= 0:
        return DEFAULT_BUFFER_M

    for max_gal, radius in _BUFFER_TABLE:
        if max_gal is None or quantity_gallons <= max_gal:
            return radius

    return _BUFFER_TABLE[-1][1]


def get_buffer_table() -> list[dict]:
    """Return the buffer lookup table for API exposure / frontend sync."""
    return [
        {
            "max_gallons": max_gal,
            "radius_meters": radius,
        }
        for max_gal, radius in _BUFFER_TABLE
    ]
