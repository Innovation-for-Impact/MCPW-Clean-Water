import json

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.jurisdiction import Jurisdiction
from src.models.waterway import Waterway

router = APIRouter()

VALID_JURISDICTION_LAYERS = {
    "municipality",
    "shoreline",
    "county",
    "subwatershed",
}


@router.get("/layers/jurisdictions/{layer_name}")
async def get_jurisdiction_layer(
    layer_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a GeoJSON FeatureCollection for a jurisdiction layer."""
    if layer_name not in VALID_JURISDICTION_LAYERS:
        raise HTTPException(
            status_code=404,
            detail=f"Layer '{layer_name}' not found. Valid layers: {sorted(VALID_JURISDICTION_LAYERS)}",
        )

    stmt = select(
        Jurisdiction.jurisdiction_id,
        Jurisdiction.name,
        Jurisdiction.layer,
        ST_AsGeoJSON(Jurisdiction.geometry).label("geojson"),
    ).where(Jurisdiction.layer == layer_name)

    result = await db.execute(stmt)
    rows = result.all()

    features = []
    for row in rows:
        geom = json.loads(row.geojson) if row.geojson else None
        features.append({
            "type": "Feature",
            "properties": {
                "jurisdiction_id": row.jurisdiction_id,
                "name": row.name,
                "layer": row.layer,
            },
            "geometry": geom,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/layers/jurisdictions")
async def list_jurisdiction_layers(
    db: AsyncSession = Depends(get_db),
):
    """Return available jurisdiction layers and their feature counts."""
    stmt = select(Jurisdiction.layer, func.count()).group_by(Jurisdiction.layer)
    result = await db.execute(stmt)
    rows = result.all()
    return {
        "layers": [
            {"name": row[0], "count": row[1]}
            for row in rows
        ]
    }


@router.get("/layers/waterways")
async def get_waterways_layer(
    db: AsyncSession = Depends(get_db),
    named_only: bool = Query(default=True, description="Only return flowlines with names"),
    limit: int = Query(default=1000, le=5000),
    offset: int = Query(default=0, ge=0),
):
    """Return a GeoJSON FeatureCollection of waterway flowlines."""
    stmt = select(
        Waterway.nhd_comid,
        Waterway.name,
        Waterway.has_beach_downstream,
        Waterway.has_intake_downstream,
        ST_AsGeoJSON(Waterway.geometry).label("geojson"),
    )

    if named_only:
        stmt = stmt.where(Waterway.name.isnot(None))

    stmt = stmt.order_by(Waterway.name, Waterway.nhd_comid).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    features = []
    for row in rows:
        geom = json.loads(row.geojson) if row.geojson else None
        features.append({
            "type": "Feature",
            "properties": {
                "nhd_comid": row.nhd_comid,
                "name": row.name,
                "has_beach_downstream": row.has_beach_downstream,
                "has_intake_downstream": row.has_intake_downstream,
            },
            "geometry": geom,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
