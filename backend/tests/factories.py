"""Small helpers that create rows through the real service layer."""
from datetime import time
from itertools import count

from app.core.security import create_access_token
from app.models import Role, Room, RoomKind, Slot, SlotKind, SlotPeriod
from app.services import admin_service, registration_service

_seq = count(1)
_slot_seq = count(0)
PASSWORD = "Passw0rd!x"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def make_admin(db):
    from app.core.security import hash_password
    from app.models import User

    n = next(_seq)
    u = User(name=f"Admin {n}", email=f"admin{n}@t.edu", password_hash=hash_password(PASSWORD), role=Role.ADMIN)
    db.add(u)
    db.commit()
    return u


def make_faculty(db, name=None):
    n = next(_seq)
    return admin_service.create_faculty(db, name or f"Prof {n}", f"fac{n}@t.edu", PASSWORD, f"E{n}", "CS")


def make_student(db, credits=12, name=None, max_credits=24):
    n = next(_seq)
    u = admin_service.create_student(db, name or f"Student {n}", f"stu{n}@t.edu", PASSWORD, f"R{n}", max_credits)
    if credits:
        registration_service.set_credits(db, u.id, credits)
    return u


def make_subject(db, code=None, credits=3, lab_credits=0):
    n = next(_seq)
    return admin_service.create_subject(db, code or f"SUB{n}", f"Subject {n}", credits, lab_credits)


def make_slot(db, kind="THEORY", credits=3, name=None, periods=None):
    """A slot with its own unique, non-overlapping period(s) unless ``periods`` ([(day, 'HH:MM', 'HH:MM')]) is given."""
    n = next(_slot_seq)
    if periods is None:
        day = DAYS[n % 5]
        hour = 6 + (n // 5) % 17
        minute = (n // 85) * 30
        periods = [(day, time(hour, minute), time(hour, minute + 29))]
    else:
        periods = [(d, time(*map(int, a.split(":"))), time(*map(int, b.split(":")))) for d, a, b in periods]
    slot = Slot(name=name or f"S{n}-{kind[0]}{credits}", kind=SlotKind(kind), credits=credits)
    for d, a, b in periods:
        slot.periods.append(SlotPeriod(day=d, start_time=a, end_time=b))
    db.add(slot)
    db.commit()
    return slot


def make_rooms(db, lecture=3, lab=2, capacity=100):
    for i in range(lecture):
        admin_service.create_room(db, f"LH{i + 1}-{next(_seq)}", "LECTURE", capacity)
    for i in range(lab):
        admin_service.create_room(db, f"LAB{i + 1}-{next(_seq)}", "LAB", capacity)


def make_class(db, subject, faculty, capacity=2, placed=True, theory_slot=None, lab_slot=None):
    """An offering (faculty teaching the subject). By default it gets its own fresh, non-clashing slot(s)."""
    t = l = None
    if placed:
        t = theory_slot or make_slot(db, "THEORY", subject.credits)
        if subject.has_lab:
            l = lab_slot or make_slot(db, "LAB", 1)
    res = admin_service.create_offering(
        db, subject.id, faculty.id, capacity, t.id if t else None, l.id if l else None
    )
    return res["class_id"]


def headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def pick(db, student, subject, class_id):
    """Select a subject (if needed) and request a class.

    A subject with a single faculty is requested automatically when it is selected, so in that case the request
    that already exists is returned instead of sending a second one.
    """
    from sqlalchemy import select

    from app.core.errors import DomainError
    from app.models import JoinRequest, RequestStatus

    try:
        registration_service.select_subject(db, student.id, subject.id)
    except DomainError:  # already selected
        db.rollback()
    req = db.scalar(
        select(JoinRequest).where(
            JoinRequest.student_id == student.id, JoinRequest.class_id == class_id, JoinRequest.status == RequestStatus.PENDING
        )
    )
    if req is not None:
        return registration_service.SubmitOutcome("QUEUED", req, "", registration_service.queue_position(db, req))
    return registration_service.submit_request(db, student.id, class_id)
