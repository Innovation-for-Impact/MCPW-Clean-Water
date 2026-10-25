from pydantic import BaseModel


class RuleCreate(BaseModel):
    jurisdiction_type: str
    water_body: str | None = None
    material: str | None = None
    size_threshold: float | None = None
    contact_id: int
    required: bool = True
    deadline: str | None = None


class RuleResponse(BaseModel):
    id: int
    jurisdiction_type: str
    water_body: str | None = None
    material: str | None = None
    size_threshold: float | None = None
    contact_id: int
    required: bool
    deadline: str | None = None

    model_config = {"from_attributes": True}
