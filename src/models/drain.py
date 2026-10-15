from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class Drain(Base):
    __tablename__ = "drains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drain_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    drain_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(5), nullable=False)  # '1','2','3','4'
    conveyance_owner: Mapped[str] = mapped_column(String(30), nullable=False)
    intercounty: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    upstream_counties: Mapped[str | None] = mapped_column(String(255), nullable=True)  # comma-separated: "Oakland,St. Clair"
    drain_district_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    has_response_plan: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    segments: Mapped[list["DrainSegment"]] = relationship(back_populates="drain", lazy="selectin")
    response_sites: Mapped[list["ResponseSite"]] = relationship(back_populates="drain", lazy="selectin")


class DrainSegment(Base):
    __tablename__ = "drain_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drain_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("drains.drain_id"), nullable=False, index=True
    )
    segment_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    conveyance_type: Mapped[str] = mapped_column(String(20), nullable=False)  # open, enclosed, sanitary, combined
    downstream_segment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outlet_nhd_comid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    geometry: Mapped[str] = mapped_column(
        Geography(geometry_type="LINESTRING", srid=4326), nullable=False
    )

    drain: Mapped["Drain"] = relationship(back_populates="segments")


class ResponseSite(Base):
    __tablename__ = "response_sites"
    __table_args__ = (UniqueConstraint("drain_id", "site_order", name="uq_response_site_drain_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drain_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("drains.drain_id"), nullable=False, index=True
    )
    site_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'plan' or 'computed'
    boom_anchor: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    access_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_sheet: Mapped[str | None] = mapped_column(String(20), nullable=True)
    geometry: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )

    drain: Mapped["Drain"] = relationship(back_populates="response_sites")
