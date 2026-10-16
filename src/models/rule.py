from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
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
    legal_citation: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", nullable=False
    )

    # Handbook / drain-context match columns (NULL = any)
    drain_tier: Mapped[str | None] = mapped_column(String(5))
    drain_id: Mapped[str | None] = mapped_column(String(100))
    conveyance_owner: Mapped[str | None] = mapped_column(String(30))
    conveyance_type: Mapped[str | None] = mapped_column(String(20))
    hazard_class: Mapped[str | None] = mapped_column(String(30))
    after_hours: Mapped[bool | None] = mapped_column(Boolean)
    immediate_threat: Mapped[bool | None] = mapped_column(Boolean)

    # What the rule produces
    action_type: Mapped[str] = mapped_column(
        String(20), default="notify", server_default="notify", nullable=False
    )
    action: Mapped[str | None] = mapped_column(Text)
    handbook_ref: Mapped[str | None] = mapped_column(String(50))

    contact: Mapped["Contact"] = relationship()
