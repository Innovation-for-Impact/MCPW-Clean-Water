import asyncio
import ipaddress
import logging
import socket
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from src.models.database import async_session_factory
from src.models.event import Event
from src.models.webhook import Webhook
from src.models.webhook_delivery import WebhookDelivery

logger = logging.getLogger(__name__)

# Exponential backoff delays: 10s, 30s, 90s, 270s, 810s (~13.5min)
RETRY_DELAYS = [10, 30, 90, 270, 810]
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # initial attempt + retries


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
        timestamp=datetime.now(UTC),
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

    Creates a WebhookDelivery record for each webhook. On failure, schedules
    retries with exponential backoff. After MAX_ATTEMPTS, marks as 'failed'
    (dead letter).
    """
    async with async_session_factory() as db:
        stmt = select(Webhook).where(Webhook.active.is_(True))
        result = await db.execute(stmt)
        webhooks = result.scalars().all()

        if not webhooks:
            return

        # Create delivery records for each webhook
        deliveries = []
        for webhook in webhooks:
            delivery = WebhookDelivery(
                id=uuid.uuid4(),
                webhook_id=webhook.id,
                event_id=event_data.get("event_id", "unknown"),
                status="pending",
                attempts=0,
                max_attempts=MAX_ATTEMPTS,
                payload=event_data,
            )
            db.add(delivery)
            deliveries.append((delivery, webhook))
        await db.commit()

    # Attempt first delivery for each webhook
    async with httpx.AsyncClient(timeout=5.0) as client:
        await asyncio.gather(*[_attempt_delivery(client, d, w) for d, w in deliveries])


async def _attempt_delivery(client: httpx.AsyncClient, delivery: WebhookDelivery, webhook: Webhook) -> None:
    """Attempt a single webhook delivery and update the delivery record."""
    url = webhook.url
    original_host = urllib.parse.urlparse(url).hostname or ""
    pinned_url = _resolve_safe_url(url)

    async with async_session_factory() as db:
        # Re-attach delivery to this session
        delivery = await db.get(WebhookDelivery, delivery.id)
        if delivery is None:
            return

        delivery.attempts += 1
        delivery.last_attempt_at = datetime.now(UTC)

        if pinned_url is None:
            delivery.status = "failed"
            delivery.error_message = "URL resolves to private/reserved address"
            await db.commit()
            logger.warning("Webhook URL %s resolves to a private/reserved address, marking as failed", url)
            return

        try:
            resp = await client.post(
                pinned_url,
                json=delivery.payload,
                headers={"Host": original_host},
            )
            delivery.status_code = resp.status_code
            if 200 <= resp.status_code < 300:
                delivery.status = "success"
                delivery.error_message = None
            else:
                _handle_failure(delivery, f"HTTP {resp.status_code}")
        except httpx.HTTPError as exc:
            _handle_failure(delivery, str(exc)[:500])
            logger.warning(
                "Webhook delivery failed for event %s to %s: %s",
                delivery.event_id,
                url,
                exc,
            )

        await db.commit()


def _handle_failure(delivery: WebhookDelivery, error: str) -> None:
    """Mark delivery for retry or as failed (dead letter) if max attempts reached."""
    delivery.error_message = error
    if delivery.attempts >= delivery.max_attempts:
        delivery.status = "failed"
        logger.warning(
            "Webhook delivery %s exhausted %d attempts, moved to dead letter",
            delivery.id,
            delivery.max_attempts,
        )
    else:
        delivery.status = "pending"
        delay = RETRY_DELAYS[delivery.attempts - 1] if delivery.attempts - 1 < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)


async def retry_pending_deliveries() -> int:
    """Retry all pending deliveries whose next_retry_at has passed.

    Returns the number of deliveries retried. Intended to be called
    by a background scheduler or cron job.
    """
    now = datetime.now(UTC)
    async with async_session_factory() as db:
        stmt = (
            select(WebhookDelivery)
            .where(WebhookDelivery.status == "pending")
            .where(WebhookDelivery.attempts > 0)
            .where(WebhookDelivery.next_retry_at <= now)
        )
        result = await db.execute(stmt)
        deliveries = result.scalars().all()

        if not deliveries:
            return 0

        # Load associated webhooks
        webhook_ids = {d.webhook_id for d in deliveries}
        wh_result = await db.execute(select(Webhook).where(Webhook.id.in_(webhook_ids)))
        webhooks_by_id = {w.id: w for w in wh_result.scalars().all()}

    retried = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        for delivery in deliveries:
            webhook = webhooks_by_id.get(delivery.webhook_id)
            if webhook and webhook.active:
                await _attempt_delivery(client, delivery, webhook)
                retried += 1

    return retried
