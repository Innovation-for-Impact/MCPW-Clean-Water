"""
WS3 ETL — Build downstream connectivity links for waterways table.

Parses the NHDPlus flow table (PlusFlow or NHDPlusFlowlineVAA) to populate
the downstream_comid column on each waterway segment.

Also flags known beaches and drinking-water intakes on downstream segments.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/build_downstream_links.py
"""

import asyncio
import csv
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "waterways"

# Known beaches downstream in the Clinton River / Lake St. Clair system
KNOWN_BEACHES = [
    "Memorial Park Beach",
    "Lake St. Clair Metropark Beach",
    "Blossom Heath Beach",
    "New Baltimore Beach",
]

# Known drinking-water intakes (confirm with MCPWO)
KNOWN_INTAKES: list[str] = [
    # Add intake names/COMIDs here once confirmed
]


async def load_plusflow_csv(session: AsyncSession, csv_path: Path) -> int:
    """Parse NHDPlus PlusFlow table and update downstream_comid links."""
    count = 0
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_comid = int(row.get("FromNHDPID") or row.get("FROMCOMID") or 0)
            to_comid = int(row.get("ToNHDPID") or row.get("TOCOMID") or 0)

            if from_comid == 0 or to_comid == 0:
                continue

            result = await session.execute(
                text("""
                    UPDATE waterways SET downstream_comid = :to_comid
                    WHERE nhd_comid = :from_comid AND downstream_comid IS NULL
                """),
                {"from_comid": from_comid, "to_comid": to_comid},
            )
            if result.rowcount > 0:
                count += 1

    return count


async def flag_beaches_and_intakes(session: AsyncSession):
    """Flag waterway segments with known beaches or intakes downstream."""
    for beach in KNOWN_BEACHES:
        await session.execute(
            text("""
                UPDATE waterways SET has_beach_downstream = true
                WHERE name ILIKE :pattern
            """),
            {"pattern": f"%{beach}%"},
        )

    for intake in KNOWN_INTAKES:
        await session.execute(
            text("""
                UPDATE waterways SET has_intake_downstream = true
                WHERE name ILIKE :pattern
            """),
            {"pattern": f"%{intake}%"},
        )

    # Propagate flags upstream via downstream_comid links
    # Segments upstream of a flagged segment should also be flagged
    await session.execute(
        text("""
            WITH RECURSIVE upstream AS (
                SELECT nhd_comid FROM waterways WHERE has_beach_downstream = true
                UNION
                SELECT w.nhd_comid
                FROM waterways w
                JOIN upstream u ON w.downstream_comid = u.nhd_comid
                WHERE w.has_beach_downstream = false
            )
            UPDATE waterways SET has_beach_downstream = true
            WHERE nhd_comid IN (SELECT nhd_comid FROM upstream)
        """),
    )
    await session.execute(
        text("""
            WITH RECURSIVE upstream AS (
                SELECT nhd_comid FROM waterways WHERE has_intake_downstream = true
                UNION
                SELECT w.nhd_comid
                FROM waterways w
                JOIN upstream u ON w.downstream_comid = u.nhd_comid
                WHERE w.has_intake_downstream = false
            )
            UPDATE waterways SET has_intake_downstream = true
            WHERE nhd_comid IN (SELECT nhd_comid FROM upstream)
        """),
    )
    print("  Propagated beach/intake flags upstream")


async def main():
    print("=" * 60)
    print("WS3 ETL: Build downstream connectivity links")
    print("=" * 60)

    # Look for PlusFlow CSV
    csv_files = list(RAW_DIR.glob("*PlusFlow*")) + list(RAW_DIR.glob("*plusflow*"))

    async with async_session_factory() as session:
        if csv_files:
            for f in csv_files:
                print(f"\n  Loading flow table: {f.name}")
                count = await load_plusflow_csv(session, f)
                print(f"  Updated {count} downstream links")
        else:
            print("\n  No PlusFlow CSV found in data/raw/waterways/")
            print("  Download from NHDPlus HR dataset and place CSV here")

        print("\n--- Flagging beaches and intakes ---")
        await flag_beaches_and_intakes(session)

        await session.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
