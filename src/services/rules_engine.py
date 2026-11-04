"""
WS4 rules engine.

Given jurisdictions and incident details, returns contacts split into
Response and Regulatory lists, sorted by rule priority.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact as ContactModel
from src.models.rule import Rule
from src.schemas.contact import Contact
from src.schemas.enums import ContactRole

log = logging.getLogger(__name__)


async def evaluate_rules(
    jurisdiction_layers: list[str],
    *,
    db: AsyncSession,
    material: str | None = None,
    quantity_gallons: float | None = None,
) -> tuple[list[Contact], list[Contact]]:
    """Evaluate rules against jurisdictions and incident details.

    Returns (response_contacts, regulatory_contacts) sorted by priority.
    """
    if not jurisdiction_layers:
        return [], []

    stmt = select(Rule).where(Rule.jurisdiction_type.in_(jurisdiction_layers))

    if material:
        stmt = stmt.where((Rule.material == material) | (Rule.material.is_(None)))
    else:
        # Unknown material: only match material-agnostic rules
        stmt = stmt.where(Rule.material.is_(None))

    if quantity_gallons is not None:
        stmt = stmt.where(
            (Rule.size_threshold <= quantity_gallons) | (Rule.size_threshold.is_(None))
        )
    else:
        # Unknown quantity: only match size-agnostic rules
        stmt = stmt.where(Rule.size_threshold.is_(None))

    rules_result = await db.execute(stmt)
    rules = rules_result.scalars().all()

    if not rules:
        return [], []

    # Deduplicate: keep the highest-priority (lowest number) rule per contact
    best_rule_per_contact: dict[int, Rule] = {}
    for rule in rules:
        existing = best_rule_per_contact.get(rule.contact_id)
        if existing is None or rule.priority < existing.priority:
            best_rule_per_contact[rule.contact_id] = rule

    contact_ids = list(best_rule_per_contact.keys())
    contacts_stmt = select(ContactModel).where(ContactModel.id.in_(contact_ids))
    contacts_result = await db.execute(contacts_stmt)
    contact_rows = contacts_result.scalars().all()

    contact_map = {c.id: c for c in contact_rows}

    response_contacts: list[tuple[int, Contact]] = []
    regulatory_contacts: list[tuple[int, Contact]] = []

    for contact_id, rule in best_rule_per_contact.items():
        c = contact_map.get(contact_id)
        if c is None:
            log.warning("Rule %d references missing contact %d", rule.id, contact_id)
            continue

        contact = Contact(
            agency=c.agency,
            role=ContactRole(c.role),
            jurisdiction_id=c.jurisdiction_id,
            jurisdiction_scope=c.jurisdiction_scope,
            phone=c.phone,
            after_hours_phone=c.after_hours_phone,
            email=c.email,
            hours=c.hours,
            reporting_deadline=c.reporting_deadline,
            source_url=c.source_url,
            last_verified=c.last_verified,
            notes=c.notes,
        )
        if c.role == ContactRole.response.value:
            response_contacts.append((rule.priority, contact))
        else:
            regulatory_contacts.append((rule.priority, contact))

    response_contacts.sort(key=lambda x: x[0])
    regulatory_contacts.sort(key=lambda x: x[0])

    return (
        [c for _, c in response_contacts],
        [c for _, c in regulatory_contacts],
    )
