import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID, ST_X, ST_Y
from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.association import IncidentContact, incident_jurisdictions
from src.models.contact import Contact as ContactModel
from src.models.incident import Incident as IncidentModel
from src.schemas.enums import IncidentStatus
from src.schemas.incident import Incident, IncidentCreate
from src.schemas.lookup import LookupRequest
from src.services.events import create_event
from src.services.lookup import run_lookup

router = APIRouter()


@router.post("/incidents", response_model=Incident, status_code=201)
async def create_incident(body: IncidentCreate, db: AsyncSession = Depends(get_db)):
    point = ST_SetSRID(
        ST_MakePoint(body.location.lon, body.location.lat), 4326
    )

    incident = IncidentModel(
        id=uuid.uuid4(),
        location=point,
        address=body.location.address,
        water_body=body.water_body.value,
        material=body.material.value,
        material_detail=body.material_detail,
        quantity=body.quantity,
        quantity_unit=body.quantity_unit.value,
        quantity_gallons=body.quantity_gallons,
        time_observed=body.time_observed,
        reporter_name=body.reporter_name,
        reporter_phone=body.reporter_phone,
        notes=body.notes,
        buffer_radius_m=body.buffer_radius_m,
        status=IncidentStatus.open.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    await db.flush()

    # Run lookup and store results
    lookup_request = LookupRequest(
        location=body.location,
        material=body.material,
        quantity_gallons=body.quantity_gallons,
        buffer_radius_m=body.buffer_radius_m,
    )
    lookup_result = await run_lookup(db, lookup_request)

    # Store jurisdiction associations
    for j in lookup_result.jurisdictions:
        await db.execute(
            incident_jurisdictions.insert().values(
                incident_id=incident.id,
                jurisdiction_id=j.jurisdiction_id,
            )
        )

    # Store contact associations
    for c in lookup_result.response_contacts + lookup_result.regulatory_contacts:
        contact_row = (
            await db.execute(
                select(ContactModel).where(
                    ContactModel.jurisdiction_id == c.jurisdiction_id,
                    ContactModel.agency == c.agency,
                )
            )
        ).scalar_one_or_none()
        if contact_row:
            db.add(
                IncidentContact(
                    incident_id=incident.id,
                    contact_id=contact_row.id,
                    role=c.role.value,
                    deadline=c.reporting_deadline,
                )
            )

    # Build event payload
    event_payload = {
        "location": body.location.model_dump(),
        "material": body.material.value,
        "material_detail": body.material_detail,
        "quantity_gallons": body.quantity_gallons,
        "water_body": body.water_body.value,
        "jurisdictions": [j.model_dump() for j in lookup_result.jurisdictions],
        "contacts": [
            c.model_dump(mode="json")
            for c in lookup_result.response_contacts + lookup_result.regulatory_contacts
        ],
        "status": IncidentStatus.open.value,
    }

    await db.commit()
    await db.refresh(incident)

    # Dispatch event after commit so webhooks don't hold the DB transaction open
    await create_event(db, "incident.created", incident.id, event_payload)

    return Incident(
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
