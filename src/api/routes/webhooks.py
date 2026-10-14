import ipaddress
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.models.webhook import Webhook

router = APIRouter()


class WebhookCreate(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urllib.parse.urlparse(v)
        if parsed.scheme not in ("https", "http"):
            raise ValueError("URL must use http or https scheme")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL must have a valid hostname")
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_reserved:
                raise ValueError("URL must not point to a private or reserved IP address")
        except ValueError as e:
            if "does not appear to be" not in str(e):
                raise
        return v


class WebhookResponse(BaseModel):
    id: int
    url: str
    active: bool
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(body: WebhookCreate, db: AsyncSession = Depends(get_db)):
    webhook = Webhook(url=body.url)
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        active=webhook.active,
        created_at=webhook.created_at.isoformat(),
    )


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Webhook))
    webhooks = result.scalars().all()
    return [
        WebhookResponse(
            id=w.id,
            url=w.url,
            active=w.active,
            created_at=w.created_at.isoformat(),
        )
        for w in webhooks
    ]


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(webhook)
    await db.commit()
