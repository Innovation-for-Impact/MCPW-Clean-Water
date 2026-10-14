import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event import Event
from src.models.webhook import Webhook

logger = logging.getLogger(__name__)


def build_event(
    event_type: str,
    incident_id: uuid.UUID,
    payload: dict,
) -> Event:
    """Create an Event ORM instance (caller is responsible for adding to session and committing)."""
    return Event(
        id=uuid.uuid4(),
        event_type=event_type,
        event_version="1.0",
        timestamp=datetime.now(timezone.utc),
        incident_id=incident_id,
        payload=payload,
    )


async def dispatch_webhooks(db: AsyncSession, event: Event) -> None:
    """POST event payload to all active webhook URLs.

    Intended to run as a background task AFTER the transaction has committed.
    Dispatches concurrently with a 5s per-webhook timeout.
    """
    stmt = select(Webhook).where(Webhook.active.is_(True))
    result = await db.execute(stmt)
    webhooks = result.scalars().all()

    if not webhooks:
        return

    event_data = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "event_version": event.event_version,
        "timestamp": event.timestamp.isoformat(),
        "incident_id": str(event.incident_id),
        "data": event.payload,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:

        async def _post(url: str) -> None:
            try:
                await client.post(url, json=event_data)
            except httpx.HTTPError:
                logger.warning(
                    "Webhook delivery failed for %s to %s",
                    event.id,
                    url,
                    exc_info=True,
                )

        await asyncio.gather(*[_post(w.url) for w in webhooks])
