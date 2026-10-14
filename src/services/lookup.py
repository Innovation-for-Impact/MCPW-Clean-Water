from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact as ContactModel
from src.models.jurisdiction import Jurisdiction as JurisdictionModel
from src.models.rule import Rule
from src.schemas.contact import Contact
from src.schemas.enums import ContactRole, MaterialType
from src.schemas.jurisdiction import Jurisdiction
from src.schemas.lookup import LookupRequest, LookupResult


async def run_lookup(db: AsyncSession, request: LookupRequest) -> LookupResult:
    """Orchestrate WS3 spatial query + WS4 rules engine."""

    point = ST_SetSRID(ST_MakePoint(request.location.lon, request.location.lat), 4326)
    buffer_m = request.buffer_radius_m or 0

    # WS3: spatial query — find jurisdictions that intersect the point/buffer
    if buffer_m > 0:
        spatial_filter = ST_DWithin(JurisdictionModel.geometry, point, buffer_m)
    else:
        spatial_filter = ST_DWithin(JurisdictionModel.geometry, point, 0)

    stmt = select(JurisdictionModel).where(spatial_filter)
    result = await db.execute(stmt)
    jurisdiction_rows = result.scalars().all()

    jurisdictions = [
        Jurisdiction(
            layer=j.layer,
            jurisdiction_id=j.jurisdiction_id,
            name=j.name,
        )
        for j in jurisdiction_rows
    ]
    jurisdiction_ids = [j.jurisdiction_id for j in jurisdictions]

    # WS4: rules engine — find contacts based on jurisdictions + material + size
    response_contacts: list[Contact] = []
    regulatory_contacts: list[Contact] = []

    if jurisdiction_ids:
        rules_stmt = select(Rule).where(
            Rule.jurisdiction_type.in_(
                [j.layer for j in jurisdiction_rows]
            )
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
                if c.role == ContactRole.response:
                    response_contacts.append(contact)
                else:
                    regulatory_contacts.append(contact)

    return LookupResult(
        jurisdictions=jurisdictions,
        downstream_path=[],  # WS3 downstream tracing — placeholder for integration
        response_contacts=response_contacts,
        regulatory_contacts=regulatory_contacts,
    )
