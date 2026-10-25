"""Seed sample contacts for development/testing.

Usage: DATABASE_URL=... python -m scripts.seed_contacts
"""
import asyncio
from datetime import date

from sqlalchemy import select, text

from src.models.contact import Contact
from src.models.database import async_session_factory, engine

SEED_CONTACTS = [
    {
        "agency": "Macomb County Public Works — Drain Office",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "phone": "586-469-5325",
        "after_hours_phone": "586-469-5325",
        "email": "public.works@macombgov.org",
        "hours": "Mon-Fri 8am-4:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://macombgov.org/departments/public-works",
        "last_verified": date(2026, 10, 25),
    },
    {
        "agency": "Macomb County Health Department — Environmental Health",
        "role": "regulatory",
        "jurisdiction_id": "county_macomb",
        "phone": "586-469-5236",
        "email": "environmentalhealth@macombgov.org",
        "hours": "Mon-Fri 8am-5pm",
        "reporting_deadline": "24 hours",
        "source_url": "https://macombgov.org/departments/health",
        "last_verified": date(2026, 10, 25),
    },
    {
        "agency": "Michigan EGLE — Pollution Emergency Alert System (PEAS)",
        "role": "regulatory",
        "jurisdiction_id": "county_macomb",
        "phone": "800-292-4706",
        "after_hours_phone": "800-292-4706",
        "hours": "24/7",
        "reporting_deadline": "Immediate for releases to surface water",
        "source_url": "https://www.michigan.gov/egle/about/contact/pollution-emergency-alerting-system",
        "last_verified": date(2026, 10, 25),
    },
    {
        "agency": "US Coast Guard — Sector Detroit",
        "role": "response",
        "jurisdiction_id": "shoreline_lake_st_clair",
        "phone": "313-568-9564",
        "after_hours_phone": "313-568-9580",
        "hours": "24/7",
        "reporting_deadline": "Immediate for spills to navigable waters",
        "source_url": "https://www.atlanticarea.uscg.mil/Our-Organization/District-9/Units/Sector-Detroit/",
        "last_verified": date(2026, 10, 25),
    },
    {
        "agency": "National Response Center (NRC)",
        "role": "regulatory",
        "jurisdiction_id": "shoreline_lake_st_clair",
        "phone": "800-424-8802",
        "hours": "24/7",
        "reporting_deadline": "Immediate for oil/hazmat to navigable waters",
        "source_url": "https://nrc.uscg.mil/",
        "last_verified": date(2026, 10, 25),
    },
]


async def main():
    async with async_session_factory() as session:
        # Check if contacts table exists and has data
        result = await session.execute(text("SELECT COUNT(*) FROM contacts"))
        count = result.scalar()
        if count > 0:
            print(f"contacts table already has {count} rows, skipping seed")
            await engine.dispose()
            return

        for c in SEED_CONTACTS:
            contact = Contact(**c)
            session.add(contact)
            print(f"  Added: {c['agency']} ({c['role']})")
        await session.commit()
        print(f"\nSeeded {len(SEED_CONTACTS)} contacts")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
