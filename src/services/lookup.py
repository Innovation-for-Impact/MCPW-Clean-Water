from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact as ContactModel
from src.models.rule import Rule
from src.schemas.contact import Contact
from src.schemas.enums import ContactRole, MaterialType
from src.schemas.jurisdiction import Jurisdiction
from src.schemas.lookup import (
    DrainInfo,
    InterceptPointInfo,
    LookupRequest,
    LookupResult,
    MajorDrainInfo,
    SpatialFlags,
    WaterInfo,
)
from src.services.spatial import run_spatial_lookup


async def run_lookup(db: AsyncSession, request: LookupRequest) -> LookupResult:
    """Orchestrate WS3 spatial query + WS4 rules engine."""

    # WS3: full spatial lookup — jurisdictions, drain/water snap, downstream trace
    spatial = await run_spatial_lookup(
        db,
        lat=request.location.lat,
        lon=request.location.lon,
        buffer_radius_m=request.buffer_radius_m,
    )

    jurisdictions = [
        Jurisdiction(layer=j.layer, jurisdiction_id=j.jurisdiction_id, name=j.name)
        for j in spatial.jurisdictions
    ]
    jurisdiction_ids = [j.jurisdiction_id for j in jurisdictions]

    # WS4: rules engine — find contacts based on jurisdictions + material + size
    response_contacts: list[Contact] = []
    regulatory_contacts: list[Contact] = []

    if jurisdiction_ids:
        rules_stmt = select(Rule).where(
            Rule.jurisdiction_type.in_(
                [j.layer for j in spatial.jurisdictions]
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

    # Build drain info
    drain_info = None
    if spatial.drain:
        drain_info = DrainInfo(
            drain_id=spatial.drain.drain_id,
            name=spatial.drain.name,
            tier=spatial.drain.tier,
            conveyance_owner=spatial.drain.conveyance_owner,
            conveyance_type=spatial.drain.conveyance_type,
            distance_m=spatial.drain.distance_m,
        )

    water_info = None
    if spatial.nearest_water:
        water_info = WaterInfo(
            name=spatial.nearest_water.name,
            nhd_comid=spatial.nearest_water.nhd_comid,
            distance_m=spatial.nearest_water.distance_m,
        )

    intercept_info = None
    if spatial.next_intercept_point:
        intercept_info = InterceptPointInfo(
            name=spatial.next_intercept_point.name,
            source=spatial.next_intercept_point.source,
            plan_sheet=spatial.next_intercept_point.plan_sheet,
        )

    return LookupResult(
        jurisdictions=jurisdictions,
        drain=drain_info,
        nearest_water=water_info,
        first_major_drain_downstream=(
            MajorDrainInfo(**spatial.first_major_drain_downstream)
            if spatial.first_major_drain_downstream else None
        ),
        next_intercept_point=intercept_info,
        downstream_path=spatial.downstream_path,
        upstream_counties=spatial.upstream_counties,
        flags=SpatialFlags(
            beach_downstream=spatial.flags.get("beach_downstream", False),
            intake_downstream=spatial.flags.get("intake_downstream", False),
            outside_county=spatial.flags.get("outside_county", False),
            excluded_procedure=spatial.flags.get("excluded_procedure", False),
        ),
        response_contacts=response_contacts,
        regulatory_contacts=regulatory_contacts,
    )
