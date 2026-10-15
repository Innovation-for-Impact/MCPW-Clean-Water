"""
WS3 Task 1.3d — Seed Red Run response_sites from HRC plan set (Sept 2026 draft).

Inserts the Red Run Drain (Tier 1) and its 18 crossings from Sheet 1 of the
Red Run Intercepting Drain District (RRIDD) response plan.

KNOWN ISSUES in the plan set (confirm with HRC before finalizing):
  - Sheets 7, 8, 13, 15, and 18 cite the wrong cross-reference sheets
  - Sheet 18 is labeled "Crossing 21" (should be Crossing 18)

Coordinates are approximate; refine from plan sheets or field GPS once available.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/seed_response_sites.py
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine


# Red Run Drain master record
RED_RUN_DRAIN = {
    "drain_id": "drain_red_run",
    "drain_number": None,  # Red Run is an intercounty drain, no single county drain number
    "name": "Red Run Drain",
    "tier": "1",
    "conveyance_owner": "county_drain",
    "intercounty": True,
    "upstream_counties": "Oakland",
    "drain_district_id": "dd_red_run",
    "has_response_plan": True,
}

# 18 crossings from HRC plan set Sheet 1 table.
# Coordinates are approximate (from plan set maps); refine with field GPS.
# site_order follows downstream order (1 = most upstream at Dequindre, 18 = outlet at Utica Rd).
RED_RUN_CROSSINGS = [
    {"site_order": 1, "name": "Crossing 1 — Dequindre Rd (south of Chicago Rd)", "boom_anchor": True, "plan_sheet": "Sheet 2", "lat": 42.5125, "lon": -83.0880, "access_notes": "Oakland County line; upstream_counties = [Oakland]", "access_contact": "OCWRC (GWK) for gate access"},
    {"site_order": 2, "name": "Crossing 2 — Chicago Rd at Dequindre", "boom_anchor": True, "plan_sheet": "Sheet 3", "lat": 42.5148, "lon": -83.0880, "access_notes": "Near county line", "access_contact": None},
    {"site_order": 3, "name": "Crossing 3 — Ryan Rd Bridge", "boom_anchor": True, "plan_sheet": "Sheet 4", "lat": 42.5230, "lon": -83.0555, "access_notes": None, "access_contact": None},
    {"site_order": 4, "name": "Crossing 4 — Dequindre Rd (north of 14 Mile)", "boom_anchor": False, "plan_sheet": "Sheet 5", "lat": 42.5290, "lon": -83.0880, "access_notes": None, "access_contact": None},
    {"site_order": 5, "name": "Crossing 5 — Schoenherr Rd", "boom_anchor": True, "plan_sheet": "Sheet 6", "lat": 42.5350, "lon": -83.0430, "access_notes": None, "access_contact": None},
    {"site_order": 6, "name": "Crossing 6 — Mound Rd", "boom_anchor": True, "plan_sheet": "Sheet 7", "lat": 42.5410, "lon": -83.0300, "access_notes": "CAUTION: Sheet 7 cites wrong cross-reference", "access_contact": None},
    {"site_order": 7, "name": "Crossing 7 — Bear Creek Confluence", "boom_anchor": True, "plan_sheet": "Sheet 8", "lat": 42.5480, "lon": -83.0180, "access_notes": "Bear Creek enters here; CAUTION: Sheet 8 cites wrong cross-reference", "access_contact": None},
    {"site_order": 8, "name": "Crossing 8 — Van Dyke Ave", "boom_anchor": True, "plan_sheet": "Sheet 9", "lat": 42.5530, "lon": -83.0090, "access_notes": None, "access_contact": None},
    {"site_order": 9, "name": "Crossing 9 — Hoover Rd", "boom_anchor": False, "plan_sheet": "Sheet 10", "lat": 42.5580, "lon": -82.9980, "access_notes": None, "access_contact": None},
    {"site_order": 10, "name": "Crossing 10 — Dodge Park Rd", "boom_anchor": True, "plan_sheet": "Sheet 11", "lat": 42.5630, "lon": -82.9870, "access_notes": None, "access_contact": None},
    {"site_order": 11, "name": "Crossing 11 — Hayes Rd", "boom_anchor": False, "plan_sheet": "Sheet 12", "lat": 42.5670, "lon": -82.9760, "access_notes": None, "access_contact": None},
    {"site_order": 12, "name": "Crossing 12 — Garfield Rd", "boom_anchor": True, "plan_sheet": "Sheet 13", "lat": 42.5720, "lon": -82.9620, "access_notes": "CAUTION: Sheet 13 cites wrong cross-reference", "access_contact": None},
    {"site_order": 13, "name": "Crossing 13 — Moravian Dr", "boom_anchor": False, "plan_sheet": "Sheet 14", "lat": 42.5760, "lon": -82.9500, "access_notes": None, "access_contact": None},
    {"site_order": 14, "name": "Crossing 14 — Harper Ave", "boom_anchor": True, "plan_sheet": "Sheet 15", "lat": 42.5790, "lon": -82.9380, "access_notes": "CAUTION: Sheet 15 cites wrong cross-reference", "access_contact": None},
    {"site_order": 15, "name": "Crossing 15 — Groesbeck Hwy", "boom_anchor": True, "plan_sheet": "Sheet 16", "lat": 42.5820, "lon": -82.9260, "access_notes": None, "access_contact": None},
    {"site_order": 16, "name": "Crossing 16 — Gratiot Ave", "boom_anchor": True, "plan_sheet": "Sheet 17", "lat": 42.5850, "lon": -82.9140, "access_notes": None, "access_contact": None},
    {"site_order": 17, "name": "Crossing 17 — N River Rd", "boom_anchor": False, "plan_sheet": "Sheet 18", "lat": 42.5880, "lon": -82.9020, "access_notes": "CAUTION: Sheet 18 labeled 'Crossing 21' and cites wrong cross-reference", "access_contact": None},
    {"site_order": 18, "name": "Crossing 18 — Utica Rd Bridge (outlet to Clinton River)", "boom_anchor": True, "plan_sheet": "Sheet 19", "lat": 42.5910, "lon": -82.8900, "access_notes": "Red Run outlet to Clinton River; no further planned crossings downstream", "access_contact": None},
]


async def seed():
    async with async_session_factory() as session:  # type: AsyncSession
        # Insert drain record
        d = RED_RUN_DRAIN
        await session.execute(
            text("""
                INSERT INTO drains (drain_id, drain_number, name, tier, conveyance_owner, intercounty, upstream_counties, drain_district_id, has_response_plan)
                VALUES (:drain_id, :drain_number, :name, :tier, :conveyance_owner, :intercounty, :upstream_counties, :drain_district_id, :has_response_plan)
                ON CONFLICT (drain_id) DO UPDATE SET
                    tier = EXCLUDED.tier,
                    upstream_counties = EXCLUDED.upstream_counties,
                    has_response_plan = EXCLUDED.has_response_plan
            """),
            d,
        )
        print(f"Upserted drain: {d['drain_id']} ({d['name']}, Tier {d['tier']})")

        # Insert response sites
        for c in RED_RUN_CROSSINGS:
            wkt = f"POINT({c['lon']} {c['lat']})"
            await session.execute(
                text("""
                    INSERT INTO response_sites (drain_id, site_order, name, source, boom_anchor, access_notes, access_contact, plan_sheet, geometry)
                    VALUES (:drain_id, :site_order, :name, 'plan', :boom_anchor, :access_notes, :access_contact, :plan_sheet, ST_GeogFromText(:wkt))
                    ON CONFLICT DO NOTHING
                """),
                {
                    "drain_id": "drain_red_run",
                    "site_order": c["site_order"],
                    "name": c["name"],
                    "boom_anchor": c["boom_anchor"],
                    "access_notes": c["access_notes"],
                    "access_contact": c["access_contact"],
                    "plan_sheet": c["plan_sheet"],
                    "wkt": wkt,
                },
            )

        await session.commit()
        print(f"Seeded {len(RED_RUN_CROSSINGS)} Red Run response sites (source=plan)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
