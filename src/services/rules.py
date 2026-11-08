from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rule import Rule
from src.schemas.rule import RuleCreate


async def list_rules(db: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[Rule]:
    result = await db.execute(select(Rule).limit(limit).offset(offset))
    return list(result.scalars().all())


async def create_rule(db: AsyncSession, body: RuleCreate) -> Rule:
    rule = Rule(
        jurisdiction_type=body.jurisdiction_type,
        water_body=body.water_body,
        material=body.material,
        size_threshold=body.size_threshold,
        contact_id=body.contact_id,
        required=body.required,
        deadline=body.deadline,
        priority=body.priority,
        legal_citation=body.legal_citation,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: int) -> None:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
