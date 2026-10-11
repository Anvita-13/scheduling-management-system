"""Pydantic request/response schemas (all incoming data is validated here)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth ---------------------------------------------------------------- #
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    current_password: Optional[str] = Field(default=None, max_length=128, description="needed to change the e-mail")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ---- admin --------------------------------------------------------------- #
class SubjectCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9\-_]+$")
    name: str = Field(min_length=2, max_length=150)
    credits: int = Field(ge=1, le=6, description="theory credits")
    lab_credits: int = Field(default=0, ge=0, le=4, description="0 = theory only; >0 = theory + lab")


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    credits: Optional[int] = Field(default=None, ge=1, le=6)
    lab_credits: Optional[int] = Field(default=None, ge=0, le=4)


class FacultyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    employee_code: str = Field(min_length=1, max_length=30)
    department: str = Field(default="", max_length=100)


class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    roll_number: str = Field(min_length=1, max_length=30)
    max_credits: Optional[int] = Field(default=None, ge=1, le=60)


class OfferingCreate(BaseModel):
    """A faculty member becomes an option for a subject, optionally with its slots."""

    subject_id: int
    faculty_id: int
    capacity: Optional[int] = Field(default=None, ge=0, le=1000)
    theory_slot_id: Optional[int] = None
    lab_slot_id: Optional[int] = None


class PlacementUpdate(BaseModel):
    """Both null = un-place the offering."""

    theory_slot_id: Optional[int] = None
    lab_slot_id: Optional[int] = None


class CapacityUpdate(BaseModel):
    capacity: int = Field(ge=0, le=1000)


class RegistrationUpdate(BaseModel):
    phase: Optional[Literal["OPEN", "CLOSED"]] = None
    min_credits: Optional[int] = Field(default=None, ge=1, le=60)
    max_credits: Optional[int] = Field(default=None, ge=1, le=60)


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    kind: Literal["LECTURE", "LAB"] = "LECTURE"
    capacity: int = Field(ge=1, le=1000)


class RoomOut(ORM):
    id: int
    name: str
    kind: str
    capacity: int


# ---- student ------------------------------------------------------------- #
class CreditsUpdate(BaseModel):
    credits: int = Field(ge=1, le=60)


class JoinRequestCreate(BaseModel):
    class_id: int


# ---- notifications ------------------------------------------------------- #
class NotificationOut(ORM):
    id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime
