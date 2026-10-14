from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    water_body: Mapped[str | None] = mapped_column(String(50))
    material: Mapped[str | None] = mapped_column(String(50))
    size_threshold: Mapped[float | None] = mapped_column(Float)
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=False
    )
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(100))

    contact: Mapped["Contact"] = relationship()


from src.models.contact import Contact  # noqa: E402, F401
