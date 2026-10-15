"""
WS3 Spatial Services — jurisdiction lookup, drain/water snapping, downstream tracing.

All spatial queries use PostGIS functions on EPSG:4326 geography columns.
"""

from dataclasses import dataclass, field

from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.drain import Drain, DrainSegment, ResponseSite
from src.models.jurisdiction import Jurisdiction
from src.models.waterway import Waterway


# ---------- Result types ----------

@dataclass
class JurisdictionHit:
    layer: str
    jurisdiction_id: str
    name: str


@dataclass
class DrainHit:
    drain_id: str
    segment_id: str
    name: str
    tier: str
    conveyance_owner: str
    conveyance_type: str
    distance_m: float


@dataclass
class WaterHit:
    name: str | None
    nhd_comid: int | None
    distance_m: float


@dataclass
class InterceptPoint:
    name: str
    source: str  # 'plan' or 'computed'
    plan_sheet: str | None


@dataclass
class SpatialResult:
    jurisdictions: list[JurisdictionHit] = field(default_factory=list)
    drain: DrainHit | None = None
    nearest_water: WaterHit | None = None
    first_major_drain_downstream: dict | None = None
    next_intercept_point: InterceptPoint | None = None
    downstream_path: list[str] = field(default_factory=list)
    upstream_counties: list[str] = field(default_factory=list)
    flags: dict = field(default_factory=lambda: {
        "beach_downstream": False,
        "intake_downstream": False,
        "outside_county": False,
        "excluded_procedure": False,
    })


# ---------- 2.1 Jurisdiction lookup ----------

async def lookup_jurisdictions(
    db: AsyncSession,
    lat: float,
    lon: float,
    buffer_radius_m: float | None = None,
) -> list[JurisdictionHit]:
    """
    Return every jurisdiction that intersects a point (or buffered point).

    Edge cases:
    - Point on a boundary line → returns both adjacent jurisdictions (ST_DWithin with 0m)
    - Point outside Macomb County → returns empty list (caller sets outside_county flag)
    - Buffer crosses county lines → only Macomb County jurisdictions returned
    """
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
    radius = buffer_radius_m if buffer_radius_m and buffer_radius_m > 0 else 0

    stmt = (
        select(
            Jurisdiction.layer,
            Jurisdiction.jurisdiction_id,
            Jurisdiction.name,
        )
        .where(ST_DWithin(Jurisdiction.geometry, point, radius))
        .order_by(Jurisdiction.layer, Jurisdiction.name)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        JurisdictionHit(layer=r.layer, jurisdiction_id=r.jurisdiction_id, name=r.name)
        for r in rows
    ]


# ---------- 2.2a Find nearest drain ----------

async def find_nearest_drain(
    db: AsyncSession,
    lat: float,
    lon: float,
    max_distance_m: float = 200,
) -> DrainHit | None:
    """
    Snap to the nearest county drain segment within max_distance_m.

    Returns drain metadata including tier, conveyance owner, and conveyance type.
    Returns None if no drain segment is within range.
    """
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

    stmt = text("""
        SELECT
            d.drain_id,
            ds.segment_id,
            d.name AS drain_name,
            d.tier,
            d.conveyance_owner,
            ds.conveyance_type,
            ST_Distance(ds.geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m
        FROM drain_segments ds
        JOIN drains d ON d.drain_id = ds.drain_id
        WHERE ST_DWithin(ds.geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :max_dist)
        ORDER BY distance_m
        LIMIT 1
    """)

    result = await db.execute(stmt, {"lat": lat, "lon": lon, "max_dist": max_distance_m})
    row = result.first()

    if row is None:
        return None

    return DrainHit(
        drain_id=row.drain_id,
        segment_id=row.segment_id,
        name=row.drain_name,
        tier=row.tier,
        conveyance_owner=row.conveyance_owner,
        conveyance_type=row.conveyance_type,
        distance_m=row.distance_m,
    )


# ---------- 2.2b Find nearest water (NHD fallback) ----------

async def find_nearest_water(
    db: AsyncSession,
    lat: float,
    lon: float,
    max_distance_m: float = 500,
) -> WaterHit | None:
    """
    Find the nearest NHD waterway segment to the spill point.

    Used as fallback when no county drain is within range of find_nearest_drain.
    """
    stmt = text("""
        SELECT
            name,
            nhd_comid,
            ST_Distance(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m
        FROM waterways
        WHERE ST_DWithin(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :max_dist)
        ORDER BY distance_m
        LIMIT 1
    """)

    result = await db.execute(stmt, {"lat": lat, "lon": lon, "max_dist": max_distance_m})
    row = result.first()

    if row is None:
        return None

    return WaterHit(name=row.name, nhd_comid=row.nhd_comid, distance_m=row.distance_m)


# ---------- 2.2c Downstream trace ----------

MAX_TRACE_DEPTH = 100


async def _trace_drain_to_outlet(
    db: AsyncSession,
    drain_id: str,
    start_segment_id: str | None = None,
) -> tuple[list[str], int | None, dict | None, InterceptPoint | None]:
    """
    Walk drain_segments downstream to the outlet.

    Returns:
        - path: list of drain names traversed
        - outlet_nhd_comid: NHD COMID where the drain discharges (or None)
        - first_major: dict with drain_id/name/tier if a Tier 1/2 drain is reached
        - intercept: nearest downstream response site (plan sites preferred)
    """
    path: list[str] = []
    outlet_comid: int | None = None
    first_major: dict | None = None
    intercept: InterceptPoint | None = None

    # Get all segments for this drain ordered by downstream linkage, with drain info JOINed
    result = await db.execute(
        text("""
            WITH RECURSIVE trace AS (
                SELECT segment_id, drain_id, downstream_segment_id, outlet_nhd_comid,
                       1 AS depth, ARRAY[segment_id] AS visited
                FROM (
                    SELECT segment_id, drain_id, downstream_segment_id, outlet_nhd_comid
                    FROM drain_segments
                    WHERE drain_id = :drain_id
                      AND (segment_id = :start_seg OR :start_seg IS NULL)
                    ORDER BY segment_id
                    LIMIT 1
                ) anchor
                UNION ALL
                SELECT ds.segment_id, ds.drain_id, ds.downstream_segment_id, ds.outlet_nhd_comid,
                       t.depth + 1, t.visited || ds.segment_id
                FROM drain_segments ds
                JOIN trace t ON ds.segment_id = t.downstream_segment_id
                WHERE t.depth < :max_depth
                  AND ds.segment_id <> ALL(t.visited)
            )
            SELECT t.segment_id, t.drain_id, t.downstream_segment_id, t.outlet_nhd_comid,
                   d.name AS drain_name, d.tier AS drain_tier
            FROM trace t
            JOIN drains d ON d.drain_id = t.drain_id
            ORDER BY t.depth
        """),
        {"drain_id": drain_id, "start_seg": start_segment_id, "max_depth": MAX_TRACE_DEPTH},
    )
    segments = result.all()

    visited_drains: set[str] = set()
    for seg in segments:
        if seg.drain_id not in visited_drains:
            path.append(seg.drain_name)
            visited_drains.add(seg.drain_id)
            if first_major is None and seg.drain_tier in ("1", "2") and seg.drain_id != drain_id:
                first_major = {"drain_id": seg.drain_id, "name": seg.drain_name, "tier": seg.drain_tier}

        if seg.outlet_nhd_comid:
            outlet_comid = seg.outlet_nhd_comid

    # Find nearest downstream response site (plan preferred over computed)
    # Check starting drain first, then the first major drain downstream
    search_drain_ids = [drain_id]
    if first_major:
        search_drain_ids.append(first_major["drain_id"])

    for search_id in search_drain_ids:
        site_result = await db.execute(
            select(ResponseSite)
            .where(ResponseSite.drain_id == search_id)
            .order_by(
                # Prefer plan sites over computed
                text("CASE WHEN source = 'plan' THEN 0 ELSE 1 END"),
                ResponseSite.site_order,
            )
            .limit(1)
        )
        site = site_result.scalar()
        if site:
            intercept = InterceptPoint(
                name=site.name, source=site.source, plan_sheet=site.plan_sheet
            )
            break

    return path, outlet_comid, first_major, intercept


async def _trace_nhd_downstream(
    db: AsyncSession,
    start_comid: int,
) -> tuple[list[str], bool, bool]:
    """
    Walk NHD flowlines downstream from start_comid to the terminal water body.

    Returns:
        - path: list of water body names (deduplicated)
        - beach_downstream: True if any downstream segment has a beach
        - intake_downstream: True if any downstream segment has a drinking-water intake
    """
    result = await db.execute(
        text("""
            WITH RECURSIVE downstream AS (
                SELECT id, name, nhd_comid, downstream_comid,
                       has_beach_downstream, has_intake_downstream, 1 AS depth
                FROM waterways WHERE nhd_comid = :start_comid
                UNION ALL
                SELECT w.id, w.name, w.nhd_comid, w.downstream_comid,
                       w.has_beach_downstream, w.has_intake_downstream, d.depth + 1
                FROM waterways w
                JOIN downstream d ON w.nhd_comid = d.downstream_comid
                WHERE d.depth < :max_depth
            )
            SELECT DISTINCT name, nhd_comid, has_beach_downstream, has_intake_downstream
            FROM downstream
            ORDER BY nhd_comid
        """),
        {"start_comid": start_comid, "max_depth": MAX_TRACE_DEPTH},
    )
    rows = result.all()

    path: list[str] = []
    seen_names: set[str] = set()
    beach = False
    intake = False

    for row in rows:
        if row.name and row.name not in seen_names:
            path.append(row.name)
            seen_names.add(row.name)
        if row.has_beach_downstream:
            beach = True
        if row.has_intake_downstream:
            intake = True

    return path, beach, intake


async def trace_downstream(
    db: AsyncSession,
    drain: DrainHit | None = None,
    water: WaterHit | None = None,
) -> tuple[list[str], bool, bool, dict | None, InterceptPoint | None]:
    """
    Full downstream trace from a drain or water hit.

    Strategy:
    1. Walk drain segments first (if drain hit provided)
    2. Continue on NHD from the drain outlet
    3. Record first Tier 1/2 drain and nearest intercept point

    Returns:
        - path: ordered list of water body names to terminal water body
        - beach_downstream: flag
        - intake_downstream: flag
        - first_major_drain: dict or None
        - intercept: InterceptPoint or None
    """
    full_path: list[str] = []
    beach = False
    intake = False
    first_major: dict | None = None
    intercept: InterceptPoint | None = None

    nhd_start_comid: int | None = None

    if drain:
        drain_path, outlet_comid, first_major, intercept = await _trace_drain_to_outlet(
            db, drain.drain_id, start_segment_id=drain.segment_id
        )
        full_path.extend(drain_path)
        nhd_start_comid = outlet_comid

    if nhd_start_comid is None and water and water.nhd_comid:
        nhd_start_comid = water.nhd_comid

    if nhd_start_comid:
        nhd_path, nhd_beach, nhd_intake = await _trace_nhd_downstream(db, nhd_start_comid)
        full_path.extend(nhd_path)
        beach = beach or nhd_beach
        intake = intake or nhd_intake

    return full_path, beach, intake, first_major, intercept


# ---------- Combined spatial lookup ----------

async def run_spatial_lookup(
    db: AsyncSession,
    lat: float,
    lon: float,
    buffer_radius_m: float | None = None,
) -> SpatialResult:
    """
    Full WS3 spatial lookup for a spill point.

    Returns jurisdictions, nearest drain/water, downstream path, and all flags.
    """
    result = SpatialResult()

    # 1. Jurisdiction lookup
    result.jurisdictions = await lookup_jurisdictions(db, lat, lon, buffer_radius_m)

    if not result.jurisdictions:
        result.flags["outside_county"] = True

    # 2. Snap to nearest drain
    result.drain = await find_nearest_drain(db, lat, lon)

    # 3. Fallback to nearest NHD water if no drain
    if result.drain is None:
        result.nearest_water = await find_nearest_water(db, lat, lon)

    # 4. Downstream trace
    path, beach, intake, first_major, intercept = await trace_downstream(
        db, drain=result.drain, water=result.nearest_water
    )
    result.downstream_path = path
    result.flags["beach_downstream"] = beach
    result.flags["intake_downstream"] = intake
    result.first_major_drain_downstream = first_major
    result.next_intercept_point = intercept

    # 5. Detect upstream counties for intercounty drains
    if result.drain:
        drain_result = await db.execute(
            select(Drain.upstream_counties).where(Drain.drain_id == result.drain.drain_id)
        )
        upstream_str = drain_result.scalar()
        if upstream_str:
            result.upstream_counties = [c.strip() for c in upstream_str.split(",") if c.strip()]

    # 6. Check for excluded procedures (sanitary/combined sewers, NPDES)
    if result.drain and result.drain.conveyance_type in ("sanitary", "combined"):
        result.flags["excluded_procedure"] = True

    return result
