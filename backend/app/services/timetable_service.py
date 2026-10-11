"""Scheduling optimisation: automatic slot suggestion, clash report, slot chart and role-specific timetables.

The optimisation problem (solved by ``backtracking_slot_assignment``):

  vertices  every offering's theory part, and its lab part for theory+lab courses
  domain    slot packages of the right kind and credit value (a 3-credit theory part can only take 3-credit theory slots)
  hard      must never overlap in time:
              - two parts of the same faculty member
              - the theory and lab of one offering
              - two *mandatory* subjects of the same student group  (every student of the group takes both)
              - a mandatory subject vs an optional subject of the same group (the optional one would be unpickable)
  soft      preferably not overlapping: two optional subjects of one group (students want to combine them)
  fixed     offerings that are already placed stay exactly where they are
  rooms     at most (number of lecture / lab rooms) parts may meet in the identical period

Rooms are then derived automatically (``room_service``) - the Admin never enters same-room conflicts.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms.backtracking_graph_coloring import (
    Interval,
    backtracking_slot_assignment,
    intervals_overlap,
)
from app.core.errors import ValidationFailed
from app.models import (
    AlgorithmRun,
    ClassSection,
    CurriculumEntry,
    NotificationType,
    Registration,
    RegistrationStatus,
    Room,
    RoomKind,
    Slot,
    SlotKind,
    Student,
)
from app.models.enums import DAY_ORDER
from app.services import notification_service, room_service, slot_service

THEORY, LAB = "THEORY", "LAB"


def vid(class_id: int, part: str) -> int:
    return class_id * 2 + (1 if part == LAB else 0)


def part_of(v: int) -> str:
    return LAB if v % 2 else THEORY


# --------------------------------------------------------------------------- #
# Building the problem from real data
# --------------------------------------------------------------------------- #
@dataclass
class Problem:
    classes: Dict[int, ClassSection]
    vertices: List[int]
    domains: Dict[int, List[int]]
    hard: Dict[int, Set[int]]
    soft: Dict[int, Set[int]]
    reasons: Dict[Tuple[int, int], List[str]]
    intervals: Dict[int, List[Interval]]
    fixed: Dict[int, int]
    resource: Dict[int, str]
    capacity: Dict[str, int]
    slot_names: Dict[int, str]
    unplaceable: List[str] = field(default_factory=list)

    def label(self, v: int) -> str:
        c = self.classes[v // 2]
        return f"{c.subject.code} / {c.faculty.user.name}" + (" (lab)" if part_of(v) == LAB else "")

    @property
    def free(self) -> List[int]:
        return [v for v in self.vertices if v not in self.fixed]


def _edge(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a < b else (b, a)


def build_problem(db: Session) -> Problem:
    classes = {c.id: c for c in db.scalars(select(ClassSection).order_by(ClassSection.id))}
    cache = slot_service.slot_intervals(db)
    slots = list(db.scalars(select(Slot).order_by(Slot.id)))
    slot_names = {s.id: s.name for s in slots}
    theory_by_credits: Dict[int, List[int]] = {}
    lab_slots: List[int] = []
    for s in slots:
        if s.kind == SlotKind.THEORY:
            theory_by_credits.setdefault(s.credits, []).append(s.id)
        else:
            lab_slots.append(s.id)

    vertices: List[int] = []
    domains: Dict[int, List[int]] = {}
    fixed: Dict[int, int] = {}
    resource: Dict[int, str] = {}
    unplaceable: List[str] = []
    verts_of_subject: Dict[int, List[int]] = {}
    verts_of_faculty: Dict[int, List[int]] = {}
    for c in classes.values():
        parts = [(THEORY, c.theory_slot_id)] + ([(LAB, c.lab_slot_id)] if c.subject.has_lab else [])
        for part, slot_id in parts:
            v = vid(c.id, part)
            vertices.append(v)
            resource[v] = "LECTURE" if part == THEORY else "LAB"
            domains[v] = list(theory_by_credits.get(c.subject.credits, [])) if part == THEORY else list(lab_slots)
            if c.theory_slot_id is not None and slot_id is not None:
                fixed[v] = slot_id
                domains[v] = [slot_id]
            verts_of_subject.setdefault(c.subject_id, []).append(v)
            verts_of_faculty.setdefault(c.faculty_id, []).append(v)

    hard: Dict[int, Set[int]] = {v: set() for v in vertices}
    soft: Dict[int, Set[int]] = {v: set() for v in vertices}
    reasons: Dict[Tuple[int, int], List[str]] = {}

    def add(table: Dict[int, Set[int]], a: int, b: int, why: str) -> None:
        if a == b:
            return
        table[a].add(b)
        table[b].add(a)
        bucket = reasons.setdefault(_edge(a, b), [])
        if why not in bucket and len(bucket) < 3:
            bucket.append(why)

    for c in classes.values():
        if c.subject.has_lab:
            add(hard, vid(c.id, THEORY), vid(c.id, LAB), "theory and lab of the same offering")
    for fid, vs in verts_of_faculty.items():
        name = classes[vs[0] // 2].faculty.user.name
        for i, a in enumerate(vs):
            for b in vs[i + 1:]:
                if a // 2 != b // 2:
                    add(hard, a, b, f"same faculty ({name})")

    groups: Dict[str, Dict[str, List[int]]] = {}
    for g, sid, mand in db.execute(
        select(CurriculumEntry.group_code, CurriculumEntry.subject_id, CurriculumEntry.is_mandatory)
    ):
        groups.setdefault(g, {"M": [], "N": []})["M" if mand else "N"].append(sid)
    code_of = {c.subject_id: c.subject.code for c in classes.values()}
    for g, parts in groups.items():
        mand = [s for s in parts["M"] if s in verts_of_subject]
        opt = [s for s in parts["N"] if s in verts_of_subject]
        for i, m1 in enumerate(mand):
            for m2 in mand[i + 1:]:
                for a in verts_of_subject[m1]:
                    for b in verts_of_subject[m2]:
                        add(hard, a, b, f"{g}: mandatory {code_of[m1]} + {code_of[m2]}")
            for n in opt:
                for a in verts_of_subject[m1]:
                    for b in verts_of_subject[n]:
                        add(hard, a, b, f"{g}: mandatory {code_of[m1]} vs optional {code_of[n]}")
        for i, n1 in enumerate(opt):
            for n2 in opt[i + 1:]:
                for a in verts_of_subject[n1]:
                    for b in verts_of_subject[n2]:
                        add(soft, a, b, f"{g}: optional subjects")

    capacity: Dict[str, int] = {}
    for kind, n in (("LECTURE", RoomKind.LECTURE), ("LAB", RoomKind.LAB)):
        count = len(list(db.scalars(select(Room.id).where(Room.kind == n))))
        if count:
            capacity[kind] = count
    for v in vertices:
        if not domains[v]:
            unplaceable.append(f"{classes[v // 2].subject.code}: no {'lab' if part_of(v) == LAB else str(classes[v // 2].subject.credits) + '-credit theory'} slots exist")
    return Problem(classes, vertices, domains, hard, soft, reasons, cache, fixed, resource, capacity, slot_names, sorted(set(unplaceable)))


def _assigned(problem: Problem) -> Dict[int, int]:
    """Slot currently stored for every placed vertex."""
    out: Dict[int, int] = {}
    for c in problem.classes.values():
        if c.theory_slot_id is not None:
            out[vid(c.id, THEORY)] = c.theory_slot_id
            if c.lab_slot_id is not None:
                out[vid(c.id, LAB)] = c.lab_slot_id
    return out


def _overlap(problem: Problem, a_slot: int, b_slot: int) -> bool:
    return intervals_overlap(problem.intervals.get(a_slot, []), problem.intervals.get(b_slot, []))


def group_warnings(db: Session, cls: ClassSection) -> List[str]:
    """After placing one offering: which already-placed classes does it overlap (beyond blocking errors)?"""
    problem = build_problem(db)
    placed = _assigned(problem)
    out: List[str] = []
    optional: List[str] = []
    for part in (THEORY, LAB):
        v = vid(cls.id, part)
        if v not in placed:
            continue
        for u in problem.hard.get(v, ()):
            if u in placed and u // 2 != cls.id and _overlap(problem, placed[v], placed[u]):
                out.append(f"Overlaps {problem.label(u)} - {'; '.join(problem.reasons[_edge(v, u)])}")
        for u in problem.soft.get(v, ()):
            if u in placed and _overlap(problem, placed[v], placed[u]):
                optional.append(problem.classes[u // 2].subject.code)
    if optional:
        out.append("Shares time with optional " + ", ".join(sorted(set(optional))[:6]) + ": students of that group can pick only one.")
    return out


# --------------------------------------------------------------------------- #
# The optimisation: automatic slot suggestion
# --------------------------------------------------------------------------- #
def auto_assign(db: Session, admin_id: Optional[int] = None, dry_run: bool = False, max_steps: int = 300_000) -> Dict[str, Any]:
    problem = build_problem(db)
    free = problem.free
    report: Dict[str, Any] = {
        "dry_run": dry_run,
        "offerings": len(problem.classes),
        "already_placed": len({v // 2 for v in problem.fixed}),
        "to_place": len({v // 2 for v in free}),
        "vertices_to_place": len(free),
        "hard_edges": sum(len(s) for s in problem.hard.values()) // 2,
        "soft_edges": sum(len(s) for s in problem.soft.values()) // 2,
        "rooms": dict(problem.capacity),
    }
    edges = sorted({_edge(a, b) for a, ns in problem.hard.items() for b in ns if a in free or b in free})
    report["edges_total"] = len(edges)
    report["edges"] = [
        {"a": problem.label(a), "b": problem.label(b), "reasons": problem.reasons[(a, b)]} for a, b in edges[:150]
    ]
    if not free:
        report.update(status="OK", message="Every offering is already placed.", nodes_visited=0, backtracks=0,
                      backtracking_required=False, soft_overlaps=0, assignments=[], rooms_unassigned=[])
        return report
    if problem.unplaceable:
        report.update(status="INFEASIBLE", message="; ".join(problem.unplaceable) + ". Load the standard slot chart first.",
                      nodes_visited=0, backtracks=0, backtracking_required=False, soft_overlaps=0, assignments=[], rooms_unassigned=[])
        if not dry_run:
            raise ValidationFailed(report["message"], code="NO_SLOTS", extra={"report": report})
        return report

    result = backtracking_slot_assignment(
        problem.vertices, problem.domains, problem.hard, problem.intervals,
        fixed=problem.fixed, soft=problem.soft, resource=problem.resource,
        resource_capacity=problem.capacity, max_steps=max_steps,
    )
    report.update(
        status=result.status, message=result.message, nodes_visited=result.nodes_visited, backtracks=result.backtracks,
        backtracking_required=result.backtracking_required, soft_overlaps=result.soft_overlaps,
        vertex_order=[problem.label(v) for v in result.order[:40]],
    )
    placements: Dict[int, Dict[str, Optional[int]]] = {}
    if result.success:
        for v in free:
            placements.setdefault(v // 2, {})[part_of(v)] = result.assignment[v]
    report["assignments"] = [
        {
            "class_id": cid,
            "subject_code": problem.classes[cid].subject.code,
            "faculty": problem.classes[cid].faculty.user.name,
            "theory_slot": problem.slot_names.get(p.get(THEORY)),
            "lab_slot": problem.slot_names.get(p.get(LAB)),
        }
        for cid, p in sorted(placements.items())
    ]
    report["rooms_unassigned"] = []
    if dry_run:
        return report

    if not result.success:
        db.add(AlgorithmRun(algorithm="slot_assignment", status="FAILED", summary=_run_summary(report), triggered_by=admin_id))
        db.commit()
        raise ValidationFailed(f"Slots could not be assigned: {result.message}", code="PLACEMENT_INFEASIBLE", extra={"report": report})

    for cid, p in placements.items():
        c = problem.classes[cid]
        c.theory_slot_id = p.get(THEORY)
        c.lab_slot_id = p.get(LAB)
    db.flush()
    rooms = room_service.assign_rooms(db)
    report["rooms_unassigned"] = [
        f"{problem.classes[i].subject.code} / {problem.classes[i].faculty.user.name}" for i in rooms["unassigned_class_ids"]
    ]
    db.add(AlgorithmRun(algorithm="slot_assignment", status="SUCCESS", summary=_run_summary(report), triggered_by=admin_id))
    for cid, p in placements.items():
        c = problem.classes[cid]
        notification_service.notify(
            db, c.faculty_id, NotificationType.SCHEDULE_UPDATED,
            f"{c.subject.code} was scheduled in {problem.slot_names[p[THEORY]]}"
            + (f" with lab {problem.slot_names[p[LAB]]}." if LAB in p and p[LAB] else "."),
        )
    notification_service.notify_admins(
        db, NotificationType.TIMETABLE_GENERATED,
        f"Slots assigned for {len(placements)} offering(s); {result.soft_overlaps} optional-subject overlap(s) remain.",
    )
    db.commit()
    return report


def _run_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("status", "to_place", "already_placed", "hard_edges", "soft_edges", "nodes_visited", "backtracks", "soft_overlaps", "message")
    return {k: report.get(k) for k in keep}


def clear_unlocked(db: Session) -> int:
    """Un-place every offering nobody has enrolled in or requested (so auto-assign can re-optimise them)."""
    n = 0
    for c in db.scalars(select(ClassSection).where(ClassSection.theory_slot_id.is_not(None))):
        if not slot_service.is_locked(db, c):
            c.theory_slot_id = c.lab_slot_id = c.room_id = c.lab_room_id = None
            n += 1
    db.commit()
    return n


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def clash_report(db: Session) -> Dict[str, Any]:
    problem = build_problem(db)
    placed = _assigned(problem)
    hard, soft = [], []
    for (a, b), why in sorted(problem.reasons.items()):
        if a in placed and b in placed and _overlap(problem, placed[a], placed[b]):
            row = {"a": problem.label(a), "b": problem.label(b), "reasons": why}
            if b in problem.hard.get(a, ()):
                hard.append(row)
            elif b in problem.soft.get(a, ()):
                soft.append(row)

    cache = problem.intervals
    student_rows = []
    by_student: Dict[int, List[ClassSection]] = {}
    for sid, cid in db.execute(
        select(Registration.student_id, Registration.class_id).where(
            Registration.status == RegistrationStatus.ENROLLED, Registration.class_id.is_not(None)
        )
    ):
        by_student.setdefault(sid, []).append(problem.classes[cid])
    names = {s.user_id: s.user.name for s in db.scalars(select(Student))}
    for sid, cs in by_student.items():
        for i, a in enumerate(cs):
            for b in cs[i + 1:]:
                if intervals_overlap(slot_service.class_intervals(a, cache), slot_service.class_intervals(b, cache)):
                    student_rows.append({"student": names.get(sid, str(sid)), "a": a.subject.code, "b": b.subject.code})

    return {
        "unscheduled": [
            {"class_id": c.id, "subject_code": c.subject.code, "faculty": c.faculty.user.name}
            for c in problem.classes.values() if not c.is_scheduled
        ],
        "no_room": [
            {"class_id": c.id, "subject_code": c.subject.code, "faculty": c.faculty.user.name}
            for c in problem.classes.values()
            if c.is_scheduled and (c.room_id is None or (c.lab_slot_id and c.lab_room_id is None))
        ],
        "hard_clashes": hard,
        "shared_slot_options": soft,
        "student_clashes": student_rows,
    }


def slot_chart(db: Session) -> Dict[str, Any]:
    """Every slot that has offerings, with the offerings in it - i.e. which subjects are alternatives in one slot."""
    slots = {s["id"]: s for s in slot_service.list_slots(db)}
    for s in slots.values():
        s["offerings"] = []
    unscheduled = []
    for c in db.scalars(select(ClassSection).order_by(ClassSection.id)):
        row = {
            "class_id": c.id, "subject_code": c.subject.code, "subject_name": c.subject.name,
            "faculty": c.faculty.user.name, "seats": c.capacity, "enrolled": c.enrolled_count, "status": c.status.value,
        }
        if not c.is_scheduled:
            unscheduled.append(row)
            continue
        slots[c.theory_slot_id]["offerings"].append({**row, "component": THEORY, "room": c.room.name if c.room else None})
        if c.lab_slot_id:
            slots[c.lab_slot_id]["offerings"].append({**row, "component": LAB, "room": c.lab_room.name if c.lab_room else None})
    used = [s for s in slots.values() if s["offerings"]]
    return {
        "slots": used,
        "free_slots": {"THEORY": sum(1 for s in slots.values() if s["kind"] == "THEORY" and not s["offerings"]),
                       "LAB": sum(1 for s in slots.values() if s["kind"] == "LAB" and not s["offerings"])},
        "unscheduled": unscheduled,
    }


# --------------------------------------------------------------------------- #
# Role-specific timetable views (derived from the offerings' slots)
# --------------------------------------------------------------------------- #
def _entries_for(classes: List[ClassSection]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in classes:
        for component, slot, room in ((THEORY, c.theory_slot, c.room), (LAB, c.lab_slot, c.lab_room)):
            if slot is None:
                continue
            for p in slot.periods:
                out.append(
                    {
                        "entry_id": f"{c.id}-{component}-{p.day}-{p.start_time.strftime('%H%M')}",
                        "class_id": c.id,
                        "subject_code": c.subject.code,
                        "subject_name": c.subject.name,
                        "faculty_id": c.faculty_id,
                        "faculty_name": c.faculty.user.name,
                        "component": component,
                        "slot": slot.name,
                        "day": p.day,
                        "start_time": p.start_time.strftime("%H:%M"),
                        "end_time": p.end_time.strftime("%H:%M"),
                        "room": room.name if room else None,
                    }
                )
    return sorted(
        out,
        key=lambda d: (DAY_ORDER.index(d["day"]) if d["day"] in DAY_ORDER else 99, d["start_time"], d["subject_code"]),
    )


def all_entries(db: Session) -> List[Dict[str, Any]]:
    return _entries_for(list(db.scalars(select(ClassSection).where(ClassSection.theory_slot_id.is_not(None)))))


def faculty_entries(db: Session, faculty_id: int) -> List[Dict[str, Any]]:
    return _entries_for(
        list(db.scalars(select(ClassSection).where(ClassSection.faculty_id == faculty_id, ClassSection.theory_slot_id.is_not(None))))
    )


def student_entries(db: Session, student_id: int) -> List[Dict[str, Any]]:
    classes = list(
        db.scalars(
            select(ClassSection)
            .join(Registration, Registration.class_id == ClassSection.id)
            .where(Registration.student_id == student_id, Registration.status == RegistrationStatus.ENROLLED,
                   ClassSection.theory_slot_id.is_not(None))
        )
    )
    return _entries_for(classes)
