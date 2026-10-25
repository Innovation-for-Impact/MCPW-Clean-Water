from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.user import User
from src.models.webhook import Webhook
from src.schemas.webhook import WebhookCreate, WebhookResponse

router = APIRouter()


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
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
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(select(Webhook).limit(limit).offset(offset))
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
async def delete_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(webhook)
    await db.commit()
