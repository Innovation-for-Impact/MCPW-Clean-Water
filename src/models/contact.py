from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    jurisdiction_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("jurisdictions.jurisdiction_id"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    after_hours_phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    hours: Mapped[str | None] = mapped_column(String(100))
    reporting_deadline: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    last_verified: Mapped[date] = mapped_column(Date, nullable=False)

    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="contacts")
