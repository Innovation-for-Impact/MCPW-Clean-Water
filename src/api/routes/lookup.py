from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.user import User
from src.schemas.lookup import LookupRequest, LookupResult
from src.services.lookup import run_lookup

router = APIRouter()


@router.post("/lookup", response_model=LookupResult)
async def lookup(
    request: LookupRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("responder", "admin")),
):
    return await run_lookup(db, request)
