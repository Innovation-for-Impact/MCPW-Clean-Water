from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.contact import Contact
from src.models.user import User
from src.schemas.contact import ContactCreate

router = APIRouter()


@router.get("/contacts")
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("viewer")),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(select(Contact).limit(limit).offset(offset))
    rows = result.scalars().all()
    return [
        {
            "id": c.id,
            "agency": c.agency,
            "role": c.role,
            "jurisdiction_id": c.jurisdiction_id,
            "phone": c.phone,
            "after_hours_phone": c.after_hours_phone,
            "email": c.email,
            "hours": c.hours,
            "reporting_deadline": c.reporting_deadline,
            "source_url": c.source_url,
            "last_verified": c.last_verified.isoformat() if c.last_verified else None,
        }
        for c in rows
    ]


@router.post("/contacts", status_code=201)
async def create_contact(
    body: ContactCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    contact = Contact(
        agency=body.agency,
        role=body.role.value,
        jurisdiction_id=body.jurisdiction_id,
        phone=body.phone,
        after_hours_phone=body.after_hours_phone,
        email=body.email,
        hours=body.hours,
        reporting_deadline=body.reporting_deadline,
        source_url=body.source_url,
        last_verified=body.last_verified,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return {"id": contact.id, "agency": contact.agency}


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(contact)
    await db.commit()
    return {"deleted": True}
