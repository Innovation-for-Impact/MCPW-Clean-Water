"""Contact verification service.

Checks contacts for staleness (not verified recently) and basic
validity (phone format, email format). Used by the verify_contacts
script and the admin API.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact

STALE_DAYS = 90  # contacts older than 90 days need re-verification

_PHONE_RE = re.compile(r"^[\d\s\-\(\)\+\.]+$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ContactIssue:
    contact_id: int
    agency: str
    issue_type: str  # "stale", "invalid_phone", "invalid_email", "missing_email"
    detail: str


async def check_all_contacts(db: AsyncSession) -> list[ContactIssue]:
    """Run all verification checks on every contact. Returns a list of issues."""
    result = await db.execute(select(Contact).order_by(Contact.agency))
    contacts = result.scalars().all()

    issues = []
    today = date.today()
    cutoff = today - timedelta(days=STALE_DAYS)

    for c in contacts:
        # Staleness check
        if c.last_verified < cutoff:
            days_ago = (today - c.last_verified).days
            issues.append(
                ContactIssue(
                    contact_id=c.id,
                    agency=c.agency,
                    issue_type="stale",
                    detail=f"Last verified {days_ago} days ago ({c.last_verified}). Threshold: {STALE_DAYS} days.",
                )
            )

        # Phone format check
        if c.phone and not _PHONE_RE.match(c.phone):
            issues.append(
                ContactIssue(
                    contact_id=c.id,
                    agency=c.agency,
                    issue_type="invalid_phone",
                    detail=f"Phone '{c.phone}' contains unexpected characters.",
                )
            )

        # Email checks
        if c.email:
            if not _EMAIL_RE.match(c.email):
                issues.append(
                    ContactIssue(
                        contact_id=c.id,
                        agency=c.agency,
                        issue_type="invalid_email",
                        detail=f"Email '{c.email}' does not match expected format.",
                    )
                )
        else:
            issues.append(
                ContactIssue(
                    contact_id=c.id,
                    agency=c.agency,
                    issue_type="missing_email",
                    detail="No email address on file.",
                )
            )

    return issues


async def get_verification_summary(db: AsyncSession) -> dict:
    """Return a summary of contact verification status."""
    result = await db.execute(select(Contact))
    contacts = result.scalars().all()

    today = date.today()
    cutoff = today - timedelta(days=STALE_DAYS)

    total = len(contacts)
    current = sum(1 for c in contacts if c.last_verified >= cutoff)
    stale = total - current
    missing_email = sum(1 for c in contacts if not c.email)

    return {
        "total_contacts": total,
        "current": current,
        "stale": stale,
        "stale_threshold_days": STALE_DAYS,
        "missing_email": missing_email,
    }
