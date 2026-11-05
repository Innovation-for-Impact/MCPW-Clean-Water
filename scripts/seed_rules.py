"""Seed rules for development/testing.

Rules define which contacts are triggered based on jurisdiction type,
material, and spill size. Priority (lower = more urgent) controls
sort order in response panels.

Usage: DATABASE_URL=... python -m scripts.seed_rules
Must run after seed_contacts.py (rules reference contact IDs).
"""

import asyncio

from sqlalchemy import select, text

from src.models.contact import Contact
from src.models.database import async_session_factory, engine
from src.models.rule import Rule

# Rules: (jurisdiction_type, material, size_threshold, contact_agency_substr,
#          required, deadline, priority, legal_citation)
# contact_id is resolved at runtime from the agency substring.
SEED_RULES = [
    # ── County-wide response (any spill) ─────────────────────────────────
    {
        "jurisdiction_type": "county",
        "contact_agency": "Emergency Hotline",
        "required": True,
        "deadline": "Immediate",
        "priority": 1,
        "legal_citation": "Michigan Drain Code Section 280.423",
        "notes": "Primary county clearing house — always first call",
    },
    {
        "jurisdiction_type": "county",
        "contact_agency": "Environmental Engineer",
        "required": True,
        "deadline": "Immediate",
        "priority": 5,
        "notes": "MCPWO lead responder per Spill Response Protocol",
    },
    # ── Municipal DPW (any spill in a municipality) ──────────────────────
    {
        "jurisdiction_type": "municipality",
        "contact_agency": "DPW",
        "required": True,
        "deadline": "Immediate",
        "priority": 10,
        "notes": "Matches any municipal DPW contact via jurisdiction_type",
    },
    {
        "jurisdiction_type": "municipality",
        "contact_agency": "Public Services",
        "required": True,
        "deadline": "Immediate",
        "priority": 10,
        "notes": "Clinton Twp uses 'Public Services' instead of 'DPW'",
    },
    {
        "jurisdiction_type": "municipality",
        "contact_agency": "Public Works",
        "required": True,
        "deadline": "Immediate",
        "priority": 10,
    },
    {
        "jurisdiction_type": "municipality",
        "contact_agency": "Water and Sewer",
        "required": True,
        "deadline": "Immediate",
        "priority": 10,
    },
    {
        "jurisdiction_type": "municipality",
        "contact_agency": "Water Department",
        "required": True,
        "deadline": "Immediate",
        "priority": 10,
    },
    # ── County regulatory (any spill) ────────────────────────────────────
    {
        "jurisdiction_type": "county",
        "contact_agency": "Health Department",
        "required": True,
        "deadline": "24 hours",
        "priority": 70,
    },
    # ── State regulatory (any spill) ─────────────────────────────────────
    {
        "jurisdiction_type": "county",
        "contact_agency": "EGLE — Pollution Emergency",
        "required": True,
        "deadline": "Immediate",
        "priority": 50,
        "legal_citation": "Michigan Part 5 Rules (MCL 324.3111a)",
    },
    {
        "jurisdiction_type": "county",
        "contact_agency": "EGLE — District 11",
        "required": True,
        "deadline": "Written follow-up within 10 days",
        "priority": 90,
        "legal_citation": "Michigan Part 5 Rules",
    },
    # ── Federal — shoreline/navigable waters ─────────────────────────────
    {
        "jurisdiction_type": "shoreline",
        "contact_agency": "Coast Guard",
        "required": True,
        "deadline": "Immediate",
        "priority": 15,
        "legal_citation": "33 CFR 153",
    },
    {
        "jurisdiction_type": "shoreline",
        "material": "oil_fuel",
        "contact_agency": "National Response Center",
        "required": True,
        "deadline": "Immediate",
        "priority": 51,
        "legal_citation": "CWA Section 311; 40 CFR 302.4",
    },
    {
        "jurisdiction_type": "shoreline",
        "material": "chemical_hazmat",
        "contact_agency": "National Response Center",
        "required": True,
        "deadline": "Immediate",
        "priority": 51,
        "legal_citation": "40 CFR 302.4 (CERCLA RQ)",
    },
    # ── Federal — EPA for large oil/hazmat spills ────────────────────────
    {
        "jurisdiction_type": "county",
        "material": "oil_fuel",
        "size_threshold": 25.0,
        "contact_agency": "EPA Region 5",
        "required": True,
        "deadline": "Per CERCLA schedule",
        "priority": 60,
        "legal_citation": "40 CFR 302 (CERCLA reportable quantity: 25 gal petroleum)",
    },
    {
        "jurisdiction_type": "county",
        "material": "chemical_hazmat",
        "contact_agency": "EPA Region 5",
        "required": True,
        "deadline": "Per CERCLA schedule",
        "priority": 60,
        "legal_citation": "40 CFR 302 (CERCLA)",
    },
]


async def main():
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM rules"))
        count = result.scalar()
        if count > 0:
            print(f"rules table already has {count} rows, skipping seed")
            print("  To re-seed, delete existing rows first")
            await engine.dispose()
            return

        contacts_result = await session.execute(select(Contact))
        contacts = contacts_result.scalars().all()
        if not contacts:
            print("No contacts found. Run seed_contacts.py first.")
            await engine.dispose()
            return

        added = 0
        for rule_def in SEED_RULES:
            agency_substr = rule_def["contact_agency"]
            match = next(
                (c for c in contacts if agency_substr in c.agency),
                None,
            )
            if not match:
                print(f"  WARNING: No contact matching '{agency_substr}', skipping rule")
                continue

            rule = Rule(
                jurisdiction_type=rule_def["jurisdiction_type"],
                material=rule_def.get("material"),
                size_threshold=rule_def.get("size_threshold"),
                contact_id=match.id,
                required=rule_def["required"],
                deadline=rule_def["deadline"],
                priority=rule_def["priority"],
                legal_citation=rule_def.get("legal_citation"),
            )
            session.add(rule)
            print(
                f"  [{rule_def['priority']:3d}] {rule_def['jurisdiction_type']}"
                f" / {rule_def.get('material', 'any')} -> {match.agency}"
            )
            added += 1

        await session.commit()
        print(f"\nSeeded {added} rules")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
