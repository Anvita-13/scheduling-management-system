"""Glue between the database and the Greedy Faculty Allocation algorithm."""
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.algorithms.backtracking_graph_coloring import intervals_overlap
from app.algorithms.greedy_faculty_allocation import (
    AllocationResult,
    Candidate,
    GreedyConfig,
    Preference,
    select_best,
)
from app.models import ClassSection, JoinRequest, Registration, RegistrationStatus, RequestStatus
from app.services import slot_service

# The greedy rule is configured here (see algorithms/greedy_faculty_allocation.py for the docs).
GREEDY_CONFIG = GreedyConfig()


def build_candidates(
    db: Session, subject_id: int, student_id: Optional[int] = None, exclude_class_ids: Iterable[int] = ()
) -> List[Candidate]:
    """Offerings of a subject as candidates. An offering is only *available* if it is scheduled, open, has a
    free seat and (for a given student) does not overlap in time with anything the student already holds."""
    excluded = set(exclude_class_ids)
    db.flush()  # autoflush is off: include this transaction's pending changes in the counts below
    classes = list(
        db.scalars(select(ClassSection).where(ClassSection.subject_id == subject_id).order_by(ClassSection.id))
    )
    queue_len: Dict[int, int] = dict(
        db.execute(
            select(JoinRequest.class_id, func.count(JoinRequest.id))
            .where(JoinRequest.subject_id == subject_id, JoinRequest.status == RequestStatus.PENDING)
            .group_by(JoinRequest.class_id)
        ).all()
    )
    cache = slot_service.slot_intervals(db)
    held: List[List] = []
    if student_id is not None:
        for c in db.scalars(
            select(ClassSection)
            .join(Registration, Registration.class_id == ClassSection.id)
            .where(
                Registration.student_id == student_id,
                Registration.status.in_([RegistrationStatus.ENROLLED, RegistrationStatus.REQUESTED]),
                ClassSection.subject_id != subject_id,
            )
        ):
            held.append(slot_service.class_intervals(c, cache))
    out: List[Candidate] = []
    for c in classes:
        if c.id in excluded:
            continue
        mine = slot_service.class_intervals(c, cache)
        compatible = not any(intervals_overlap(mine, h) for h in held)
        out.append(
            Candidate(
                class_id=c.id,
                faculty_id=c.faculty_id,
                faculty_name=c.faculty.user.name,
                remaining_capacity=c.remaining,
                queue_length=queue_len.get(c.id, 0),
                is_open=c.is_open and c.is_scheduled and compatible,
                slot_compatible=compatible,
            )
        )
    return out


def greedy_pick(
    db: Session,
    subject_id: int,
    student_id: Optional[int] = None,
    preferred_class_id: Optional[int] = None,
    preferred_faculty_id: Optional[int] = None,
    exclude_class_ids: Iterable[int] = (),
) -> AllocationResult:
    candidates = build_candidates(db, subject_id, student_id, exclude_class_ids)
    return select_best(candidates, Preference(preferred_class_id, preferred_faculty_id), GREEDY_CONFIG)


def has_available_class(db: Session, subject_id: int) -> bool:
    return any(c.available for c in build_candidates(db, subject_id))
