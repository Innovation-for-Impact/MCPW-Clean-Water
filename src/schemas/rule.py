from pydantic import BaseModel


class RuleCreate(BaseModel):
    jurisdiction_type: str
    water_body: str | None = None
    material: str | None = None
    size_threshold: float | None = None
    contact_id: int
    required: bool = True
    deadline: str | None = None
    priority: int = 100
    legal_citation: str | None = None


class RuleBrief(BaseModel):
    id: int

    model_config = {"from_attributes": True}


class RuleResponse(BaseModel):
    id: int
    jurisdiction_type: str
    water_body: str | None = None
    material: str | None = None
    size_threshold: float | None = None
    contact_id: int
    required: bool
    deadline: str | None = None
    priority: int
    legal_citation: str | None = None

    model_config = {"from_attributes": True}
