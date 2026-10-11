"""Student-side registration workflow: credits -> subjects -> offering (faculty + slots) -> FIFO join request.

An offering is a complete unit (theory slot + its own lab slot), so one request covers both. A student can never
hold two offerings whose periods overlap: such requests are refused and the message says which parts clash
(theory/theory, theory/lab or lab/lab) and when. A subject that has only one faculty is requested automatically
the moment the student picks it, because there is nothing left to choose.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.algorithms.backtracking_graph_coloring import intervals_overlap
from app.core.config import settings as app_settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.models import (
    ClassSection,
    ClassStatus,
    JoinRequest,
    NotificationType,
    Registration,
    RegistrationPhase,
    RegistrationSettings,
    RegistrationStatus,
    RequestStatus,
    Student,
    Subject,
)
from app.models.enums import REASON_CLASS_CLOSED, REASON_CLASS_FULL
from app.services import allocation_service, capacity_service, notification_service, slot_service


# --------------------------------------------------------------------------- #
# Settings / lookups
# --------------------------------------------------------------------------- #
def get_registration_settings(db: Session) -> RegistrationSettings:
    row = db.get(RegistrationSettings, 1)
    if row is None:
        row = RegistrationSettings(
            id=1,
            phase=RegistrationPhase.OPEN,
            min_credits=app_settings.DEFAULT_MIN_CREDITS,
            max_credits=app_settings.DEFAULT_MAX_CREDITS,
        )
        db.add(row)
        db.flush()
    return row


def require_registration_open(db: Session) -> RegistrationSettings:
    s = get_registration_settings(db)
    if s.phase != RegistrationPhase.OPEN:
        raise ConflictError(
            "The registration period is closed. Please wait for the administration to reopen it.",
            code="REGISTRATION_CLOSED",
        )
    return s


def get_student(db: Session, user_id: int) -> Student:
    st = db.get(Student, user_id)
    if st is None:
        raise NotFoundError("Student profile not found")
    return st


def allowed_credit_range(db: Session, student: Student) -> tuple[int, int]:
    s = get_registration_settings(db)
    return s.min_credits, min(s.max_credits, student.max_credits)


def committed_credits(db: Session, student_id: int) -> int:
    """Credits of everything the student has selected (theory + lab credits)."""
    return db.scalar(
        select(func.coalesce(func.sum(Subject.credits + Subject.lab_credits), 0))
        .join(Registration, Registration.subject_id == Subject.id)
        .where(Registration.student_id == student_id)
    ) or 0


# --------------------------------------------------------------------------- #
# Credits & subjects
# --------------------------------------------------------------------------- #
def profile(db: Session, user_id: int) -> Dict[str, Any]:
    st = get_student(db, user_id)
    lo, hi = allowed_credit_range(db, st)
    s = get_registration_settings(db)
    return {
        "user_id": st.user_id,
        "name": st.user.name,
        "email": st.user.email,
        "roll_number": st.roll_number,
        "selected_credits": st.selected_credits,
        "min_credits": lo,
        "max_credits": hi,
        "committed_credits": committed_credits(db, st.user_id),
        "registration_open": s.phase == RegistrationPhase.OPEN,
    }


def set_credits(db: Session, user_id: int, credits: int) -> Dict[str, Any]:
    require_registration_open(db)
    st = get_student(db, user_id)
    lo, hi = allowed_credit_range(db, st)
    if not lo <= credits <= hi:
        raise ValidationFailed(f"Credits must be between {lo} and {hi}.", code="CREDITS_OUT_OF_RANGE")
    used = committed_credits(db, user_id)
    if credits < used:
        raise ValidationFailed(
            f"You have already chosen subjects worth {used} credits; "
            "drop a subject or choose a higher credit load.",
            code="CREDITS_BELOW_SELECTED",
        )
    st.selected_credits = credits
    db.commit()
    return profile(db, user_id)


def _scheduled_classes_by_subject(db: Session) -> Dict[int, List[ClassSection]]:
    out: Dict[int, List[ClassSection]] = {}
    for c in db.scalars(select(ClassSection).where(ClassSection.theory_slot_id.is_not(None)).order_by(ClassSection.id)):
        out.setdefault(c.subject_id, []).append(c)
    return out


def subject_clashes(
    subject_id: int, regs: Dict[int, Registration],
    scheduled: Dict[int, List[ClassSection]], cache: slot_service.IntervalCache,
) -> List[Dict[str, Any]]:
    """Subjects the student already picked that this subject can never be combined with.

    Two subjects are in unavoidable clash when no faculty option of one fits beside any option of the other. For a
    subject the student already holds a class in, only that class counts; for one still waiting for a faculty choice
    every scheduled option counts. (If nothing is scheduled yet there is nothing to compare.)
    """
    mine = scheduled.get(subject_id, [])
    if not mine:
        return []
    blocked: List[Dict[str, Any]] = []
    for other_id, reg in regs.items():
        if other_id == subject_id:
            continue
        theirs = [reg.class_section] if reg.class_id and reg.class_section else scheduled.get(other_id, [])
        if not theirs:
            continue
        if any(
            not intervals_overlap(slot_service.class_intervals(a, cache), slot_service.class_intervals(b, cache))
            for a in mine for b in theirs
        ):
            continue  # at least one combination works
        a, b = mine[0], theirs[0]
        pc = slot_service.part_clashes(slot_service.class_parts(a), slot_service.class_parts(b), cache)[0]
        msg = pc.sentence(a.subject.code, b.subject.code)
        if len(mine) > 1 or len(theirs) > 1:
            msg += " Every faculty option of these two subjects overlaps in this way."
        blocked.append({"subject_id": other_id, "code": b.subject.code, "name": b.subject.name, "message": msg})
    return blocked


def list_subjects(db: Session, user_id: int) -> List[Dict[str, Any]]:
    regs = {r.subject_id: r for r in db.scalars(select(Registration).where(Registration.student_id == user_id))}
    open_classes: Dict[int, int] = dict(
        db.execute(
            select(ClassSection.subject_id, func.count(ClassSection.id))
            .where(
                ClassSection.status == ClassStatus.OPEN,
                ClassSection.enrolled_count < ClassSection.capacity,
                ClassSection.theory_slot_id.is_not(None),
            )
            .group_by(ClassSection.subject_id)
        ).all()
    )
    total_classes: Dict[int, int] = dict(
        db.execute(select(ClassSection.subject_id, func.count(ClassSection.id)).group_by(ClassSection.subject_id)).all()
    )
    scheduled = _scheduled_classes_by_subject(db)
    cache = slot_service.slot_intervals(db)
    out = []
    for s in db.scalars(select(Subject).order_by(Subject.code)):
        r = regs.get(s.id)
        out.append(
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "credits": s.credits,
                "lab_credits": s.lab_credits,
                "total_credits": s.total_credits,
                "has_lab": s.has_lab,
                "selected": r is not None,
                "registration_status": r.status.value if r else None,
                "class_id": r.class_id if r else None,
                "classes_total": total_classes.get(s.id, 0),
                "classes_available": open_classes.get(s.id, 0),
                "clashes_with": [] if r else subject_clashes(s.id, regs, scheduled, cache),
            }
        )
    return out


def select_subject(db: Session, user_id: int, subject_id: int) -> Dict[str, Any]:
    require_registration_open(db)
    st = get_student(db, user_id)
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError("Subject not found")
    if st.selected_credits is None:
        raise ValidationFailed("Choose your credit load before selecting subjects.", code="CREDITS_NOT_SET")
    if _registration(db, user_id, subject_id):
        raise ConflictError("You have already registered for this subject.", code="ALREADY_REGISTERED")
    regs = {r.subject_id: r for r in db.scalars(select(Registration).where(Registration.student_id == user_id))}
    blocked = subject_clashes(subject_id, regs, _scheduled_classes_by_subject(db), slot_service.slot_intervals(db))
    if blocked:
        raise ConflictError(
            f"{subject.code} cannot be added: it is at the same time as {blocked[0]['code']}, which you already "
            f"picked. {blocked[0]['message']}",
            code="SUBJECT_CLASH",
        )
    used = committed_credits(db, user_id)
    if used + subject.total_credits > st.selected_credits:
        raise ValidationFailed(
            f"Adding {subject.code} ({subject.total_credits} credits) would exceed your chosen load of "
            f"{st.selected_credits} credits (currently {used}).",
            code="CREDIT_LIMIT_EXCEEDED",
        )
    reg = Registration(student_id=user_id, subject_id=subject_id, status=RegistrationStatus.SELECTED)
    db.add(reg)
    try:
        db.flush()
    except IntegrityError:  # concurrent double-submit hit the unique constraint
        db.rollback()
        raise ConflictError("You have already registered for this subject.", code="ALREADY_REGISTERED")
    capacity_service.raise_no_faculty_alert_if_needed(db, subject)
    db.commit()
    return _after_select(db, user_id, subject, reg)


def _after_select(db: Session, user_id: int, subject: Subject, reg: Registration) -> Dict[str, Any]:
    """A subject with a single faculty needs no further choice: send the request straight away."""
    result: Dict[str, Any] = {
        "subject_id": subject.id, "status": reg.status.value, "queued": False, "queue_position": None,
        "message": f"{subject.code} added. Choose a faculty to finish.",
    }
    classes = list(db.scalars(select(ClassSection).where(ClassSection.subject_id == subject.id)))
    if len(classes) != 1:
        return result
    cls = classes[0]
    if not cls.is_scheduled:
        result["message"] = f"{subject.code} added. Its timetable slot has not been set yet."
        return result
    if cls.is_open:
        try:
            out = submit_request(db, user_id, cls.id)
        except ConflictError as e:
            result["message"] = f"{subject.code} added, but the request could not be sent: {e.message}"
            return result
        if out.outcome == "QUEUED":
            result.update(
                status=RegistrationStatus.REQUESTED.value, queued=True, queue_position=out.queue_position,
                message=f"{subject.code} added. It has only one faculty, so your request was sent to "
                        f"{cls.faculty.user.name} automatically (queue position {out.queue_position}).",
            )
            return result
    what = "closed" if cls.status == ClassStatus.CLOSED else "full"
    result["message"] = (
        f"{subject.code} added, but its only class is {what} right now. "
        "You will be put in the queue automatically if a seat opens up."
    )
    return result


def deselect_subject(db: Session, user_id: int, subject_id: int) -> None:
    require_registration_open(db)
    reg = _registration(db, user_id, subject_id)
    if reg is None:
        raise NotFoundError("You have not selected this subject.")
    if reg.status == RegistrationStatus.ENROLLED:
        raise ConflictError(
            "You are already enrolled in a class for this subject; contact the administration to drop it.",
            code="ALREADY_ENROLLED",
        )
    if reg.status == RegistrationStatus.REQUESTED:
        pending = db.scalar(
            select(JoinRequest).where(
                JoinRequest.student_id == user_id,
                JoinRequest.subject_id == subject_id,
                JoinRequest.status == RequestStatus.PENDING,
            )
        )
        if pending:
            capacity_service.get_class(db, pending.class_id, lock=True)  # serialise with faculty actions
            db.refresh(pending)
            if pending.status == RequestStatus.PENDING:
                _cancel(pending)
    # Dropping a subject also clears its request history, so the Request Status page never shows leftovers
    # (for example a "choose another faculty" button for a subject the student no longer holds).
    for old in db.scalars(select(JoinRequest).where(JoinRequest.student_id == user_id, JoinRequest.subject_id == subject_id)):
        if old.status != RequestStatus.ACCEPTED:
            db.delete(old)
    db.delete(reg)
    db.commit()


def _registration(db: Session, user_id: int, subject_id: int) -> Optional[Registration]:
    return db.scalar(
        select(Registration).where(Registration.student_id == user_id, Registration.subject_id == subject_id)
    )


# --------------------------------------------------------------------------- #
# Slot clashes
# --------------------------------------------------------------------------- #
def clashing_classes(
    db: Session, student_id: int, cls: ClassSection, cache: Optional[slot_service.IntervalCache] = None
) -> List[ClassSection]:
    """The student's enrolled/requested offerings (of *other* subjects) whose periods overlap this offering's."""
    cache = cache if cache is not None else slot_service.slot_intervals(db)
    mine = slot_service.class_intervals(cls, cache)
    if not mine:
        return []
    q = (
        select(ClassSection)
        .join(Registration, Registration.class_id == ClassSection.id)
        .where(
            Registration.student_id == student_id,
            Registration.status.in_([RegistrationStatus.ENROLLED, RegistrationStatus.REQUESTED]),
            ClassSection.subject_id != cls.subject_id,
        )
    )
    return [c for c in db.scalars(q) if intervals_overlap(mine, slot_service.class_intervals(c, cache))]


def clash_messages(cls: ClassSection, held: List[ClassSection], cache: slot_service.IntervalCache) -> List[str]:
    """One plain sentence per held class, naming the clashing parts (theory/lab) and the time."""
    out = []
    for h in held:
        pcs = slot_service.part_clashes(slot_service.class_parts(cls), slot_service.class_parts(h), cache)
        if pcs:
            out.append(pcs[0].sentence(cls.subject.code, h.subject.code).rstrip(".") + " (a class you already have).")
    return out


def _offering_view(db: Session, c: ClassSection, cache, student_id: Optional[int], queue_len: int = 0) -> Dict[str, Any]:
    clash = clashing_classes(db, student_id, c, cache) if student_id is not None else []
    return {
        "class_id": c.id,
        "subject_id": c.subject_id,
        "subject_code": c.subject.code,
        "subject_name": c.subject.name,
        "has_lab": c.subject.has_lab,
        "faculty_id": c.faculty_id,
        "faculty_name": c.faculty.user.name,
        "theory_slot": c.theory_slot.name if c.theory_slot else None,
        "lab_slot": c.lab_slot.name if c.lab_slot else None,
        "theory_times": slot_service.period_text(c.theory_slot),
        "lab_times": slot_service.period_text(c.lab_slot),
        "room": c.room.name if c.room else None,
        "lab_room": c.lab_room.name if c.lab_room else None,
        "scheduled": c.is_scheduled,
        "capacity": c.capacity,
        "enrolled_count": c.enrolled_count,
        "remaining": c.remaining,
        "status": c.status.value,
        "queue_length": queue_len,
        "available": c.is_open and c.is_scheduled and not clash,
        "clash_with": clash_messages(c, clash, cache),
    }


# --------------------------------------------------------------------------- #
# Faculty / offering options (Greedy Faculty Allocation assists the student here)
# --------------------------------------------------------------------------- #
def class_options(
    db: Session, user_id: int, subject_id: int, preferred_class_id: Optional[int] = None
) -> Dict[str, Any]:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError("Subject not found")
    if _registration(db, user_id, subject_id) is None:
        raise ValidationFailed(
            "You are not registered for this subject (it may have been dropped). Select it again on the Subjects page.",
            code="SUBJECT_NOT_SELECTED",
        )
    classes = list(
        db.scalars(select(ClassSection).where(ClassSection.subject_id == subject_id).order_by(ClassSection.id))
    )
    result = allocation_service.greedy_pick(db, subject_id, student_id=user_id, preferred_class_id=preferred_class_id)
    candidates = {sc.candidate.class_id: sc.candidate for sc in result.considered}
    my_requests = {
        r.class_id: r
        for r in db.scalars(
            select(JoinRequest).where(
                JoinRequest.student_id == user_id,
                JoinRequest.subject_id == subject_id,
                JoinRequest.status.in_([RequestStatus.PENDING, RequestStatus.ACCEPTED]),
            )
        )
    }
    cache = slot_service.slot_intervals(db)
    options = []
    for c in classes:
        mine = my_requests.get(c.id)
        view = _offering_view(db, c, cache, user_id, candidates[c.id].queue_length)
        view["recommended"] = bool(result.selected and result.selected.class_id == c.id)
        view["my_request_status"] = mine.status.value if mine else None
        options.append(view)
    return {
        "subject": {
            "id": subject.id, "code": subject.code, "name": subject.name, "credits": subject.credits,
            "lab_credits": subject.lab_credits, "has_lab": subject.has_lab,
        },
        "options": options,
        "any_available": any(o["available"] for o in options),
    }


def student_offerings(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Every scheduled offering with its slots and whether it clashes with what the student already holds.
    Grouping by slot (client side) shows which subjects are alternatives in the same slot."""
    get_student(db, user_id)
    cache = slot_service.slot_intervals(db)
    regs = {r.subject_id: r for r in db.scalars(select(Registration).where(Registration.student_id == user_id))}
    out = []
    for c in db.scalars(
        select(ClassSection).where(ClassSection.theory_slot_id.is_not(None)).order_by(ClassSection.subject_id, ClassSection.id)
    ):
        view = _offering_view(db, c, cache, user_id)
        r = regs.get(c.subject_id)
        view["my_status"] = r.status.value if r else None
        view["mine"] = bool(r and r.class_id == c.id)
        out.append(view)
    return out


# --------------------------------------------------------------------------- #
# Join requests (FIFO enqueue)
# --------------------------------------------------------------------------- #
@dataclass
class SubmitOutcome:
    outcome: str  # QUEUED | REJECTED_FULL
    request: JoinRequest
    message: str
    queue_position: Optional[int] = None
    suggestion: Optional[Dict[str, Any]] = None


def queue_position(db: Session, req: JoinRequest) -> Optional[int]:
    """1-based position of a pending request in its class queue (1 = next to be served)."""
    if req.status != RequestStatus.PENDING or req.queue_seq is None:
        return None
    ahead = db.scalar(
        select(func.count(JoinRequest.id)).where(
            JoinRequest.class_id == req.class_id,
            JoinRequest.status == RequestStatus.PENDING,
            JoinRequest.queue_seq < req.queue_seq,
        )
    )
    return (ahead or 0) + 1


def _enqueue(db: Session, cls: ClassSection, student_id: int) -> JoinRequest:
    """Enqueue at the rear. O(1): the class row is locked and its sequence counter advanced."""
    seq = cls.next_queue_seq
    cls.next_queue_seq = seq + 1
    req = JoinRequest(
        student_id=student_id,
        class_id=cls.id,
        subject_id=cls.subject_id,
        queue_seq=seq,
        status=RequestStatus.PENDING,
    )
    db.add(req)
    return req


def submit_request(db: Session, user_id: int, class_id: int) -> SubmitOutcome:
    require_registration_open(db)
    student = get_student(db, user_id)
    target = capacity_service.get_class(db, class_id)
    reg = _registration(db, user_id, target.subject_id)
    if reg is None:
        raise ValidationFailed("Select this subject before requesting a class.", code="SUBJECT_NOT_SELECTED")
    if reg.status == RegistrationStatus.ENROLLED:
        raise ConflictError("You are already enrolled in this subject.", code="ALREADY_ENROLLED")
    if reg.status == RegistrationStatus.REQUESTED:
        raise ConflictError(
            "You already have a pending request for this subject. Cancel it before choosing another faculty.",
            code="REQUEST_ALREADY_PENDING",
        )
    if not target.is_scheduled:
        raise ConflictError("This class has no timetable slot yet, so it cannot be requested.", code="NOT_SCHEDULED")
    cache = slot_service.slot_intervals(db)
    clash = clashing_classes(db, user_id, target, cache)
    if clash:
        raise ConflictError(
            f"You cannot request {target.subject.code} with {target.faculty.user.name}. "
            + clash_messages(target, clash, cache)[0],
            code="SLOT_CLASH",
        )

    cls = capacity_service.get_class(db, class_id, lock=True)  # row lock => deterministic queue order
    if not cls.is_open:
        return _turned_away(db, student, cls)

    try:
        req = _enqueue(db, cls, user_id)
        reg.status = RegistrationStatus.REQUESTED
        reg.class_id = cls.id
        notification_service.notify(
            db,
            cls.faculty_id,
            NotificationType.NEW_JOIN_REQUEST,
            f"{student.user.name} ({student.roll_number}) requested to join {cls.subject.code}.",
        )
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("You already have an active request for this subject.", code="REQUEST_ALREADY_PENDING")
    db.commit()
    pos = queue_position(db, req)
    return SubmitOutcome("QUEUED", req, f"Request sent to {cls.faculty.user.name}. Queue position: {pos}.", pos)


def _turned_away(db: Session, student: Student, cls: ClassSection) -> SubmitOutcome:
    reason = REASON_CLASS_CLOSED if cls.status == ClassStatus.CLOSED else REASON_CLASS_FULL
    rejected = JoinRequest(
        student_id=student.user_id,
        class_id=cls.id,
        subject_id=cls.subject_id,
        queue_seq=None,  # never entered the queue
        status=RequestStatus.REJECTED,
        decision_reason=reason,
        decided_at=capacity_service.utcnow(),
    )
    db.add(rejected)
    alt = allocation_service.greedy_pick(db, cls.subject_id, student_id=student.user_id, exclude_class_ids=[cls.id])
    what = "closed" if reason == REASON_CLASS_CLOSED else "full"
    msg = f"{capacity_service.class_label(cls)} is {what}."
    suggestion = None
    if alt.selected:
        suggestion = _suggestion(alt.selected)
        msg += f" Suggested alternative: {alt.selected.faculty_name} ({alt.selected.remaining_capacity} seat(s) left)."
    else:
        msg += " No other faculty currently has seats; the administration has been alerted."
        capacity_service.raise_no_faculty_alert_if_needed(db, cls.subject)
    notification_service.notify(db, student.user_id, NotificationType.CLASS_FULL, msg)
    db.commit()
    return SubmitOutcome("REJECTED_FULL", rejected, msg, None, suggestion)


def _suggestion(c) -> Dict[str, Any]:
    return {
        "class_id": c.class_id,
        "faculty_id": c.faculty_id,
        "faculty_name": c.faculty_name,
        "remaining": c.remaining_capacity,
    }


def _cancel(req: JoinRequest) -> None:
    req.status = RequestStatus.CANCELLED
    req.decision_reason = "CANCELLED_BY_STUDENT"
    req.decided_at = capacity_service.utcnow()


def cancel_request(db: Session, user_id: int, request_id: int) -> JoinRequest:
    req = db.get(JoinRequest, request_id)
    if req is None or req.student_id != user_id:
        raise NotFoundError("Request not found")
    capacity_service.get_class(db, req.class_id, lock=True)  # serialise with faculty actions
    db.refresh(req)
    if req.status != RequestStatus.PENDING:
        raise ConflictError("Only pending requests can be cancelled.", code="NOT_PENDING")
    _cancel(req)
    reg = _registration(db, user_id, req.subject_id)
    if reg and reg.status == RegistrationStatus.REQUESTED:
        reg.status = RegistrationStatus.SELECTED
        reg.class_id = None
    db.commit()
    return req


def sync_waiting_students(db: Session, subject_id: int) -> List[int]:
    """Seats opened up (capacity raised or class reopened): put students who picked a single-faculty subject while
    its class was full or closed into the queue automatically, oldest first. Returns the student ids queued.
    The caller commits. Subjects with several faculty are left alone - the student still has a choice to make."""
    if get_registration_settings(db).phase != RegistrationPhase.OPEN:
        return []
    classes = list(db.scalars(select(ClassSection).where(ClassSection.subject_id == subject_id)))
    if len(classes) != 1 or not classes[0].is_scheduled:
        return []
    cls = capacity_service.get_class(db, classes[0].id, lock=True)
    waiting = list(
        db.scalars(
            select(Registration)
            .where(Registration.subject_id == subject_id, Registration.status == RegistrationStatus.SELECTED)
            .order_by(Registration.created_at, Registration.id)
        )
    )
    cache = slot_service.slot_intervals(db)
    queued: List[int] = []
    for reg in waiting:
        db.flush()
        pending = db.scalar(
            select(func.count(JoinRequest.id)).where(
                JoinRequest.class_id == cls.id, JoinRequest.status == RequestStatus.PENDING
            )
        ) or 0
        if not cls.is_open or pending >= cls.remaining:
            break
        if clashing_classes(db, reg.student_id, cls, cache):
            continue
        req = _enqueue(db, cls, reg.student_id)
        reg.status = RegistrationStatus.REQUESTED
        reg.class_id = cls.id
        db.flush()
        pos = queue_position(db, req)
        notification_service.notify(
            db, reg.student_id, NotificationType.CAPACITY_INCREASED,
            f"A seat is available in {capacity_service.class_label(cls)}, so your request was sent automatically "
            f"(queue position {pos}).",
        )
        notification_service.notify(
            db, cls.faculty_id, NotificationType.NEW_JOIN_REQUEST,
            f"{reg.student.user.name} ({reg.student.roll_number}) is waiting to join {cls.subject.code}.",
        )
        queued.append(reg.student_id)
    return queued


def list_requests(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """One row per subject the student currently holds: the latest request, or 'not requested yet'.

    Requests for subjects the student has dropped are never shown, and old rejected/cancelled attempts are replaced
    by the newest one, so every row describes something that is true right now.
    """
    regs = {r.subject_id: r for r in db.scalars(select(Registration).where(Registration.student_id == user_id))}
    latest: Dict[int, JoinRequest] = {}
    for r in db.scalars(
        select(JoinRequest)
        .where(JoinRequest.student_id == user_id)
        .order_by(JoinRequest.requested_at.desc(), JoinRequest.id.desc())
    ):
        if r.subject_id in regs and r.subject_id not in latest:
            latest[r.subject_id] = r
    open_now = get_registration_settings(db).phase == RegistrationPhase.OPEN
    counts = dict(db.execute(select(ClassSection.subject_id, func.count(ClassSection.id)).group_by(ClassSection.subject_id)).all())
    rows: List[Dict[str, Any]] = []
    for sid, reg in regs.items():
        req = latest.get(sid)
        if req is not None:
            cs = req.class_section
            rows.append(
                {
                    "id": req.id,
                    "class_id": req.class_id,
                    "subject_id": sid,
                    "subject_code": req.subject.code,
                    "subject_name": req.subject.name,
                    "faculty_name": cs.faculty.user.name,
                    "theory_slot": cs.theory_slot.name if cs.theory_slot else None,
                    "lab_slot": cs.lab_slot.name if cs.lab_slot else None,
                    "status": req.status.value,
                    "decision_reason": req.decision_reason,
                    "requested_at": req.requested_at,
                    "decided_at": req.decided_at,
                    "queue_position": queue_position(db, req),
                    "can_choose_another": open_now and reg.status == RegistrationStatus.SELECTED
                    and req.status in (RequestStatus.REJECTED, RequestStatus.CANCELLED),
                    "note": None,
                }
            )
        elif reg.status == RegistrationStatus.SELECTED:
            sub = reg.subject
            if counts.get(sid, 0) == 1:
                note = "The only class for this subject is full or closed. You will be queued automatically if a seat opens up."
            else:
                note = "You have not sent a request yet. Choose a faculty to continue."
            rows.append(
                {
                    "id": None, "class_id": None, "subject_id": sid, "subject_code": sub.code,
                    "subject_name": sub.name, "faculty_name": None, "theory_slot": None, "lab_slot": None,
                    "status": "NOT_REQUESTED", "decision_reason": None, "requested_at": reg.created_at,
                    "decided_at": None, "queue_position": None,
                    "can_choose_another": open_now and counts.get(sid, 0) > 1, "note": note,
                }
            )
    rows.sort(key=lambda r: r["requested_at"].replace(tzinfo=None), reverse=True)
    return rows
