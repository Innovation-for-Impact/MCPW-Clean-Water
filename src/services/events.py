import asyncio
import ipaddress
import logging
import socket
import urllib.parse
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


def _is_safe_url(url: str) -> bool:
    """Check that a URL does not resolve to a private/loopback/reserved IP at dispatch time."""
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for _family, _type, _proto, _canonname, sockaddr in resolved:
        try:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
                return False
        except ValueError:
            return False
    return True


async def dispatch_webhooks(event_data: dict) -> None:
    """POST event payload to all active webhook URLs.

    Creates its own DB session so it is safe to run as a BackgroundTask
    after the request-scoped session has been closed.
    Dispatches concurrently with a 5s per-webhook timeout.
    Re-validates each URL at dispatch time to guard against DNS rebinding.
    """
    async with async_session_factory() as db:
        stmt = select(Webhook).where(Webhook.active.is_(True))
        result = await db.execute(stmt)
        webhooks = result.scalars().all()

    if not webhooks:
        return

    async with httpx.AsyncClient(timeout=5.0) as client:

        async def _post(url: str) -> None:
            if not _is_safe_url(url):
                logger.warning(
                    "Webhook URL %s resolves to a private/reserved address, skipping",
                    url,
                )
                return
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
