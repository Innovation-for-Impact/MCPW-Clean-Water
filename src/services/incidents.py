import uuid
from datetime import datetime, timezone

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.association import IncidentContact, incident_jurisdictions
from src.models.contact import Contact as ContactModel
from src.models.incident import Incident as IncidentModel
from src.schemas.enums import IncidentStatus
from src.schemas.incident import IncidentCreate
from src.schemas.lookup import LookupRequest
from src.services.events import build_event
from src.services.lookup import run_lookup


async def create_incident(db: AsyncSession, body: IncidentCreate) -> tuple[IncidentModel, "Event"]:
    """Create an incident with jurisdiction/contact associations and event in a single transaction.

    Returns (incident, event) after commit. Caller dispatches webhooks as a background task.
    """
    point = ST_SetSRID(ST_MakePoint(body.location.lon, body.location.lat), 4326)

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

    # Spatial lookup + rules engine
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
    all_contacts = lookup_result.response_contacts + lookup_result.regulatory_contacts
    for c in all_contacts:
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

    # Build event in the SAME transaction
    event_payload = {
        "location": body.location.model_dump(),
        "material": body.material.value,
        "material_detail": body.material_detail,
        "quantity_gallons": body.quantity_gallons,
        "water_body": body.water_body.value,
        "jurisdictions": [j.model_dump() for j in lookup_result.jurisdictions],
        "contacts": [c.model_dump(mode="json") for c in all_contacts],
        "status": IncidentStatus.open.value,
    }
    event = build_event("incident.created", incident.id, event_payload)
    db.add(event)

    # Single atomic commit — incident + associations + event
    await db.commit()
    await db.refresh(incident)

    return incident, event
