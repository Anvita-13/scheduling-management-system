from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.academic import ClassSection, Subject
from app.models.enums import RegistrationStatus, RequestStatus
from app.models.user import Student


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_ACTIVE = "status IN ('PENDING', 'ACCEPTED')"


class JoinRequest(Base):
    """A student's request to join a class; the rows with status PENDING *are* the FIFO queue."""

    __tablename__ = "join_requests"
    __table_args__ = (
        # queue_seq is unique per class => deterministic, gap-tolerant FIFO order.
        UniqueConstraint("class_id", "queue_seq", name="uq_request_class_seq"),
        Index("ix_request_queue", "class_id", "status", "queue_seq"),
        # A student can hold at most ONE live (pending/accepted) request per subject.
        Index(
            "uq_request_student_subject_active",
            "student_id",
            "subject_id",
            unique=True,
            postgresql_where=text(_ACTIVE),
            sqlite_where=text(_ACTIVE),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.user_id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_sections.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    # NULL for requests turned away at the door (class already full) - they never joined a queue.
    queue_seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, native_enum=False, length=10), default=RequestStatus.PENDING
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped[Student] = relationship()
    class_section: Mapped[ClassSection] = relationship()
    subject: Mapped[Subject] = relationship()


class Registration(Base):
    """Student <-> subject registration state (StudentSubjects)."""

    __tablename__ = "registrations"
    __table_args__ = (
        # A student can never register for the same subject twice.
        UniqueConstraint("student_id", "subject_id", name="uq_registration_student_subject"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.user_id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RegistrationStatus] = mapped_column(
        Enum(RegistrationStatus, native_enum=False, length=10), default=RegistrationStatus.SELECTED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped[Student] = relationship()
    subject: Mapped[Subject] = relationship()
    class_section: Mapped[Optional[ClassSection]] = relationship()
