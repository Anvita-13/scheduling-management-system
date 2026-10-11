from datetime import time
from typing import Optional

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import RoomKind, SlotKind


class Slot(Base):
    """A selectable weekly slot package such as ``A1+TA1`` (theory) or ``L3+L4`` (lab).

    Its meeting times are the rows of ``slot_periods``. Two slots *clash* when any of their periods overlap
    in time - they do not have to be the same slot (a theory slot can overlap a lab slot).
    """

    __tablename__ = "slots"
    __table_args__ = (CheckConstraint("credits > 0", name="ck_slot_credits_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    kind: Mapped[SlotKind] = mapped_column(Enum(SlotKind, native_enum=False, length=10))
    # Theory credits this package is meant for (2, 3 or 4 periods-worth); labs use 1.
    credits: Mapped[int] = mapped_column(Integer)

    periods: Mapped[list["SlotPeriod"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan", order_by="SlotPeriod.id"
    )


class SlotPeriod(Base):
    __tablename__ = "slot_periods"
    __table_args__ = (
        UniqueConstraint("slot_id", "day", "start_time", name="uq_slot_period"),
        CheckConstraint("start_time < end_time", name="ck_slot_period_start_before_end"),
        Index("ix_slot_periods_slot", "slot_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"))
    day: Mapped[str] = mapped_column(String(3))  # Mon..Sun
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    slot: Mapped[Slot] = relationship(back_populates="periods")


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_room_capacity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    kind: Mapped[RoomKind] = mapped_column(Enum(RoomKind, native_enum=False, length=10), default=RoomKind.LECTURE)
    capacity: Mapped[int] = mapped_column(Integer, default=60)
