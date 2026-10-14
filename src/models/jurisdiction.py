from geoalchemy2 import Geography
from sqlalchemy import Integer, String
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

    incidents: Mapped[list["Incident"]] = relationship(
        secondary="incident_jurisdictions", back_populates="jurisdictions", lazy="selectin"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="jurisdiction", lazy="selectin"
    )


from src.models.contact import Contact  # noqa: E402, F401
from src.models.incident import Incident  # noqa: E402, F401
