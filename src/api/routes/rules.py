from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import RequireRole, get_db
from src.models.rule import Rule
from src.models.user import User
from src.schemas.rule import RuleCreate

router = APIRouter()


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(RequireRole("viewer")),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(select(Rule).limit(limit).offset(offset))
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "jurisdiction_type": r.jurisdiction_type,
            "water_body": r.water_body,
            "material": r.material,
            "size_threshold": r.size_threshold,
            "contact_id": r.contact_id,
            "required": r.required,
            "deadline": r.deadline,
        }
        for r in rows
    ]


@router.post("/rules", status_code=201)
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    rule = Rule(
        jurisdiction_type=body.jurisdiction_type,
        water_body=body.water_body,
        material=body.material,
        size_threshold=body.size_threshold,
        contact_id=body.contact_id,
        required=body.required,
        deadline=body.deadline,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": rule.id}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(RequireRole("admin")),
):
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": True}
