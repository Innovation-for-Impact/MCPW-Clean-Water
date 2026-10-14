import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event import Event
from src.models.webhook import Webhook

logger = logging.getLogger(__name__)


async def create_event(
    db: AsyncSession,
    event_type: str,
    incident_id: uuid.UUID,
    payload: dict,
) -> Event:
    """Write an event to the events table and dispatch webhooks."""
    event = Event(
        id=uuid.uuid4(),
        event_type=event_type,
        event_version="1.0",
        timestamp=datetime.now(timezone.utc),
        incident_id=incident_id,
        payload=payload,
    )
    db.add(event)
    await db.commit()

    # Dispatch webhooks after commit so HTTP calls don't hold the transaction open
    await _dispatch_webhooks(db, event, payload)

    return event


async def _dispatch_webhooks(db: AsyncSession, event: Event, payload: dict) -> None:
    """POST event payload to all active webhook URLs. Fire-and-forget with 5s timeout."""
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
        "data": payload,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for webhook in webhooks:
            try:
                await client.post(webhook.url, json=event_data)
            except httpx.HTTPError:
                logger.warning(
                    "Webhook delivery failed for %s to %s",
                    event.id,
                    webhook.url,
                    exc_info=True,
                )
