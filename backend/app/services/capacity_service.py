"""Class capacity, class status transitions and the persistent FIFO queue plumbing.

Concurrency model
-----------------
Every operation that changes a class's seat count or its queue first takes a row lock on the
class (``SELECT ... FOR UPDATE``).  Seat consumption additionally uses a *conditional* UPDATE
(``enrolled_count = enrolled_count + 1 WHERE enrolled_count < capacity``) and the table has
``CHECK (enrolled_count <= capacity)``, so overbooking is impossible even if a caller forgets the lock.
"""
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.algorithms.fifo_queue import FifoQueue
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.models import (
    ClassSection,
    ClassStatus,
    JoinRequest,
    NotificationType,
    Registration,
    RegistrationStatus,
    RequestStatus,
    Subject,
)
from app.models.enums import REASON_CLASS_CLOSED, REASON_CLASS_FULL
from app.services import allocation_service, notification_service


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Loading / locking
# --------------------------------------------------------------------------- #
def get_class(db: Session, class_id: int, lock: bool = False) -> ClassSection:
    q = select(ClassSection).where(ClassSection.id == class_id)
    if lock:
        # populate_existing: after the lock is granted, overwrite any stale copy in the session.
        q = q.with_for_update().execution_options(populate_existing=True)
    cls = db.scalar(q)
    if cls is None:
        raise NotFoundError("Class not found")
    return cls


def class_label(cls: ClassSection) -> str:
    return f"{cls.subject.code} ({cls.faculty.user.name})"


# --------------------------------------------------------------------------- #
# FIFO queue persistence
# --------------------------------------------------------------------------- #
def pending_requests_in_order(db: Session, class_id: int) -> List[JoinRequest]:
    """Pending requests strictly in arrival order (queue_seq is assigned at enqueue under a row lock)."""
    db.flush()  # autoflush is off: make sure earlier status changes in this transaction are visible
    return list(
        db.scalars(
            select(JoinRequest)
            .where(JoinRequest.class_id == class_id, JoinRequest.status == RequestStatus.PENDING)
            .order_by(JoinRequest.queue_seq.asc())
        )
    )


def hydrate_queue(db: Session, class_id: int) -> "FifoQueue[JoinRequest]":
    """Rebuild the class's in-memory FIFO queue from the durable store."""
    return FifoQueue(pending_requests_in_order(db, class_id))


# --------------------------------------------------------------------------- #
# Request/registration state helpers
# --------------------------------------------------------------------------- #
def _registration_for(db: Session, student_id: int, subject_id: int) -> Registration | None:
    return db.scalar(
        select(Registration).where(
            Registration.student_id == student_id, Registration.subject_id == subject_id
        )
    )


def reject_request(db: Session, req: JoinRequest, reason: str) -> None:
    req.status = RequestStatus.REJECTED
    req.decision_reason = reason
    req.decided_at = utcnow()
    reg = _registration_for(db, req.student_id, req.subject_id)
    if reg and reg.status == RegistrationStatus.REQUESTED and reg.class_id == req.class_id:
        reg.status = RegistrationStatus.SELECTED
        reg.class_id = None


def raise_no_faculty_alert_if_needed(db: Session, subject: Subject, context: str = "") -> bool:
    """Admin alert when a subject has unmet demand and no class with a free seat left."""
    if allocation_service.has_available_class(db, subject.id):
        return False
    db.flush()
    waiting = len(
        db.scalars(
            select(Registration.id).where(
                Registration.subject_id == subject.id,
                Registration.status != RegistrationStatus.ENROLLED,
            )
        ).all()
    )
    if waiting == 0:
        return False
    extra = f" {context}" if context else ""
    notification_service.notify_admins(
        db,
        NotificationType.NO_FACULTY_AVAILABLE,
        f"No faculty is available for {subject.code} - {subject.name}: {waiting} student(s) are "
        f"waiting and every class is full or closed.{extra} Consider increasing capacity.",
        dedupe_key=f"no-faculty:{subject.id}",
    )
    return True


def reject_all_pending(db: Session, cls: ClassSection, reason: str) -> List[JoinRequest]:
    """Drain the class queue front-to-back, rejecting (and notifying) each waiting student in order."""
    queue = hydrate_queue(db, cls.id)
    rejected: List[JoinRequest] = []
    while not queue.is_empty():
        req = queue.dequeue()  # FIFO: earliest request is told first
        reject_request(db, req, reason)
        rejected.append(req)
        if reason == REASON_CLASS_FULL:
            msg = f"{class_label(cls)} is now full, so your join request could not be accepted."
            type_ = NotificationType.CLASS_FULL
        else:
            msg = f"{class_label(cls)} was closed, so your join request was cancelled."
            type_ = NotificationType.CLASS_CLOSED
        alt = allocation_service.greedy_pick(
            db, cls.subject_id, student_id=req.student_id, exclude_class_ids=[cls.id]
        )
        if alt.selected:
            msg += (
                f" Suggested alternative: {alt.selected.faculty_name} "
                f"({alt.selected.remaining_capacity} seat(s) left). Please choose another faculty."
            )
        else:
            msg += " No other faculty currently has seats; the administration has been alerted."
        notification_service.notify(db, req.student_id, type_, msg)
    return rejected


def mark_full_and_drain(db: Session, cls: ClassSection) -> None:
    """Called (inside the class lock) once the last seat is taken."""
    cls.status = ClassStatus.FULL
    rejected = reject_all_pending(db, cls, REASON_CLASS_FULL)
    msg = f"{class_label(cls)} is full ({cls.enrolled_count}/{cls.capacity}) and has been closed."
    notification_service.notify(db, cls.faculty_id, NotificationType.CLASS_CLOSED, msg)
    notification_service.notify_admins(db, NotificationType.CLASS_CLOSED, msg)
    raise_no_faculty_alert_if_needed(
        db, cls.subject, f"({len(rejected)} waiting request(s) were turned away)" if rejected else ""
    )


def consume_seat(db: Session, cls: ClassSection) -> None:
    """Atomically take one seat; raises if none is left (never lets enrolled_count exceed capacity)."""
    res = db.execute(
        update(ClassSection)
        .where(
            ClassSection.id == cls.id,
            ClassSection.status == ClassStatus.OPEN,
            ClassSection.enrolled_count < ClassSection.capacity,
        )
        .values(enrolled_count=ClassSection.enrolled_count + 1)
    )
    if res.rowcount != 1:
        raise ConflictError("The class has no free seat or is closed.", code="CLASS_FULL")
    db.refresh(cls)


# --------------------------------------------------------------------------- #
# Admin / faculty capacity operations
# --------------------------------------------------------------------------- #
def update_capacity(db: Session, class_id: int, new_capacity: int) -> ClassSection:
    cls = get_class(db, class_id, lock=True)
    if new_capacity < 0:
        raise ValidationFailed("Capacity cannot be negative.")
    if new_capacity < cls.enrolled_count:
        raise ConflictError(
            f"Capacity cannot be lower than the {cls.enrolled_count} student(s) already enrolled.",
            code="CAPACITY_BELOW_ENROLLED",
        )
    old = cls.capacity
    cls.capacity = new_capacity

    if new_capacity > old:
        if cls.status == ClassStatus.FULL:
            cls.status = ClassStatus.OPEN  # seats appeared; the class accepts requests again
        msg = (
            f"Capacity of {class_label(cls)} was increased from {old} to {new_capacity} "
            f"({cls.remaining} seat(s) free)."
        )
        notification_service.notify(db, cls.faculty_id, NotificationType.CAPACITY_INCREASED, msg)
        # Tell students who still have no seat for this subject that room has opened up.
        waiting = db.scalars(
            select(Registration.student_id).where(
                Registration.subject_id == cls.subject_id,
                Registration.status == RegistrationStatus.SELECTED,
            )
        ).all()
        for sid in waiting:
            notification_service.notify(
                db,
                sid,
                NotificationType.CAPACITY_INCREASED,
                f"Seats are now available for {cls.subject.code} with {cls.faculty.user.name}. "
                "You can send a join request.",
            )
    elif new_capacity == cls.enrolled_count and cls.status == ClassStatus.OPEN:
        mark_full_and_drain(db, cls)
    db.commit()
    return cls


def close_class(db: Session, class_id: int, by_faculty_id: int | None = None) -> ClassSection:
    """Manually close a class: no new requests; waiting students are rejected and told why."""
    cls = get_class(db, class_id, lock=True)
    if cls.status != ClassStatus.OPEN:
        raise ConflictError(f"Class is already {cls.status.value.lower()}.", code="ALREADY_CLOSED")
    cls.status = ClassStatus.CLOSED
    rejected = reject_all_pending(db, cls, REASON_CLASS_CLOSED)
    msg = f"{class_label(cls)} was closed with {cls.enrolled_count}/{cls.capacity} seat(s) filled."
    notification_service.notify_admins(db, NotificationType.CLASS_CLOSED, msg)
    if by_faculty_id is None:
        notification_service.notify(db, cls.faculty_id, NotificationType.CLASS_CLOSED, msg)
    raise_no_faculty_alert_if_needed(db, cls.subject)
    db.commit()
    return cls


def reopen_class(db: Session, class_id: int) -> ClassSection:
    cls = get_class(db, class_id, lock=True)
    if cls.status == ClassStatus.OPEN:
        raise ConflictError("Class is already open.", code="ALREADY_OPEN")
    if cls.remaining <= 0:
        raise ConflictError("The class has no free seats; increase its capacity first.", code="NO_SEATS")
    cls.status = ClassStatus.OPEN
    db.commit()
    return cls
