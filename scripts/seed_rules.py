"""Seed sample rules for development/testing.

Usage: DATABASE_URL=... python -m scripts.seed_rules

Must run after seed_contacts.py (rules reference contact IDs).
"""
import asyncio

from sqlalchemy import select, text

from src.models.contact import Contact
from src.models.database import async_session_factory, engine
from src.models.rule import Rule

# Rules are defined by (jurisdiction_type, material, contact_agency_substring)
# contact_id is resolved at runtime from the agency name
SEED_RULES = [
    # County-level response for any spill
    {"jurisdiction_type": "county", "material": None, "contact_agency": "Drain Office", "required": True, "deadline": "Immediate"},
    # County-level regulatory for any spill
    {"jurisdiction_type": "county", "material": None, "contact_agency": "Health Department", "required": True, "deadline": "24 hours"},
    # State regulatory for any spill in county
    {"jurisdiction_type": "county", "material": None, "contact_agency": "EGLE", "required": True, "deadline": "Immediate"},
    # USCG for shoreline spills
    {"jurisdiction_type": "shoreline", "material": None, "contact_agency": "Coast Guard", "required": True, "deadline": "Immediate"},
    # NRC for oil/hazmat on shoreline
    {"jurisdiction_type": "shoreline", "material": "oil_fuel", "contact_agency": "National Response Center", "required": True, "deadline": "Immediate"},
    {"jurisdiction_type": "shoreline", "material": "chemical_hazmat", "contact_agency": "National Response Center", "required": True, "deadline": "Immediate"},
]


async def main():
    async with async_session_factory() as session:
        # Check if rules already seeded
        result = await session.execute(text("SELECT COUNT(*) FROM rules"))
        count = result.scalar()
        if count > 0:
            print(f"rules table already has {count} rows, skipping seed")
            await engine.dispose()
            return

        # Load contacts to resolve IDs
        contacts_result = await session.execute(select(Contact))
        contacts = contacts_result.scalars().all()
        if not contacts:
            print("No contacts found. Run seed_contacts.py first.")
            await engine.dispose()
            return

        for rule_def in SEED_RULES:
            # Find matching contact by agency substring
            match = next(
                (c for c in contacts if rule_def["contact_agency"] in c.agency),
                None,
            )
            if not match:
                print(f"  WARNING: No contact matching '{rule_def['contact_agency']}', skipping rule")
                continue

            rule = Rule(
                jurisdiction_type=rule_def["jurisdiction_type"],
                material=rule_def["material"],
                contact_id=match.id,
                required=rule_def["required"],
                deadline=rule_def["deadline"],
            )
            session.add(rule)
            print(f"  Added rule: {rule_def['jurisdiction_type']} / {rule_def['material'] or 'any'} -> {match.agency}")

        await session.commit()
        print(f"\nSeeded rules")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
