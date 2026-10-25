import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact as ContactModel
from src.models.rule import Rule
from src.schemas.contact import Contact
from src.schemas.enums import ContactRole
from src.schemas.jurisdiction import Jurisdiction
from src.schemas.lookup import LookupRequest, LookupResult
from src.services.spatial import find_nearest_water, lookup_jurisdictions, trace_downstream

log = logging.getLogger(__name__)


async def run_lookup(db: AsyncSession, request: LookupRequest) -> LookupResult:
    """Orchestrate WS3 spatial query + WS4 rules engine."""

    buffer_m = request.buffer_radius_m or 0
    lat, lon = request.location.lat, request.location.lon

    # WS3: spatial query — find jurisdictions that intersect the point/buffer
    jurisdiction_dicts = await lookup_jurisdictions(lat, lon, db=db, buffer_m=buffer_m)

    jurisdictions = [
        Jurisdiction(layer=j["layer"], jurisdiction_id=j["jurisdiction_id"], name=j["name"])
        for j in jurisdiction_dicts
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
    response_contacts: list[Contact] = []
    regulatory_contacts: list[Contact] = []

    if jurisdiction_layers:
        rules_stmt = select(Rule).where(
            Rule.jurisdiction_type.in_(jurisdiction_layers)
        )
        if request.material:
            rules_stmt = rules_stmt.where(
                (Rule.material == request.material.value) | (Rule.material.is_(None))
            )
        if request.quantity_gallons is not None:
            rules_stmt = rules_stmt.where(
                (Rule.size_threshold <= request.quantity_gallons) | (Rule.size_threshold.is_(None))
            )
        rules_result = await db.execute(rules_stmt)
        rules = rules_result.scalars().all()

        contact_ids = [r.contact_id for r in rules]
        if contact_ids:
            contacts_stmt = select(ContactModel).where(ContactModel.id.in_(contact_ids))
            contacts_result = await db.execute(contacts_stmt)
            contact_rows = contacts_result.scalars().all()

            for c in contact_rows:
                contact = Contact(
                    agency=c.agency,
                    role=ContactRole(c.role),
                    jurisdiction_id=c.jurisdiction_id,
                    phone=c.phone,
                    after_hours_phone=c.after_hours_phone,
                    email=c.email,
                    hours=c.hours,
                    reporting_deadline=c.reporting_deadline,
                    source_url=c.source_url,
                    last_verified=c.last_verified,
                )
                if c.role == ContactRole.response.value:
                    response_contacts.append(contact)
                else:
                    regulatory_contacts.append(contact)

    return LookupResult(
        jurisdictions=jurisdictions,
        downstream_path=downstream_path,
        response_contacts=response_contacts,
        regulatory_contacts=regulatory_contacts,
    )
