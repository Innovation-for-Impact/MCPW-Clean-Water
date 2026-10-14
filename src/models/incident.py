import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(500))
    water_body: Mapped[str] = mapped_column(String(50), nullable=False)
    material: Mapped[str] = mapped_column(String(50), nullable=False)
    material_detail: Mapped[str | None] = mapped_column(String(200))
    quantity: Mapped[float | None] = mapped_column(Float)
    quantity_unit: Mapped[str] = mapped_column(String(10), default="gal")
    quantity_gallons: Mapped[float | None] = mapped_column(Float)
    time_observed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporter_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    buffer_radius_m: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    jurisdictions: Mapped[list["Jurisdiction"]] = relationship(
        secondary="incident_jurisdictions", back_populates="incidents", lazy="selectin"
    )
    contacts: Mapped[list["IncidentContact"]] = relationship(
        back_populates="incident", lazy="selectin"
    )
    events: Mapped[list["Event"]] = relationship(back_populates="incident", lazy="selectin")
