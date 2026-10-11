from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import ClassStatus
from app.models.scheduling import Room, Slot
from app.models.user import Faculty


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        CheckConstraint("credits > 0", name="ck_subjects_credits_positive"),
        CheckConstraint("lab_credits >= 0", name="ck_subjects_lab_credits_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    credits: Mapped[int] = mapped_column(Integer)  # theory credits
    lab_credits: Mapped[int] = mapped_column(Integer, default=0)  # > 0 => theory + lab course
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    classes: Mapped[list["ClassSection"]] = relationship(back_populates="subject")

    @property
    def has_lab(self) -> bool:
        return (self.lab_credits or 0) > 0

    @property
    def total_credits(self) -> int:
        return self.credits + (self.lab_credits or 0)


class FacultySubject(Base):
    """Which faculty teach which subject, plus the default seat capacity of that class."""

    __tablename__ = "faculty_subjects"
    __table_args__ = (CheckConstraint("default_capacity >= 0", name="ck_fs_default_capacity"),)

    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.user_id", ondelete="CASCADE"), primary_key=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True
    )
    default_capacity: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClassSection(Base):
    """One *offering*: one faculty member teaching one subject, as a complete selectable unit.

    For a theory+lab subject the offering carries its own theory slot AND its own lab slot - a student who
    picks this faculty gets exactly this pair (no mixing theory of one faculty with lab of another).
    """

    __tablename__ = "class_sections"
    __table_args__ = (
        UniqueConstraint("subject_id", "faculty_id", name="uq_class_subject_faculty"),
        ForeignKeyConstraint(
            ["faculty_id", "subject_id"],
            ["faculty_subjects.faculty_id", "faculty_subjects.subject_id"],
            ondelete="CASCADE",
            name="fk_class_faculty_subject",
        ),
        CheckConstraint("capacity >= 0", name="ck_class_capacity_nonneg"),
        CheckConstraint("enrolled_count >= 0", name="ck_class_enrolled_nonneg"),
        CheckConstraint("enrolled_count <= capacity", name="ck_class_enrolled_le_capacity"),
        Index("ix_class_subject_status", "subject_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.user_id", ondelete="CASCADE"), index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=30)
    enrolled_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ClassStatus] = mapped_column(
        Enum(ClassStatus, native_enum=False, length=10), default=ClassStatus.OPEN
    )
    # Next FIFO sequence number for this class's request queue (assigned under a row lock).
    next_queue_seq: Mapped[int] = mapped_column(Integer, default=1)
    # NULL slot = not scheduled yet. Rooms are assigned automatically from the slots (never typed in by Admin).
    theory_slot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("slots.id", ondelete="SET NULL"), nullable=True)
    lab_slot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("slots.id", ondelete="SET NULL"), nullable=True)
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    lab_room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    # Set when the faculty member asks the administration to reopen a closed class; cleared on reopen/decline.
    reopen_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subject: Mapped[Subject] = relationship(back_populates="classes")
    faculty: Mapped[Faculty] = relationship()
    theory_slot: Mapped[Optional[Slot]] = relationship(foreign_keys=[theory_slot_id])
    lab_slot: Mapped[Optional[Slot]] = relationship(foreign_keys=[lab_slot_id])
    room: Mapped[Optional[Room]] = relationship(foreign_keys=[room_id])
    lab_room: Mapped[Optional[Room]] = relationship(foreign_keys=[lab_room_id])

    @property
    def is_scheduled(self) -> bool:
        return self.theory_slot_id is not None

    @property
    def remaining(self) -> int:
        return max(self.capacity - self.enrolled_count, 0)

    @property
    def is_open(self) -> bool:
        return self.status == ClassStatus.OPEN and self.remaining > 0
