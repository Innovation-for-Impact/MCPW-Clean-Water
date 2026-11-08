from datetime import date

from pydantic import BaseModel

from src.schemas.enums import ContactRole


class ContactResponse(BaseModel):
    id: int
    agency: str
    role: str
    jurisdiction_id: str
    jurisdiction_scope: str | None = None
    phone: str
    after_hours_phone: str | None = None
    email: str | None = None
    hours: str | None = None
    reporting_deadline: str | None = None
    source_url: str
    last_verified: date
    notes: str | None = None

    model_config = {"from_attributes": True}


class ContactBrief(BaseModel):
    id: int
    agency: str

    model_config = {"from_attributes": True}


class Contact(BaseModel):
    """Contact schema used in lookup results and event payloads (no id)."""

    agency: str
    role: ContactRole
    jurisdiction_id: str
    jurisdiction_scope: str | None = None
    phone: str
    after_hours_phone: str | None = None
    email: str | None = None
    hours: str | None = None
    reporting_deadline: str | None = None
    source_url: str
    last_verified: date
    notes: str | None = None

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    agency: str
    role: ContactRole
    jurisdiction_id: str
    jurisdiction_scope: str | None = None
    phone: str
    after_hours_phone: str | None = None
    email: str | None = None
    hours: str | None = None
    reporting_deadline: str | None = None
    source_url: str
    last_verified: date
    notes: str | None = None
