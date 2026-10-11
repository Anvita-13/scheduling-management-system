"""Admin management: subjects, offerings (faculty + slots), registration period, demand, rooms, people."""
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.core.security import hash_password
from app.models import (
    ClassSection,
    CurriculumEntry,
    Faculty,
    FacultySubject,
    JoinRequest,
    NotificationType,
    Registration,
    RegistrationPhase,
    RegistrationStatus,
    RequestStatus,
    Role,
    Room,
    RoomKind,
    Student,
    Subject,
    User,
)
from app.services import notification_service, registration_service, room_service, slot_service, timetable_service


def _commit_unique(db: Session, message: str, code: str = "DUPLICATE") -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(message, code=code)


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
def create_faculty(db: Session, name: str, email: str, password: str, employee_code: str, department: str) -> User:
    user = User(name=name, email=email.lower(), password_hash=hash_password(password), role=Role.FACULTY)
    user.faculty = Faculty(employee_code=employee_code, department=department)
    db.add(user)
    _commit_unique(db, "A user with this email or employee code already exists.")
    return user


def create_student(
    db: Session, name: str, email: str, password: str, roll_number: str,
    max_credits: Optional[int] = None, group_code: Optional[str] = None,
) -> User:
    user = User(name=name, email=email.lower(), password_hash=hash_password(password), role=Role.STUDENT)
    user.student = Student(
        roll_number=roll_number, max_credits=max_credits or app_settings.DEFAULT_MAX_CREDITS, group_code=group_code
    )
    db.add(user)
    _commit_unique(db, "A user with this email or roll number already exists.")
    return user


def list_faculty(db: Session) -> List[Dict[str, Any]]:
    subs: Dict[int, List[str]] = {}
    for fid, code in db.execute(
        select(FacultySubject.faculty_id, Subject.code).join(Subject, Subject.id == FacultySubject.subject_id)
    ):
        subs.setdefault(fid, []).append(code)
    rows = db.scalars(select(Faculty).join(User).order_by(User.name))
    return [
        {
            "user_id": f.user_id,
            "name": f.user.name,
            "email": f.user.email,
            "employee_code": f.employee_code,
            "department": f.department,
            "subjects": sorted(subs.get(f.user_id, [])),
        }
        for f in rows
    ]


def list_students(db: Session) -> List[Dict[str, Any]]:
    rows = db.scalars(select(Student).join(User).order_by(Student.roll_number))
    return [
        {
            "user_id": s.user_id,
            "name": s.user.name,
            "email": s.user.email,
            "roll_number": s.roll_number,
            "group_code": s.group_code,
            "selected_credits": s.selected_credits,
            "max_credits": s.max_credits,
        }
        for s in rows
    ]


def list_curriculum(db: Session) -> List[Dict[str, Any]]:
    out: Dict[str, Dict[str, List[str]]] = {}
    for g, code, mand in db.execute(
        select(CurriculumEntry.group_code, Subject.code, CurriculumEntry.is_mandatory)
        .join(Subject, Subject.id == CurriculumEntry.subject_id)
        .order_by(CurriculumEntry.group_code, Subject.code)
    ):
        out.setdefault(g, {"mandatory": [], "optional": []})["mandatory" if mand else "optional"].append(code)
    return [{"group_code": g, **v} for g, v in out.items()]


# --------------------------------------------------------------------------- #
# Subjects & offerings
# --------------------------------------------------------------------------- #
def list_classes(db: Session) -> List[Dict[str, Any]]:
    """Every offering with slots, rooms and seats."""
    pending: Dict[int, int] = dict(
        db.execute(
            select(JoinRequest.class_id, func.count(JoinRequest.id))
            .where(JoinRequest.status == RequestStatus.PENDING)
            .group_by(JoinRequest.class_id)
        ).all()
    )
    out = []
    for c in db.scalars(select(ClassSection).order_by(ClassSection.subject_id, ClassSection.id)):
        out.append(
            {
                "id": c.id,
                "subject_id": c.subject_id,
                "subject_code": c.subject.code,
                "subject_name": c.subject.name,
                "has_lab": c.subject.has_lab,
                "faculty_id": c.faculty_id,
                "faculty_name": c.faculty.user.name,
                "capacity": c.capacity,
                "enrolled_count": c.enrolled_count,
                "remaining": c.remaining,
                "status": c.status.value,
                "pending_requests": pending.get(c.id, 0),
                "theory_slot_id": c.theory_slot_id,
                "lab_slot_id": c.lab_slot_id,
                "theory_slot": c.theory_slot.name if c.theory_slot else None,
                "lab_slot": c.lab_slot.name if c.lab_slot else None,
                "theory_times": slot_service.period_text(c.theory_slot),
                "lab_times": slot_service.period_text(c.lab_slot),
                "room": c.room.name if c.room else None,
                "lab_room": c.lab_room.name if c.lab_room else None,
                "scheduled": c.is_scheduled,
                "locked": c.enrolled_count > 0 or pending.get(c.id, 0) > 0,
            }
        )
    return out


def list_subjects(db: Session) -> List[Dict[str, Any]]:
    by_subject: Dict[int, List[Dict[str, Any]]] = {}
    for c in list_classes(db):
        by_subject.setdefault(c["subject_id"], []).append(c)
    groups: Dict[int, List[str]] = {}
    for g, sid, mand in db.execute(select(CurriculumEntry.group_code, CurriculumEntry.subject_id, CurriculumEntry.is_mandatory)):
        groups.setdefault(sid, []).append(f"{g}{' (mandatory)' if mand else ''}")
    return [
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "credits": s.credits,
            "lab_credits": s.lab_credits,
            "has_lab": s.has_lab,
            "groups": sorted(groups.get(s.id, [])),
            "offerings": by_subject.get(s.id, []),
        }
        for s in db.scalars(select(Subject).order_by(Subject.code))
    ]


def create_subject(db: Session, code: str, name: str, credits: int, lab_credits: int = 0) -> Subject:
    s = Subject(code=code.upper(), name=name, credits=credits, lab_credits=lab_credits)
    db.add(s)
    _commit_unique(db, f"Subject code {code.upper()} already exists.")
    return s


def update_subject(db: Session, subject_id: int, name: Optional[str], credits: Optional[int], lab_credits: Optional[int]) -> Subject:
    s = db.get(Subject, subject_id)
    if s is None:
        raise NotFoundError("Subject not found")
    if (credits is not None and credits != s.credits) or (lab_credits is not None and bool(lab_credits) != s.has_lab):
        if db.scalar(select(func.count(ClassSection.id)).where(ClassSection.subject_id == subject_id, ClassSection.theory_slot_id.is_not(None))):
            raise ConflictError("Offerings of this subject already have slots; clear them before changing credits.", code="IN_USE")
    if name is not None:
        s.name = name
    if credits is not None:
        s.credits = credits
    if lab_credits is not None:
        s.lab_credits = lab_credits
    db.commit()
    return s


def delete_subject(db: Session, subject_id: int) -> None:
    s = db.get(Subject, subject_id)
    if s is None:
        raise NotFoundError("Subject not found")
    in_use = db.scalar(select(func.count(Registration.id)).where(Registration.subject_id == subject_id))
    if in_use:
        raise ConflictError("Students have registered for this subject; it cannot be deleted.", code="IN_USE")
    db.delete(s)
    db.commit()


def create_offering(
    db: Session, subject_id: int, faculty_id: int, capacity: Optional[int],
    theory_slot_id: Optional[int] = None, lab_slot_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Make a faculty member an option for a subject, optionally with its slots (validated against clashes)."""
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError("Subject not found")
    if db.get(Faculty, faculty_id) is None:
        raise NotFoundError("Faculty not found")
    if db.get(FacultySubject, (faculty_id, subject_id)):
        raise ConflictError("This faculty member already teaches the subject.", code="ALREADY_ASSIGNED")
    cap = app_settings.DEFAULT_CLASS_CAPACITY if capacity is None else capacity
    warnings = slot_service.check_placement(db, subject, faculty_id, theory_slot_id, lab_slot_id)
    db.add(FacultySubject(faculty_id=faculty_id, subject_id=subject_id, default_capacity=cap))
    db.flush()
    cls = ClassSection(
        subject_id=subject_id, faculty_id=faculty_id, capacity=cap,
        theory_slot_id=theory_slot_id, lab_slot_id=lab_slot_id if subject.has_lab else None,
    )
    db.add(cls)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Could not create the offering.", code="DUPLICATE")
    rooms = room_service.assign_rooms(db)
    if theory_slot_id is not None and cls.id in rooms["unassigned_class_ids"]:
        db.rollback()
        raise ConflictError("No free room of the right type and size is available during those periods.", code="NO_ROOM")
    if theory_slot_id is not None:
        warnings = timetable_service.group_warnings(db, cls)
    db.commit()
    return {"class_id": cls.id, "warnings": warnings}


def delete_offering(db: Session, class_id: int) -> None:
    cls = db.get(ClassSection, class_id)
    if cls is None:
        raise NotFoundError("Offering not found")
    if slot_service.is_locked(db, cls):
        raise ConflictError("Students are enrolled or waiting in this class; it cannot be removed.", code="IN_USE")
    link = db.get(FacultySubject, (cls.faculty_id, cls.subject_id))
    db.delete(cls)
    if link:
        db.delete(link)
    db.flush()
    room_service.assign_rooms(db)
    db.commit()


# --------------------------------------------------------------------------- #
# Registration period
# --------------------------------------------------------------------------- #
def update_registration(
    db: Session, phase: Optional[str], min_credits: Optional[int], max_credits: Optional[int]
) -> Dict[str, Any]:
    s = registration_service.get_registration_settings(db)
    lo = s.min_credits if min_credits is None else min_credits
    hi = s.max_credits if max_credits is None else max_credits
    if lo > hi:
        raise ValidationFailed("Minimum credits cannot exceed maximum credits.")
    s.min_credits, s.max_credits = lo, hi
    if phase is not None:
        new_phase = RegistrationPhase(phase)
        if new_phase != s.phase:
            s.phase = new_phase
            msg = (
                "Registration is now OPEN. You can select subjects and send join requests."
                if new_phase == RegistrationPhase.OPEN
                else "The registration period has ended. Requests are no longer accepted."
            )
            notification_service.notify_all_with_role(db, Role.STUDENT, NotificationType.REGISTRATION_STATUS, msg)
    db.commit()
    return registration_info(db)


def registration_info(db: Session) -> Dict[str, Any]:
    s = registration_service.get_registration_settings(db)
    db.flush()
    return {
        "phase": s.phase.value,
        "min_credits": s.min_credits,
        "max_credits": s.max_credits,
        "students": db.scalar(select(func.count(Student.user_id))) or 0,
        "students_with_credits": db.scalar(
            select(func.count(Student.user_id)).where(Student.selected_credits.is_not(None))
        )
        or 0,
        "registrations": db.scalar(select(func.count(Registration.id))) or 0,
        "enrolled": db.scalar(
            select(func.count(Registration.id)).where(Registration.status == RegistrationStatus.ENROLLED)
        )
        or 0,
        "pending_requests": db.scalar(
            select(func.count(JoinRequest.id)).where(JoinRequest.status == RequestStatus.PENDING)
        )
        or 0,
    }


# --------------------------------------------------------------------------- #
# Demand / waitlist
# --------------------------------------------------------------------------- #
def demand_report(db: Session) -> Dict[str, Any]:
    classes = list_classes(db)
    by_subject: Dict[int, List[Dict[str, Any]]] = {}
    for c in classes:
        by_subject.setdefault(c["subject_id"], []).append(c)
    reg_counts: Dict[int, Dict[str, int]] = {}
    for sid, status, n in db.execute(
        select(Registration.subject_id, Registration.status, func.count(Registration.id)).group_by(
            Registration.subject_id, Registration.status
        )
    ):
        reg_counts.setdefault(sid, {})[status.value] = n
    turned_away: Dict[int, int] = {}
    for sid, n in db.execute(
        select(JoinRequest.subject_id, func.count(func.distinct(JoinRequest.student_id)))
        .join(
            Registration,
            (Registration.student_id == JoinRequest.student_id) & (Registration.subject_id == JoinRequest.subject_id),
        )
        .where(JoinRequest.status == RequestStatus.REJECTED, Registration.status == RegistrationStatus.SELECTED)
        .group_by(JoinRequest.subject_id)
    ):
        turned_away[sid] = n

    subjects = []
    for s in db.scalars(select(Subject).order_by(Subject.code)):
        cs = by_subject.get(s.id, [])
        counts = reg_counts.get(s.id, {})
        unmet = counts.get("SELECTED", 0)
        subjects.append(
            {
                "subject_id": s.id,
                "code": s.code,
                "name": s.name,
                "demand": sum(counts.values()),
                "enrolled": counts.get("ENROLLED", 0),
                "pending": counts.get("REQUESTED", 0),
                "unmet": unmet,
                "turned_away": turned_away.get(s.id, 0),
                "total_capacity": sum(c["capacity"] for c in cs),
                "seats_remaining": sum(c["remaining"] for c in cs if c["status"] == "OPEN"),
                "classes": cs,
                "no_faculty_available": bool(unmet or counts.get("REQUESTED", 0))
                and not any(c["status"] == "OPEN" and c["remaining"] > 0 and c["scheduled"] for c in cs),
            }
        )
    waitlist = []
    rows = db.execute(
        select(Registration, Student, User, Subject)
        .join(Student, Student.user_id == Registration.student_id)
        .join(User, User.id == Student.user_id)
        .join(Subject, Subject.id == Registration.subject_id)
        .where(Registration.status == RegistrationStatus.SELECTED)
        .order_by(Subject.code, Registration.created_at)
    ).all()
    for reg, st, user, subj in rows:
        waitlist.append(
            {
                "student_id": st.user_id,
                "student_name": user.name,
                "roll_number": st.roll_number,
                "subject_id": subj.id,
                "subject_code": subj.code,
                "since": reg.created_at,
            }
        )
    return {"subjects": subjects, "waitlist": waitlist, "total_unmet": sum(s["unmet"] for s in subjects)}


def dashboard(db: Session) -> Dict[str, Any]:
    info = registration_info(db)
    classes = list_classes(db)
    clashes = timetable_service.clash_report(db)
    return {
        "registration": info,
        "subjects": db.scalar(select(func.count(Subject.id))) or 0,
        "faculty": db.scalar(select(func.count(Faculty.user_id))) or 0,
        "offerings": len(classes),
        "unscheduled": sum(1 for c in classes if not c["scheduled"]),
        "full_classes": sum(1 for c in classes if c["status"] == "FULL"),
        "total_capacity": sum(c["capacity"] for c in classes),
        "total_enrolled": sum(c["enrolled_count"] for c in classes),
        "unmet_demand": demand_report(db)["total_unmet"],
        "hard_clashes": len(clashes["hard_clashes"]) + len(clashes["student_clashes"]),
        "no_room": len(clashes["no_room"]),
    }


# --------------------------------------------------------------------------- #
# Rooms
# --------------------------------------------------------------------------- #
def list_rooms(db: Session) -> List[Room]:
    return list(db.scalars(select(Room).order_by(Room.kind, Room.name)))


def create_room(db: Session, name: str, kind: str, capacity: int) -> Room:
    room = Room(name=name, kind=RoomKind(kind), capacity=capacity)
    db.add(room)
    _commit_unique(db, "A room with that name already exists.")
    room_service.assign_rooms(db)
    db.commit()
    return room


def delete_room(db: Session, room_id: int) -> None:
    room = db.get(Room, room_id)
    if room is None:
        raise NotFoundError("Room not found")
    db.delete(room)
    db.flush()
    room_service.assign_rooms(db)
    db.commit()
