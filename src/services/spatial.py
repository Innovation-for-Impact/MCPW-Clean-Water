"""
WS3 spatial service functions.

Provides low-level spatial queries against the PostGIS jurisdictions and
waterways tables. Used by test_spatial.py boundary tests and can be
called independently of the lookup/rules engine.
"""
from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jurisdiction import Jurisdiction as JurisdictionModel
from src.models.waterway import Waterway as WaterwayModel


async def lookup_jurisdictions(
    lat: float, lon: float, *, db: AsyncSession, buffer_m: float = 0
) -> list[dict]:
    """Find all jurisdictions that contain or intersect a point.

    Returns a list of dicts with keys: layer, jurisdiction_id, name.
    """
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
    spatial_filter = ST_DWithin(JurisdictionModel.geometry, point, buffer_m)

    stmt = select(JurisdictionModel).where(spatial_filter)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "layer": j.layer,
            "jurisdiction_id": j.jurisdiction_id,
            "name": j.name,
        }
        for j in rows
    ]


async def find_nearest_water(
    lat: float, lon: float, *, db: AsyncSession, max_distance_m: float = 500
) -> dict | None:
    """Find the nearest waterway within max_distance_m of a point.

    Returns a dict with keys: name, nhd_comid, distance_m, or None if
    no waterway is within range.
    """
    point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
    distance = ST_Distance(WaterwayModel.geometry, point).label("distance_m")

    stmt = (
        select(WaterwayModel, distance)
        .where(ST_DWithin(WaterwayModel.geometry, point, max_distance_m))
        .order_by(distance)
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        return None

    waterway, dist = row
    return {
        "name": waterway.name,
        "nhd_comid": waterway.nhd_comid,
        "distance_m": dist,
    }


async def trace_downstream(nhd_comid: int, *, db: AsyncSession, max_hops: int = 50) -> list[dict]:
    """Trace downstream from a waterway segment, returning the path.

    Returns a list of dicts with keys: name, nhd_comid,
    has_beach_downstream, has_intake_downstream.

    Uses a recursive CTE on PostGIS or falls back to iterative lookup on SQLite.
    """
    # Try recursive CTE first (PostGIS)
    try:
        result = await db.execute(
            text("""
                WITH RECURSIVE downstream AS (
                    SELECT nhd_comid, name, downstream_comid,
                           has_beach_downstream, has_intake_downstream, 1 AS depth
                    FROM waterways WHERE nhd_comid = :start_comid
                    UNION ALL
                    SELECT w.nhd_comid, w.name, w.downstream_comid,
                           w.has_beach_downstream, w.has_intake_downstream, d.depth + 1
                    FROM waterways w
                    JOIN downstream d ON w.nhd_comid = d.downstream_comid
                    WHERE d.depth < :max_hops AND d.downstream_comid IS NOT NULL
                )
                SELECT nhd_comid, name, has_beach_downstream, has_intake_downstream
                FROM downstream ORDER BY depth
            """),
            {"start_comid": nhd_comid, "max_hops": max_hops},
        )
        rows = result.fetchall()
        return [
            {
                "name": row[1],
                "nhd_comid": row[0],
                "has_beach_downstream": row[2],
                "has_intake_downstream": row[3],
            }
            for row in rows
        ]
    except Exception:
        # Fallback for SQLite (no recursive CTE on waterways table in test mode)
        path = []
        current_comid = nhd_comid
        visited: set[int] = set()

        for _ in range(max_hops):
            if current_comid is None or current_comid in visited:
                break
            visited.add(current_comid)

            stmt = select(WaterwayModel).where(WaterwayModel.nhd_comid == current_comid)
            result = await db.execute(stmt)
            waterway = result.scalar_one_or_none()

            if waterway is None:
                break

            path.append({
                "name": waterway.name,
                "nhd_comid": waterway.nhd_comid,
                "has_beach_downstream": waterway.has_beach_downstream,
                "has_intake_downstream": waterway.has_intake_downstream,
            })

            current_comid = waterway.downstream_comid

        return path
