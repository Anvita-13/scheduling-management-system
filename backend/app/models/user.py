from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=10), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped[Optional["Student"]] = relationship(back_populates="user", uselist=False)
    faculty: Mapped[Optional["Faculty"]] = relationship(back_populates="user", uselist=False)


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("max_credits > 0", name="ck_students_max_credits_positive"),
        CheckConstraint(
            "selected_credits IS NULL OR selected_credits > 0", name="ck_students_selected_credits"
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    roll_number: Mapped[str] = mapped_column(String(30), unique=True)
    max_credits: Mapped[int] = mapped_column(Integer, default=24)
    selected_credits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Programme + semester, e.g. "CSE-S3"; drives mandatory subjects and predicted clashes.
    group_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    user: Mapped[User] = relationship(back_populates="student")


class Faculty(Base):
    __tablename__ = "faculty"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(30), unique=True)
    department: Mapped[str] = mapped_column(String(100), default="")

    user: Mapped[User] = relationship(back_populates="faculty")
