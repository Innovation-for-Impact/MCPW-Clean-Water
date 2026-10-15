"""
WS3 → WS1: Serve jurisdiction layers as GeoJSON for map overlays.

GET /layers/{layer_name} returns a GeoJSON FeatureCollection with
jurisdiction_id and name on each feature, so WS1 can match highlighted
jurisdictions to lookup results.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.user import User

router = APIRouter(prefix="/layers")

VALID_LAYERS = {
    "municipality",
    "drain_district",
    "subwatershed",
    "water_body",
    "shoreline",
    "county",
}


MAX_FEATURES = 500


@router.get("/{layer_name}")
async def get_layer(
    layer_name: str,
    limit: int = MAX_FEATURES,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("viewer", "responder", "admin")),
):
    """Return a GeoJSON FeatureCollection for a jurisdiction layer.

    Supports pagination via `limit` (default 500) and `offset` query params.
    """
    if layer_name not in VALID_LAYERS:
        raise HTTPException(status_code=404, detail=f"Unknown layer: {layer_name}")

    if limit > MAX_FEATURES:
        limit = MAX_FEATURES

    result = await db.execute(
        text("""
            SELECT
                jurisdiction_id,
                name,
                ST_AsGeoJSON(ST_Simplify(geometry::geometry, 0.0001)) AS geojson
            FROM jurisdictions
            WHERE layer = :layer
            ORDER BY name
            LIMIT :limit OFFSET :offset
        """),
        {"layer": layer_name, "limit": limit, "offset": offset},
    )
    rows = result.all()

    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "jurisdiction_id": row.jurisdiction_id,
                "name": row.name,
            },
            "geometry": json.loads(row.geojson),
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/")
async def list_layers(
    _user: User = Depends(RequireRole("viewer", "responder", "admin")),
):
    """List available jurisdiction layers."""
    return {"layers": sorted(VALID_LAYERS)}
