import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.event import Event
from src.models.user import User

router = APIRouter()


@router.get("/events")
async def list_events(
    since: datetime | None = Query(None, description="Return events after this ISO datetime"),
    limit: int = Query(50, ge=1, le=200),
    incident_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("viewer", "responder", "admin")),
):
    stmt = select(Event).order_by(Event.timestamp.desc())

    if since:
        stmt = stmt.where(Event.timestamp > since)
    if incident_id:
        stmt = stmt.where(Event.incident_id == incident_id)

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    events = result.scalars().all()

    return [
        {
            "event_id": str(e.id),
            "event_type": e.event_type,
            "event_version": e.event_version,
            "timestamp": e.timestamp.isoformat(),
            "incident_id": str(e.incident_id),
            "data": e.payload,
        }
        for e in events
    ]
