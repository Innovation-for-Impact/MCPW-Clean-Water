import uuid

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

# Simple many-to-many join table for incidents <-> jurisdictions
incident_jurisdictions = Table(
    "incident_jurisdictions",
    Base.metadata,
    Column(
        "incident_id",
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "jurisdiction_id",
        String(100),
        ForeignKey("jurisdictions.jurisdiction_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class IncidentContact(Base):
    """Join table for incidents <-> contacts with extra columns (role, deadline)."""

    __tablename__ = "incident_contacts"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(100))

    incident: Mapped["Incident"] = relationship(back_populates="contacts")
    contact: Mapped["Contact"] = relationship()


from src.models.contact import Contact  # noqa: E402, F401
from src.models.incident import Incident  # noqa: E402, F401
