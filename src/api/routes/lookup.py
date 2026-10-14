from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.schemas.lookup import LookupRequest, LookupResult
from src.services.lookup import run_lookup

router = APIRouter()


@router.post("/lookup", response_model=LookupResult)
async def lookup(request: LookupRequest, db: AsyncSession = Depends(get_db)):
    return await run_lookup(db, request)
