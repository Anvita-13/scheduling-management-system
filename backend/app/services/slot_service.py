"""Slots: the standard FFCS-style slot chart, time-overlap detection, validated placement of offerings.

A *slot* is a weekly package of periods (``A1+TA1`` = Mon 08:00, Wed 09:00, Fri 10:00). Two slots clash when any
of their periods overlap in time. An offering (ClassSection) owns a theory slot and - for theory+lab courses -
its own lab slot, and everything that checks "is this free?" goes through the helpers here.
"""
from dataclasses import dataclass
from datetime import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.algorithms.backtracking_graph_coloring import Interval, intervals_overlap
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.models import (
    ClassSection,
    Faculty,
    JoinRequest,
    RequestStatus,
    Slot,
    SlotKind,
    SlotPeriod,
    Subject,
    User,
)
from app.models.enums import DAY_ORDER

IntervalCache = Dict[int, List[Interval]]


# --------------------------------------------------------------------------- #
# Intervals
# --------------------------------------------------------------------------- #
def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def slot_intervals(db: Session) -> IntervalCache:
    """slot id -> [(day index, start minute, end minute)] for every slot."""
    cache: IntervalCache = {}
    for sid, day, start, end in db.execute(
        select(SlotPeriod.slot_id, SlotPeriod.day, SlotPeriod.start_time, SlotPeriod.end_time).order_by(SlotPeriod.id)
    ):
        cache.setdefault(sid, []).append((DAY_ORDER.index(day), _minutes(start), _minutes(end)))
    return cache


def class_intervals(cls: ClassSection, cache: IntervalCache) -> List[Interval]:
    out: List[Interval] = []
    for sid in (cls.theory_slot_id, cls.lab_slot_id):
        if sid is not None:
            out.extend(cache.get(sid, []))
    return out


def slot_label(slot: Optional[Slot]) -> Optional[str]:
    return slot.name if slot else None


def period_text(slot: Optional[Slot]) -> str:
    """'Mon 08:00, Wed 09:00, Fri 10:00' for display."""
    if slot is None:
        return ""
    ordered = sorted(slot.periods, key=lambda p: (DAY_ORDER.index(p.day), p.start_time))
    return ", ".join(f"{p.day} {p.start_time.strftime('%H:%M')}" for p in ordered)


def describe_period(iv: Interval) -> str:
    d, s, e = iv
    return f"{DAY_ORDER[d]} {s // 60:02d}:{s % 60:02d}-{e // 60:02d}:{e % 60:02d}"


# --------------------------------------------------------------------------- #
# Saying *which* parts clash (theory/theory, theory/lab or lab/lab) and when
# --------------------------------------------------------------------------- #
@dataclass
class PartClash:
    a_kind: str  # "theory" | "lab"
    a_slot: str
    b_kind: str
    b_slot: str
    when: str    # e.g. "Mon 14:00-14:50"

    @property
    def title(self) -> str:
        if self.a_kind == self.b_kind:
            return f"{self.a_kind.capitalize()}/{self.b_kind} clash"
        return "Theory/lab clash"

    def sentence(self, a_name: str, b_name: str) -> str:
        """e.g. 'Theory/lab clash on Mon 14:00-14:50: BCSE202L's lab slot L31+L32 overlaps BMAT101L's theory slot D1.'"""
        return (
            f"{self.title} on {self.when}: {a_name}'s {self.a_kind} slot {self.a_slot} "
            f"overlaps {b_name}'s {self.b_kind} slot {self.b_slot}."
        )


Part = Tuple[str, Slot]  # ("theory" | "lab", the slot)


def class_parts(cls: ClassSection) -> List[Part]:
    parts: List[Part] = []
    if cls.theory_slot is not None:
        parts.append(("theory", cls.theory_slot))
    if cls.lab_slot is not None:
        parts.append(("lab", cls.lab_slot))
    return parts


def overlap_window(a: Iterable[Interval], b: Iterable[Interval]) -> Optional[str]:
    for d1, s1, e1 in a:
        for d2, s2, e2 in b:
            if d1 == d2 and s1 < e2 and s2 < e1:
                lo, hi = max(s1, s2), min(e1, e2)
                return f"{DAY_ORDER[d1]} {lo // 60:02d}:{lo % 60:02d}-{hi // 60:02d}:{hi % 60:02d}"
    return None


def part_clashes(parts_a: Sequence[Part], parts_b: Sequence[Part], cache: "IntervalCache") -> List[PartClash]:
    """Every pair of parts (a theory or lab slot of each side) that overlaps in time."""
    out: List[PartClash] = []
    for a_kind, a_slot in parts_a:
        for b_kind, b_slot in parts_b:
            when = overlap_window(cache.get(a_slot.id, []), cache.get(b_slot.id, []))
            if when:
                out.append(PartClash(a_kind, a_slot.name, b_kind, b_slot.name, when))
    return out


# --------------------------------------------------------------------------- #
# Standard slot chart (VIT/FFCS-like)
# --------------------------------------------------------------------------- #
# Morning grid (5 theory periods per day); the afternoon grid is identical with suffix 2.
THEORY_GRID = {
    "Mon": ["A", "F", "D", "TB", "TG"],
    "Tue": ["B", "G", "E", "TC", "TAA"],
    "Wed": ["C", "A", "F", "TD", "TBB"],
    "Thu": ["D", "B", "G", "TE", "TCC"],
    "Fri": ["E", "C", "TA", "TF", "TDD"],
}
THEORY_START = {1: [8, 9, 10, 11, 12], 2: [14, 15, 16, 17, 18]}  # 50-minute periods
LAB_PERIODS = {  # six 50-minute lab periods per half-day, grouped in pairs (L1+L2, L3+L4, ...)
    1: [(8, 0, 8, 50), (8, 51, 9, 40), (9, 51, 10, 40), (10, 41, 11, 30), (11, 40, 12, 30), (12, 31, 13, 20)],
    2: [(14, 0, 14, 50), (14, 51, 15, 40), (15, 51, 16, 40), (16, 41, 17, 30), (17, 40, 18, 30), (18, 31, 19, 20)],
}
DAYS5 = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def standard_chart() -> List[Dict[str, Any]]:
    """The slot packages as plain dicts: name, kind, credits, periods [(day, start, end)]."""
    atoms: Dict[str, List[Tuple[str, time, time]]] = {}
    for half in (1, 2):
        for day in DAYS5:
            for idx, code in enumerate(THEORY_GRID[day]):
                h = THEORY_START[half][idx]
                atoms.setdefault(f"{code}{half}", []).append((day, time(h, 0), time(h, 50)))

    out: List[Dict[str, Any]] = []
    for half in (1, 2):
        for fam in "ABCDEFG":  # 2-credit theory: the main slot alone
            out.append({"name": f"{fam}{half}", "kind": "THEORY", "credits": 2, "periods": atoms[f"{fam}{half}"]})
        for fam in "ABCDEFG":  # 3-credit theory: main slot + tutorial slot
            parts = [f"{fam}{half}", f"T{fam}{half}"]
            out.append({"name": "+".join(parts), "kind": "THEORY", "credits": 3,
                        "periods": [p for a in parts for p in atoms[a]]})
        for fam in "ABCD":  # 4-credit theory: + second tutorial slot
            parts = [f"{fam}{half}", f"T{fam}{half}", f"T{fam}{fam}{half}"]
            out.append({"name": "+".join(parts), "kind": "THEORY", "credits": 4,
                        "periods": [p for a in parts for p in atoms[a]]})

    for half in (1, 2):
        for d, day in enumerate(DAYS5):
            base = (0 if half == 1 else 30) + 6 * d
            for k in range(0, 6, 2):
                a, b = k, k + 1
                periods = []
                for idx in (a, b):
                    sh, sm, eh, em = LAB_PERIODS[half][idx]
                    periods.append((day, time(sh, sm), time(eh, em)))
                out.append({"name": f"L{base + a + 1}+L{base + b + 1}", "kind": "LAB", "credits": 1, "periods": periods})
    return out


def load_standard_chart(db: Session) -> int:
    """Create the standard slot chart (idempotent: does nothing if slots already exist). Returns slots created."""
    if db.scalar(select(func.count(Slot.id))):
        return 0
    n = 0
    for spec in standard_chart():
        slot = Slot(name=spec["name"], kind=SlotKind(spec["kind"]), credits=spec["credits"])
        for day, start, end in spec["periods"]:
            slot.periods.append(SlotPeriod(day=day, start_time=start, end_time=end))
        db.add(slot)
        n += 1
    db.flush()
    return n


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def _slot_view(slot: Slot, used_by: int = 0) -> Dict[str, Any]:
    return {
        "id": slot.id,
        "name": slot.name,
        "kind": slot.kind.value,
        "credits": slot.credits,
        "periods": [
            {"day": p.day, "start_time": p.start_time.strftime("%H:%M"), "end_time": p.end_time.strftime("%H:%M")}
            for p in sorted(slot.periods, key=lambda p: (DAY_ORDER.index(p.day), p.start_time))
        ],
        "used_by": used_by,
    }


def list_slots(db: Session, kind: Optional[str] = None, credits: Optional[int] = None) -> List[Dict[str, Any]]:
    q = select(Slot).order_by(Slot.kind, Slot.credits, Slot.id)
    if kind:
        q = q.where(Slot.kind == SlotKind(kind))
    if credits is not None:
        q = q.where(Slot.credits == credits)
    used: Dict[int, int] = {}
    for col in (ClassSection.theory_slot_id, ClassSection.lab_slot_id):
        for sid, n in db.execute(select(col, func.count(ClassSection.id)).where(col.is_not(None)).group_by(col)):
            used[sid] = used.get(sid, 0) + n
    return [_slot_view(s, used.get(s.id, 0)) for s in db.scalars(q)]


# --------------------------------------------------------------------------- #
# Placement
# --------------------------------------------------------------------------- #
def is_locked(db: Session, cls: ClassSection) -> bool:
    """Students are enrolled or waiting: moving the slot would silently create clashes for them."""
    if cls.enrolled_count > 0:
        return True
    return bool(
        db.scalar(
            select(func.count(JoinRequest.id)).where(
                JoinRequest.class_id == cls.id, JoinRequest.status == RequestStatus.PENDING
            )
        )
    )


def faculty_clashes(
    db: Session, faculty_id: int, intervals: Sequence[Interval], cache: IntervalCache, exclude_class_id: Optional[int] = None
) -> List[ClassSection]:
    """Other offerings of this faculty member that overlap the given periods."""
    q = select(ClassSection).where(ClassSection.faculty_id == faculty_id, ClassSection.theory_slot_id.is_not(None))
    if exclude_class_id is not None:
        q = q.where(ClassSection.id != exclude_class_id)
    return [c for c in db.scalars(q) if intervals_overlap(intervals, class_intervals(c, cache))]


def _check_slots(db: Session, subject: Subject, theory_slot_id: Optional[int], lab_slot_id: Optional[int]) -> Tuple[Optional[Slot], Optional[Slot]]:
    theory = lab = None
    if theory_slot_id is not None:
        theory = db.get(Slot, theory_slot_id)
        if theory is None:
            raise NotFoundError("Theory slot not found")
        if theory.kind != SlotKind.THEORY or theory.credits != subject.credits:
            raise ValidationFailed(
                f"{subject.code} has {subject.credits} theory credits; choose a {subject.credits}-credit theory slot.",
                code="SLOT_MISMATCH",
            )
    if lab_slot_id is not None:
        lab = db.get(Slot, lab_slot_id)
        if lab is None:
            raise NotFoundError("Lab slot not found")
        if lab.kind != SlotKind.LAB:
            raise ValidationFailed("The lab part needs a lab slot (L..+L..).", code="SLOT_MISMATCH")
    if subject.has_lab and (theory is None) != (lab is None):
        raise ValidationFailed(
            f"{subject.code} is a theory+lab course: choose both its theory slot and its lab slot.", code="SLOT_INCOMPLETE"
        )
    if not subject.has_lab and lab is not None:
        raise ValidationFailed(f"{subject.code} has no lab component.", code="SLOT_MISMATCH")
    return theory, lab


def check_placement(
    db: Session, subject: Subject, faculty_id: int, theory_slot_id: Optional[int], lab_slot_id: Optional[int],
    exclude_class_id: Optional[int] = None,
) -> List[str]:
    """Validate a placement. Raises with a specific message if it clashes; returns a (currently empty) list of notes."""
    theory, lab = _check_slots(db, subject, theory_slot_id, lab_slot_id)
    if theory is None:
        return []
    cache = slot_intervals(db)
    mine = list(cache.get(theory.id, [])) + (list(cache.get(lab.id, [])) if lab else [])
    mine_parts: List[Part] = [("theory", theory)] + ([("lab", lab)] if lab else [])
    if lab and intervals_overlap(cache.get(theory.id, []), cache.get(lab.id, [])):
        c = part_clashes([("theory", theory)], [("lab", lab)], cache)[0]
        raise ValidationFailed(
            f"The theory slot {theory.name} and the lab slot {lab.name} of {subject.code} overlap "
            f"(on {c.when}). Choose a lab slot that does not overlap the theory slot.",
            code="SLOT_SELF_CLASH",
        )
    clash = faculty_clashes(db, faculty_id, mine, cache, exclude_class_id)
    if clash:
        c = clash[0]
        fac = db.get(Faculty, faculty_id)
        who = fac.user.name if fac else "This faculty member"
        pc = part_clashes(mine_parts, class_parts(c), cache)[0]
        raise ConflictError(
            f"{who} already teaches {c.subject.code} at that time. "
            + pc.sentence(f"the new {subject.code}", c.subject.code),
            code="FACULTY_CLASH",
        )
    return []


def set_placement(
    db: Session, class_id: int, theory_slot_id: Optional[int], lab_slot_id: Optional[int]
) -> Dict[str, Any]:
    """Place (or un-place) an offering. Rooms are then reassigned automatically."""
    from app.services import capacity_service, room_service

    cls = capacity_service.get_class(db, class_id, lock=True)
    if is_locked(db, cls):
        raise ConflictError(
            "Students are enrolled or waiting in this class, so its slot cannot be changed.", code="SLOT_LOCKED"
        )
    check_placement(db, cls.subject, cls.faculty_id, theory_slot_id, lab_slot_id, exclude_class_id=cls.id)
    cls.theory_slot_id = theory_slot_id
    cls.lab_slot_id = lab_slot_id if cls.subject.has_lab else None
    db.flush()
    rooms = room_service.assign_rooms(db)
    if theory_slot_id is not None and cls.id in rooms["unassigned_class_ids"]:
        db.rollback()
        raise ConflictError(
            "No free room of the right type and size is available during those periods.", code="NO_ROOM"
        )
    db.commit()
    return {"class_id": cls.id, "warnings": []}


# --------------------------------------------------------------------------- #
# Eligible faculty (busy teachers are simply absent from the drop-down)
# --------------------------------------------------------------------------- #
def eligible_faculty(
    db: Session, subject_id: int, theory_slot_id: Optional[int], lab_slot_id: Optional[int] = None
) -> Dict[str, Any]:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError("Subject not found")
    cache = slot_intervals(db)
    theory, lab = _check_slots(db, subject, theory_slot_id, lab_slot_id) if theory_slot_id else (None, None)
    mine: List[Interval] = []
    mine_parts: List[Part] = []
    if theory:
        mine += cache.get(theory.id, [])
        mine_parts.append(("theory", theory))
    if lab:
        mine += cache.get(lab.id, [])
        mine_parts.append(("lab", lab))

    already = set(db.scalars(select(ClassSection.faculty_id).where(ClassSection.subject_id == subject_id)))
    load = dict(
        db.execute(select(ClassSection.faculty_id, func.count(ClassSection.id)).group_by(ClassSection.faculty_id)).all()
    )
    available: List[Dict[str, Any]] = []
    unavailable: List[Dict[str, Any]] = []
    for f in db.scalars(select(Faculty).join(User, User.id == Faculty.user_id).order_by(User.name)):
        row = {"faculty_id": f.user_id, "name": f.user.name, "department": f.department, "courses": load.get(f.user_id, 0)}
        if f.user_id in already:
            unavailable.append({**row, "reason": f"already teaches {subject.code}"})
            continue
        if mine:
            clash = faculty_clashes(db, f.user_id, mine, cache)
            if clash:
                c = clash[0]
                pc = part_clashes(mine_parts, class_parts(c), cache)[0]
                unavailable.append({
                    **row,
                    "reason": f"teaches {c.subject.code} at the same time — the chosen {pc.a_kind} slot {pc.a_slot} "
                              f"overlaps {c.subject.code}'s {pc.b_kind} slot {pc.b_slot} ({pc.when})",
                })
                continue
        available.append(row)
    return {"available": available, "unavailable": unavailable}
