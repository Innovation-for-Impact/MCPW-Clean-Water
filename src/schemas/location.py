from pydantic import BaseModel


class Location(BaseModel):
    lat: float
    lon: float
    address: str | None = None
