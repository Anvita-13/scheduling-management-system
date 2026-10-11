"""Faculty-side workflow: view own classes, process the FIFO queue from the front, close classes."""
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError
from app.models import (
    ClassSection,
    ClassStatus,
    JoinRequest,
    NotificationType,
    Registration,
    RegistrationStatus,
    RequestStatus,
)
from app.models.enums import REASON_FACULTY_DECLINED
from app.services import allocation_service, capacity_service, notification_service, slot_service


def owned_class(db: Session, faculty_id: int, class_id: int, lock: bool = False) -> ClassSection:
    """Load a class and make sure it belongs to this faculty member."""
    cls = capacity_service.get_class(db, class_id, lock=lock)
    if cls.faculty_id != faculty_id:
        raise ForbiddenError("This class belongs to another faculty member.")
    return cls


def _class_summary(db: Session, cls: ClassSection) -> Dict[str, Any]:
    pending = db.scalar(
        select(func.count(JoinRequest.id)).where(
            JoinRequest.class_id == cls.id, JoinRequest.status == RequestStatus.PENDING
        )
    )
    return {
        "id": cls.id,
        "subject_id": cls.subject_id,
        "subject_code": cls.subject.code,
        "subject_name": cls.subject.name,
        "credits": cls.subject.credits,
        "lab_credits": cls.subject.lab_credits,
        "theory_slot": cls.theory_slot.name if cls.theory_slot else None,
        "lab_slot": cls.lab_slot.name if cls.lab_slot else None,
        "theory_times": slot_service.period_text(cls.theory_slot),
        "lab_times": slot_service.period_text(cls.lab_slot),
        "room": cls.room.name if cls.room else None,
        "lab_room": cls.lab_room.name if cls.lab_room else None,
        "capacity": cls.capacity,
        "enrolled_count": cls.enrolled_count,
        "remaining": cls.remaining,
        "status": cls.status.value,
        "pending_requests": pending or 0,
    }


def list_classes(db: Session, faculty_id: int) -> List[Dict[str, Any]]:
    classes = db.scalars(
        select(ClassSection).where(ClassSection.faculty_id == faculty_id).order_by(ClassSection.id)
    )
    return [_class_summary(db, c) for c in classes]


def class_detail(db: Session, faculty_id: int, class_id: int) -> Dict[str, Any]:
    cls = owned_class(db, faculty_id, class_id)
    data = _class_summary(db, cls)
    queue = capacity_service.pending_requests_in_order(db, cls.id)
    data["queue"] = [
        {
            "request_id": r.id,
            "position": i,
            "queue_seq": r.queue_seq,
            "student_id": r.student_id,
            "student_name": r.student.user.name,
            "roll_number": r.student.roll_number,
            "requested_at": r.requested_at,
            "is_front": i == 1,
        }
        for i, r in enumerate(queue, start=1)
    ]
    data["accepted"] = accepted_students(db, faculty_id, class_id)
    return data


def accepted_students(db: Session, faculty_id: int, class_id: int) -> List[Dict[str, Any]]:
    owned_class(db, faculty_id, class_id)
    rows = db.scalars(
        select(JoinRequest)
        .where(JoinRequest.class_id == class_id, JoinRequest.status == RequestStatus.ACCEPTED)
        .order_by(JoinRequest.decided_at.asc(), JoinRequest.id.asc())
    )
    return [
        {
            "request_id": r.id,
            "student_id": r.student_id,
            "student_name": r.student.user.name,
            "roll_number": r.student.roll_number,
            "accepted_at": r.decided_at,
        }
        for r in rows
    ]


def dashboard(db: Session, faculty_id: int) -> Dict[str, Any]:
    classes = list_classes(db, faculty_id)
    return {
        "classes": len(classes),
        "pending_requests": sum(c["pending_requests"] for c in classes),
        "enrolled_students": sum(c["enrolled_count"] for c in classes),
        "total_capacity": sum(c["capacity"] for c in classes),
        "open_classes": sum(1 for c in classes if c["status"] == "OPEN"),
        "unread_notifications": notification_service.unread_count(db, faculty_id),
        "class_list": classes,
    }


# --------------------------------------------------------------------------- #
# FIFO processing
# --------------------------------------------------------------------------- #
def _check_front(db: Session, cls: ClassSection, expected_request_id: Optional[int]):
    queue = capacity_service.hydrate_queue(db, cls.id)
    if queue.is_empty():
        raise ConflictError("There are no pending requests in this class.", code="QUEUE_EMPTY")
    front = queue.peek()
    if expected_request_id is not None and front.id != expected_request_id:
        raise ConflictError(
            "Requests must be processed first-come-first-served; the front of the queue is a different request.",
            code="NOT_FRONT_OF_QUEUE",
        )
    return queue


def accept_next(
    db: Session, faculty_id: int, class_id: int, expected_request_id: Optional[int] = None
) -> JoinRequest:
    """Dequeue the front request and enrol that student, atomically with the seat count."""
    cls = owned_class(db, faculty_id, class_id, lock=True)
    if cls.status != ClassStatus.OPEN or cls.remaining <= 0:
        raise ConflictError("This class is full or closed and cannot accept students.", code="CLASS_FULL")
    queue = _check_front(db, cls, expected_request_id)
    req = queue.dequeue()  # FIFO: O(1) removal from the front

    capacity_service.consume_seat(db, cls)  # conditional UPDATE: never exceeds capacity
    req.status = RequestStatus.ACCEPTED
    req.decided_at = capacity_service.utcnow()
    reg = db.scalar(
        select(Registration).where(
            Registration.student_id == req.student_id, Registration.subject_id == req.subject_id
        )
    )
    if reg:
        reg.status = RegistrationStatus.ENROLLED
        reg.class_id = cls.id
    notification_service.notify(
        db,
        req.student_id,
        NotificationType.REQUEST_ACCEPTED,
        f"You were accepted into {capacity_service.class_label(cls)}.",
    )
    if cls.enrolled_count >= cls.capacity:
        capacity_service.mark_full_and_drain(db, cls)
    db.commit()
    return req


def reject_next(
    db: Session, faculty_id: int, class_id: int, expected_request_id: Optional[int] = None
) -> JoinRequest:
    """Decline the request at the front of the queue (still strictly in order)."""
    cls = owned_class(db, faculty_id, class_id, lock=True)
    queue = _check_front(db, cls, expected_request_id)
    req = queue.dequeue()
    capacity_service.reject_request(db, req, REASON_FACULTY_DECLINED)
    msg = f"Your request to join {capacity_service.class_label(cls)} was declined."
    alt = allocation_service.greedy_pick(
        db, cls.subject_id, student_id=req.student_id, exclude_class_ids=[cls.id]
    )
    if alt.selected:
        msg += f" You can try {alt.selected.faculty_name} ({alt.selected.remaining_capacity} seat(s) left)."
    notification_service.notify(db, req.student_id, NotificationType.REQUEST_REJECTED, msg)
    db.commit()
    return req


def close_class(db: Session, faculty_id: int, class_id: int) -> ClassSection:
    owned_class(db, faculty_id, class_id)
    return capacity_service.close_class(db, class_id, by_faculty_id=faculty_id)
