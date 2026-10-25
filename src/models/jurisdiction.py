from geoalchemy2 import Geography
from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    layer: Mapped[str] = mapped_column(String(100), nullable=False)
    jurisdiction_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    geometry: Mapped[str] = mapped_column(
        Geography(geometry_type="GEOMETRY", srid=4326), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[str | None] = mapped_column(Date, nullable=True)

    incidents: Mapped[list["Incident"]] = relationship(
        secondary="incident_jurisdictions", back_populates="jurisdictions", lazy="noload"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="jurisdiction", lazy="noload"
    )
