from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class Waterway(Base):
    __tablename__ = "waterways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nhd_comid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    flow_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    downstream_comid: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    geometry: Mapped[str] = mapped_column(
        Geography(geometry_type="LINESTRING", srid=4326), nullable=False
    )
    has_beach_downstream: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    has_intake_downstream: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
