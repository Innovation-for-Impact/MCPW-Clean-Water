from datetime import date

from pydantic import BaseModel

from src.schemas.enums import ContactRole


class Contact(BaseModel):
    agency: str
    role: ContactRole
    jurisdiction_id: str
    phone: str
    after_hours_phone: str | None = None
    email: str | None = None
    hours: str | None = None
    reporting_deadline: str | None = None
    source_url: str
    last_verified: date

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    agency: str
    role: ContactRole
    jurisdiction_id: str
    phone: str
    after_hours_phone: str | None = None
    email: str | None = None
    hours: str | None = None
    reporting_deadline: str | None = None
    source_url: str
    last_verified: date
