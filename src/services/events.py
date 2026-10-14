import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from src.models.database import async_session_factory
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


async def dispatch_webhooks(event_data: dict) -> None:
    """POST event payload to all active webhook URLs.

    Creates its own DB session so it is safe to run as a BackgroundTask
    after the request-scoped session has been closed.
    Dispatches concurrently with a 5s per-webhook timeout.
    """
    async with async_session_factory() as db:
        stmt = select(Webhook).where(Webhook.active.is_(True))
        result = await db.execute(stmt)
        webhooks = result.scalars().all()

    if not webhooks:
        return

    async with httpx.AsyncClient(timeout=5.0) as client:

        async def _post(url: str) -> None:
            try:
                await client.post(url, json=event_data)
            except httpx.HTTPError:
                logger.warning(
                    "Webhook delivery failed for event %s to %s",
                    event_data.get("event_id"),
                    url,
                    exc_info=True,
                )

        await asyncio.gather(*[_post(w.url) for w in webhooks])
