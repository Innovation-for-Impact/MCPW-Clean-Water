import uuid

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from src.api.dependencies import get_db
from src.models.incident import Incident as IncidentModel
from src.schemas.enums import IncidentStatus
from src.schemas.incident import Incident, IncidentCreate
from src.services.events import dispatch_webhooks
from src.services.incidents import create_incident

router = APIRouter()


@router.post("/incidents", response_model=Incident, status_code=201)
async def post_incident(body: IncidentCreate, db: AsyncSession = Depends(get_db)):
    incident, event = await create_incident(db, body)

    # Dispatch webhooks in background — doesn't block the response
    task = BackgroundTask(dispatch_webhooks, db, event)

    result = Incident(
        id=incident.id,
        location=body.location,
        water_body=body.water_body,
        material=body.material,
        material_detail=incident.material_detail,
        quantity=incident.quantity,
        quantity_unit=body.quantity_unit,
        quantity_gallons=incident.quantity_gallons,
        time_observed=incident.time_observed,
        reporter_name=incident.reporter_name,
        reporter_phone=incident.reporter_phone,
        notes=incident.notes,
        buffer_radius_m=incident.buffer_radius_m,
        status=IncidentStatus(incident.status),
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
    return JSONResponse(
        content=result.model_dump(mode="json"),
        status_code=201,
        background=task,
    )


@router.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    geom = cast(IncidentModel.location, Geometry(srid=4326))
    stmt = select(
        IncidentModel,
        ST_Y(geom).label("lat"),
        ST_X(geom).label("lon"),
    ).where(IncidentModel.id == incident_id)
    result = await db.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident, lat, lon = row

    return Incident(
        id=incident.id,
        location={"lat": lat, "lon": lon, "address": incident.address},
        water_body=incident.water_body,
        material=incident.material,
        material_detail=incident.material_detail,
        quantity=incident.quantity,
        quantity_unit=incident.quantity_unit,
        quantity_gallons=incident.quantity_gallons,
        time_observed=incident.time_observed,
        reporter_name=incident.reporter_name,
        reporter_phone=incident.reporter_phone,
        notes=incident.notes,
        buffer_radius_m=incident.buffer_radius_m,
        status=IncidentStatus(incident.status),
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
