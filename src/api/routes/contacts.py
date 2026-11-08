from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.user import User
from src.schemas.contact import ContactBrief, ContactCreate, ContactResponse
from src.services.contacts import create_contact as svc_create
from src.services.contacts import delete_contact as svc_delete
from src.services.contacts import list_contacts as svc_list

router = APIRouter()


@router.get("/contacts", response_model=list[ContactResponse])
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("viewer")),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await svc_list(db, limit=limit, offset=offset)


@router.post("/contacts", status_code=201, response_model=ContactBrief)
async def create_contact(
    body: ContactCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    return await svc_create(db, body)


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    await svc_delete(db, contact_id)
    return {"deleted": True}
