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


def _resolve_safe_url(url: str) -> str | None:
    """Resolve URL hostname and return URL with pinned IP if safe, None if unsafe.

    Replaces hostname with the resolved IP to prevent TOCTOU DNS rebinding attacks.
    """
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return None
    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return None
    safe_ip = None
    for _family, _type, _proto, _canonname, sockaddr in resolved:
        try:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
                return None
            if safe_ip is None:
                safe_ip = str(addr)
        except ValueError:
            return None
    if safe_ip is None:
        return None
    # Replace hostname with resolved IP to pin the connection
    pinned = parsed._replace(netloc=f"{safe_ip}:{parsed.port}" if parsed.port else safe_ip)
    return urllib.parse.urlunparse(pinned)


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

        async def _post(url: str, original_host: str) -> None:
            pinned_url = _resolve_safe_url(url)
            if pinned_url is None:
                logger.warning(
                    "Webhook URL %s resolves to a private/reserved address, skipping",
                    url,
                )
                return
            try:
                await client.post(
                    pinned_url, json=event_data,
                    headers={"Host": original_host},
                )
            except httpx.HTTPError:
                logger.warning(
                    "Webhook delivery failed for event %s to %s",
                    event_data.get("event_id"),
                    url,
                    exc_info=True,
                )

        await asyncio.gather(*[
            _post(w.url, urllib.parse.urlparse(w.url).hostname or "")
            for w in webhooks
        ])
