"""Seed contacts for development/testing.

Sources:
- MCPWO Spill Response Contact Cards (180522_Spill_Response_Cards.docx)
- Draft Stormwater Spill Response Protocol (01.08.2018)
- Red Run Drain Spill Response (20260928_Owners_review_Red Run Spill Response_RFS.pdf, Sept 2026)
- Agency websites (source_url on each record)

Usage: DATABASE_URL=... python -m scripts.seed_contacts
"""

import asyncio
from datetime import date

from sqlalchemy import text

from src.models.contact import Contact
from src.models.database import async_session_factory, engine

# last_verified reflects when these were last confirmed against source docs
NEEDS_VERIFICATION = date(2018, 5, 22)
VERIFIED_2026 = date(2026, 10, 25)
RED_RUN_2026 = date(2026, 9, 28)  # Red Run Drain Spill Response document date

SEED_CONTACTS = [
    # ── County-level response ────────────────────────────────────────────
    {
        "agency": "Macomb County Public Works — Emergency Hotline",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "county",
        "phone": "1-877-679-4337",
        "after_hours_phone": "1-877-679-4337",
        "hours": "24/7",
        "reporting_deadline": "Immediate",
        "source_url": "https://macombgov.org/departments/public-works",
        "last_verified": VERIFIED_2026,
        "notes": "Primary clearing house for surface water and pollution complaints in Macomb County",
    },
    {
        "agency": "Macomb County Public Works — Environmental Engineer",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "county",
        "phone": "(586) 493-0685",
        "after_hours_phone": "(586) 746-9118",
        "email": "jeff.bednar@macombgov.org",
        "hours": "Mon-Fri 8am-4:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://macombgov.org/departments/public-works",
        "last_verified": NEEDS_VERIFICATION,
        "notes": "Jeff Bednar — primary responder per Spill Response Protocol. Verify name/number still current.",
    },
    {
        "agency": "Macomb County Public Works — Operations/Flow Manager (SSO Lead)",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "county",
        "phone": "(586) 469-6320",
        "after_hours_phone": "(586) 615-2436",
        "email": "vincent.astorino@macombgov.org",
        "hours": "Mon-Fri 8am-4:30pm",
        "reporting_deadline": "Immediate for sanitary sewer overflows",
        "source_url": "https://macombgov.org/departments/public-works",
        "last_verified": NEEDS_VERIFICATION,
        "notes": (
            "Vincent Astorino — SSO response lead per Spill Response Cards (2018). "
            "Notified for sewage/sanitary sewer overflows. Verify name/number still current."
        ),
    },
    {
        "agency": "Macomb County Public Works — Construction Engineer",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "county",
        "phone": "(586) 307-8272",
        "after_hours_phone": "(586) 615-4198",
        "email": "tom.stockel@macombgov.org",
        "hours": "Mon-Fri 8am-4:30pm",
        "reporting_deadline": "As needed",
        "source_url": "https://macombgov.org/departments/public-works",
        "last_verified": NEEDS_VERIFICATION,
        "notes": (
            "Tom Stockel — handles initial response if Environmental Engineer unavailable. "
            "Per Spill Response Cards (2018). Verify name/number still current."
        ),
    },
    # ── County-level regulatory ──────────────────────────────────────────
    {
        "agency": "Macomb County Health Department — Environmental Health",
        "role": "regulatory",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "county",
        "phone": "(586) 469-5236",
        "email": "environmentalhealth@macombgov.org",
        "hours": "Mon-Fri 8am-5pm",
        "reporting_deadline": "24 hours",
        "source_url": "https://macombgov.org/departments/health",
        "last_verified": VERIFIED_2026,
    },
    # ── State regulatory ─────────────────────────────────────────────────
    {
        "agency": "Michigan EGLE — Pollution Emergency Alert System (PEAS)",
        "role": "regulatory",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "state",
        "phone": "1-800-292-4706",
        "after_hours_phone": "1-800-292-4706",
        "hours": "24/7",
        "reporting_deadline": "Immediate for releases to surface water",
        "source_url": "https://www.michigan.gov/egle/about/contact/pollution-emergency-alerting-system",
        "last_verified": VERIFIED_2026,
        "notes": "All spills to water in Michigan. Required by Michigan Part 5 Rules (MCL 324.3111a).",
    },
    {
        "agency": "Michigan EGLE — District 11 (SE Michigan)",
        "role": "regulatory",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "state",
        "phone": "(248) 508-1078",
        "email": "ryant4@michigan.gov",
        "hours": "Mon-Fri 8am-5pm",
        "reporting_deadline": "Written follow-up within 10 days",
        "source_url": "https://www.michigan.gov/egle/about/organization/water-resources-division",
        "last_verified": NEEDS_VERIFICATION,
        "notes": (
            "Dennis Ryan, Senior Environmental Engineer. "
            "Follow-up report after PEAS notification. Verify name/number still current."
        ),
    },
    # ── Federal — shoreline / navigable waters ───────────────────────────
    {
        "agency": "US Coast Guard — Sector Detroit",
        "role": "response",
        "jurisdiction_id": "shoreline_lake_st_clair",
        "jurisdiction_scope": "federal",
        "phone": "(313) 568-9564",
        "after_hours_phone": "(313) 568-9580",
        "hours": "24/7",
        "reporting_deadline": "Immediate for spills to navigable waters",
        "source_url": "https://www.atlanticarea.uscg.mil/Our-Organization/District-9/Units/Sector-Detroit/",
        "last_verified": VERIFIED_2026,
        "notes": "Oil/hazmat on Lake St. Clair and navigable portions of Clinton River.",
    },
    {
        "agency": "National Response Center (NRC)",
        "role": "regulatory",
        "jurisdiction_id": "shoreline_lake_st_clair",
        "jurisdiction_scope": "federal",
        "phone": "1-800-424-8802",
        "hours": "24/7",
        "reporting_deadline": "Immediate for oil/hazmat to navigable waters",
        "source_url": "https://nrc.uscg.mil/",
        "last_verified": VERIFIED_2026,
        "notes": "Required by CWA Section 311 (oil sheen) and 40 CFR 302.4 (CERCLA RQ).",
    },
    {
        "agency": "EPA Region 5",
        "role": "regulatory",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "federal",
        "phone": "(312) 353-2000",
        "hours": "Mon-Fri 8am-5pm",
        "reporting_deadline": "Per CERCLA schedule",
        "source_url": "https://www.epa.gov/aboutepa/epa-region-5",
        "last_verified": VERIFIED_2026,
        "notes": "CERCLA reportable quantities: diesel/fuel oil 25 gal, gasoline 25 gal.",
    },
    # ── Municipal DPW contacts (from Spill Response Protocol Table 3) ────
    {
        "agency": "Chesterfield Township — DPW",
        "role": "response",
        "jurisdiction_id": "muni_chesterfield_township",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 949-0400 ext. 3",
        "after_hours_phone": "(586) 949-2322",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.chesterfieldtwp.org",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "Clinton Township — DPW",
        "role": "response",
        "jurisdiction_id": "muni_clinton_township",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 286-9300",
        "after_hours_phone": "(586) 469-5502",
        "email": "dps@clintontownship-mi.gov",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.clintontownship.com",
        "last_verified": RED_RUN_2026,
        "notes": "Mary Bednar — per Red Run Drain Spill Response contact list (Sept 2026).",
    },
    {
        "agency": "Clinton Township — Fire Department",
        "role": "response",
        "jurisdiction_id": "muni_clinton_township",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 263-8437",
        "after_hours_phone": "911",
        "email": "fire@clintontownship.com",
        "hours": "24/7",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.clintontownship.com",
        "last_verified": RED_RUN_2026,
        "notes": "John Gallagher — per Red Run Drain Spill Response contact list (Sept 2026).",
    },
    {
        "agency": "City of Eastpointe — Public Works",
        "role": "response",
        "jurisdiction_id": "muni_eastpointe",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 445-5040",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.cityofeastpointe.net",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "City of Fraser — Public Works",
        "role": "response",
        "jurisdiction_id": "muni_fraser",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 293-3100 ext. 126",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.ci.fraser.mi.us",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "Harrison Township — Water and Sewer",
        "role": "response",
        "jurisdiction_id": "muni_harrison_township",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 466-1426",
        "after_hours_phone": "(586) 469-5502",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.harrisontwp.org",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "Macomb Township — Water and Sewer",
        "role": "response",
        "jurisdiction_id": "muni_macomb_township",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 598-0687",
        "after_hours_phone": "(586) 598-1790",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.macomb-mi.gov",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "City of Roseville — Water Department",
        "role": "response",
        "jurisdiction_id": "muni_roseville",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 445-5466",
        "after_hours_phone": "(586) 777-6700",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.roseville-mi.gov",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "City of Mt Clemens — DPW",
        "role": "response",
        "jurisdiction_id": "muni_mt_clemens",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 469-6816",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.cityofmtclemens.org",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "City of Sterling Heights — DPW",
        "role": "response",
        "jurisdiction_id": "muni_sterling_heights",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 446-2440",
        "after_hours_phone": "(586) 469-5151",
        "email": "mmoore@sterling-heights.net",
        "hours": "Mon-Fri 7am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.sterling-heights.net",
        "last_verified": RED_RUN_2026,
        "notes": "Michael Moore — per Red Run Drain Spill Response contact list (Sept 2026).",
    },
    {
        "agency": "City of Sterling Heights — Fire Department",
        "role": "response",
        "jurisdiction_id": "muni_sterling_heights",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 446-2950",
        "after_hours_phone": "911",
        "hours": "24/7",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.sterling-heights.net",
        "last_verified": RED_RUN_2026,
        "notes": "Kevin Edmond — per Red Run Drain Spill Response contact list (Sept 2026).",
    },
    {
        "agency": "City of St Clair Shores — DPW",
        "role": "response",
        "jurisdiction_id": "muni_st_clair_shores",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 445-0600",
        "hours": "Mon-Fri 7am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.scsmi.net",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "City of Warren — DPS",
        "role": "response",
        "jurisdiction_id": "muni_warren",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 574-4604",
        "email": "dmuzzarelli@cityofwarren.org",
        "hours": "Mon-Fri 7am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.cityofwarren.org",
        "last_verified": RED_RUN_2026,
        "notes": "David Muzzarelli — per Red Run Drain Spill Response contact list (Sept 2026).",
    },
    {
        "agency": "City of Warren — Fire Department",
        "role": "response",
        "jurisdiction_id": "muni_warren",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 574-9111",
        "after_hours_phone": "911",
        "email": "warrenfire@warrenfiredept.org",
        "hours": "24/7",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.cityofwarren.org",
        "last_verified": RED_RUN_2026,
        "notes": "Skip McAdams — per Red Run Drain Spill Response contact list (Sept 2026).",
    },
    {
        "agency": "City of Warren — Spill Response Team",
        "role": "response",
        "jurisdiction_id": "muni_warren",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 574-4604",
        "email": "dmuzzarelli@cityofwarren.org",
        "hours": "Mon-Fri 7am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.cityofwarren.org",
        "last_verified": RED_RUN_2026,
        "notes": "Dave Lynette — dedicated spill response. Per Red Run Drain contact list (Sept 2026).",
    },
    {
        "agency": "Shelby Township — DPW",
        "role": "response",
        "jurisdiction_id": "muni_shelby_township",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 731-0500",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.shelbytwp.org",
        "last_verified": NEEDS_VERIFICATION,
    },
    {
        "agency": "City of New Baltimore — DPW",
        "role": "response",
        "jurisdiction_id": "muni_new_baltimore",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 725-2151",
        "hours": "Mon-Fri 7:30am-3:30pm",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.cityofnewbaltimore.org",
        "last_verified": NEEDS_VERIFICATION,
    },
    # ── Intercounty — Oakland County (Red Run crosses county line) ──────
    {
        "agency": "Oakland County Water Resources Commissioner (OCWRC)",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "intercounty",
        "phone": "(248) 858-0958",
        "after_hours_phone": "(248) 858-0931",
        "email": "frederiksene@OaklandCountyMI.gov",
        "hours": "Mon-Fri 8am-5pm",
        "reporting_deadline": "Immediate for Red Run / GWK Drain incidents",
        "source_url": "https://www.oakgov.com/water",
        "last_verified": RED_RUN_2026,
        "notes": (
            "Erik Frederikson — OCWRC GWK Drain contact. Red Run Drain is intercounty "
            "(Oakland/Macomb); OCWRC manages upstream GWK Drain. Per Red Run Spill Response (Sept 2026)."
        ),
    },
    {
        "agency": "Oakland County Water Resources Commissioner — Emergency Line",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "intercounty",
        "phone": "(248) 858-0931",
        "hours": "24/7",
        "source_url": "https://www.oakgov.com/water",
        "last_verified": RED_RUN_2026,
        "notes": "OCWRC after-hours emergency. Per Red Run Spill Response (Sept 2026).",
    },
    # ── Disposal / utility ──────────────────────────────────────────────
    {
        "agency": "South Macomb Disposal Authority (SMDA)",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "county",
        "phone": "(586) 777-1284",
        "hours": "24/7",
        "reporting_deadline": "Immediate",
        "source_url": "https://www.smda.us",
        "last_verified": RED_RUN_2026,
        "notes": "Emergency line. Gate access contact for Sterling Relief / Metro Parkway sites.",
    },
    # ── Site access — Huron Academy (Red Run Crossing 16 area) ──────────
    {
        "agency": "Huron Academy — Principal",
        "role": "response",
        "jurisdiction_id": "muni_sterling_heights",
        "jurisdiction_scope": "municipal",
        "phone": "(586) 690-8180",
        "after_hours_phone": "(586) 446-9170",
        "email": "sobczakj@huronacademy.org",
        "hours": "School hours",
        "source_url": "https://www.huronacademy.org",
        "last_verified": RED_RUN_2026,
        "notes": (
            "Joshua Sobczak — site access for Red Run Crossing 16 (Metro Parkway). "
            "Per Red Run Spill Response (Sept 2026)."
        ),
    },
    # ── Cleanup contractors (from Red Run Spill Response p.2) ───────────
    {
        "agency": "Marine Pollution Control",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "contractor",
        "phone": "(313) 849-2333",
        "hours": "24/7",
        "source_url": "https://www.marinepollutioncontrol.com",
        "last_verified": RED_RUN_2026,
        "notes": "Spill cleanup contractor. Per Red Run Spill Response (Sept 2026).",
    },
    {
        "agency": "Deotsch Environmental",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "contractor",
        "phone": "(586) 755-2090",
        "hours": "24/7",
        "source_url": "https://www.deotsch.com",
        "last_verified": RED_RUN_2026,
        "notes": "Spill cleanup contractor. Per Red Run Spill Response (Sept 2026).",
    },
    {
        "agency": "Mersino Dewatering",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "contractor",
        "phone": "(866) 637-7466",
        "hours": "24/7",
        "source_url": "https://www.mersino.com",
        "last_verified": RED_RUN_2026,
        "notes": "Dewatering contractor. Per Red Run Spill Response (Sept 2026).",
    },
    {
        "agency": "Clean Harbors",
        "role": "response",
        "jurisdiction_id": "county_macomb",
        "jurisdiction_scope": "contractor",
        "phone": "(800) 645-8265",
        "hours": "24/7",
        "source_url": "https://www.cleanharbors.com",
        "last_verified": RED_RUN_2026,
        "notes": "Environmental cleanup contractor. Per Red Run Spill Response (Sept 2026).",
    },
]


async def main():
    async with async_session_factory() as session:
        # Check if contacts table exists and has data
        result = await session.execute(text("SELECT COUNT(*) FROM contacts"))
        count = result.scalar()
        if count > 0:
            print(f"contacts table already has {count} rows, skipping seed")
            print("  To re-seed, delete existing rows first")
            await engine.dispose()
            return

        for c in SEED_CONTACTS:
            contact = Contact(**c)
            session.add(contact)
            print(f"  Added: {c['agency']} ({c['role']}) [{c.get('jurisdiction_scope', '?')}]")
        await session.commit()
        print(f"\nSeeded {len(SEED_CONTACTS)} contacts")

        # Report verification status
        needs_verify = [c for c in SEED_CONTACTS if c["last_verified"] == NEEDS_VERIFICATION]
        if needs_verify:
            print(f"\nWARNING: {len(needs_verify)} contacts need phone number verification (from 2018 docs):")
            for c in needs_verify:
                print(f"    {c['agency']}: {c['phone']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
