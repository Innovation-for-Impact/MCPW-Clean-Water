from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact
from src.schemas.contact import ContactCreate


async def list_contacts(db: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[Contact]:
    result = await db.execute(select(Contact).limit(limit).offset(offset))
    return list(result.scalars().all())


async def create_contact(db: AsyncSession, body: ContactCreate) -> Contact:
    contact = Contact(
        agency=body.agency,
        role=body.role.value,
        jurisdiction_id=body.jurisdiction_id,
        jurisdiction_scope=body.jurisdiction_scope,
        phone=body.phone,
        after_hours_phone=body.after_hours_phone,
        email=body.email,
        hours=body.hours,
        reporting_deadline=body.reporting_deadline,
        source_url=body.source_url,
        last_verified=body.last_verified,
        notes=body.notes,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def delete_contact(db: AsyncSession, contact_id: int) -> None:
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(contact)
    await db.commit()
