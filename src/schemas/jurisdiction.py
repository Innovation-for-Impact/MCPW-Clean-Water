from pydantic import BaseModel


class Jurisdiction(BaseModel):
    layer: str
    jurisdiction_id: str
    name: str

    model_config = {"from_attributes": True}
