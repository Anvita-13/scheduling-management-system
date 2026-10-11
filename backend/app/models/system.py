from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import NotificationType, RegistrationPhase


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_read", "user_id", "is_read", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False, length=30))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False)
    # Used to avoid flooding admins with the same alert repeatedly while it is still unread.
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegistrationSettings(Base):
    """Single-row table (id = 1) holding the registration period state and credit limits."""

    __tablename__ = "registration_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_settings_singleton"),
        CheckConstraint("min_credits <= max_credits", name="ck_settings_credit_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    phase: Mapped[RegistrationPhase] = mapped_column(
        Enum(RegistrationPhase, native_enum=False, length=10), default=RegistrationPhase.OPEN
    )
    min_credits: Mapped[int] = mapped_column(Integer, default=12)
    max_credits: Mapped[int] = mapped_column(Integer, default=24)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlgorithmRun(Base):
    """Audit trail of algorithm executions shown on the Admin status page."""

    __tablename__ = "algorithm_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20))
    summary: Mapped[Any] = mapped_column(JSON, default=dict)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
