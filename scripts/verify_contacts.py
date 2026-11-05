"""Contact verification report.

Queries all contacts and prints a verification status report.
Flags contacts not verified within the last 30 days.

Usage: DATABASE_URL=... python -m scripts.verify_contacts
"""

import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from src.models.contact import Contact
from src.models.database import async_session_factory, engine

STALE_DAYS = 30


async def main():
    async with async_session_factory() as session:
        result = await session.execute(select(Contact).order_by(Contact.jurisdiction_scope, Contact.agency))
        contacts = result.scalars().all()

    await engine.dispose()

    if not contacts:
        print("No contacts in database.")
        return

    today = date.today()
    cutoff = today - timedelta(days=STALE_DAYS)
    stale = []

    print(f"Contact Verification Report — {today}")
    print(f"{'':=<100}")
    print(f"{'Agency':<50} {'Phone':<22} {'Verified':<12} {'Days Ago':<10} {'Status'}")
    print(f"{'':─<100}")

    for c in contacts:
        days_ago = (today - c.last_verified).days
        status = "OK" if c.last_verified >= cutoff else "NEEDS VERIFY"
        if status == "NEEDS VERIFY":
            stale.append(c)

        print(f"{c.agency[:49]:<50} {c.phone:<22} {c.last_verified} {days_ago:>7}d   {status}")

    print(f"{'':─<100}")
    print(f"\nTotal: {len(contacts)} contacts")
    print(f"Current (verified within {STALE_DAYS} days): {len(contacts) - len(stale)}")
    print(f"Needs verification: {len(stale)}")

    if stale:
        print(f"\n{'':=<100}")
        print("CONTACTS NEEDING VERIFICATION:")
        print(f"{'':─<100}")
        for c in stale:
            print(f"  {c.agency}")
            print(f"    Phone: {c.phone}")
            if c.notes:
                print(f"    Notes: {c.notes}")
            print(f"    Source: {c.source_url}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
