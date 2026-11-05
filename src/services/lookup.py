import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.jurisdiction import Jurisdiction
from src.schemas.lookup import LookupRequest, LookupResult
from src.services.rules_engine import evaluate_rules
from src.services.spatial import (
    find_nearest_water,
    lookup_jurisdictions,
    trace_downstream,
)

log = logging.getLogger(__name__)


async def run_lookup(db: AsyncSession, request: LookupRequest) -> LookupResult:
    """Orchestrate WS3 spatial query + WS4 rules engine."""

    buffer_m = request.buffer_radius_m or 0
    lat, lon = request.location.lat, request.location.lon

    # WS3: spatial query — find jurisdictions that intersect the point/buffer
    jurisdiction_dicts = await lookup_jurisdictions(lat, lon, db=db, buffer_m=buffer_m)

    jurisdictions = [
        Jurisdiction(layer=j["layer"], jurisdiction_id=j["jurisdiction_id"], name=j["name"]) for j in jurisdiction_dicts
    ]
    jurisdiction_layers = list({j["layer"] for j in jurisdiction_dicts})

    # WS3: downstream tracing — find nearest water + trace path
    downstream_path: list[str] = []
    try:
        nearest = await find_nearest_water(lat, lon, db=db)
        if nearest:
            path = await trace_downstream(nearest["nhd_comid"], db=db)
            seen: set[str] = set()
            for w in path:
                if w["name"] and w["name"] not in seen:
                    seen.add(w["name"])
                    downstream_path.append(w["name"])
    except Exception:
        log.exception("Downstream tracing failed, returning empty path")

    # WS4: rules engine — find contacts based on jurisdictions + material + size
    material_value = request.material.value if request.material else None
    response_contacts, regulatory_contacts = await evaluate_rules(
        jurisdiction_layers,
        db=db,
        material=material_value,
        quantity_gallons=request.quantity_gallons,
    )

    return LookupResult(
        jurisdictions=jurisdictions,
        downstream_path=downstream_path,
        response_contacts=response_contacts,
        regulatory_contacts=regulatory_contacts,
    )
