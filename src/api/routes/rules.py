from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.user import User
from src.schemas.rule import RuleBrief, RuleCreate, RuleResponse
from src.services.rules import create_rule as svc_create
from src.services.rules import delete_rule as svc_delete
from src.services.rules import list_rules as svc_list

router = APIRouter()


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("viewer")),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await svc_list(db, limit=limit, offset=offset)


@router.post("/rules", status_code=201, response_model=RuleBrief)
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    return await svc_create(db, body)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    await svc_delete(db, rule_id)
    return {"deleted": True}
