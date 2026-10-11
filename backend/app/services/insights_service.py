"""Read-only 'Algorithm Insights' for the Admin demo page + the Edmonds-Karp planning report.

Nothing here changes enrolments, queues or capacities: the FCFS workflow stays authoritative.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms.edmonds_karp import FlowNetwork
from app.algorithms.fifo_queue import serve_from_front
from app.algorithms.greedy_faculty_allocation import Preference, rank_candidates
from app.algorithms.backtracking_graph_coloring import intervals_overlap
from app.core.errors import NotFoundError
from app.models import (
    AlgorithmRun,
    ClassSection,
    ClassStatus,
    Registration,
    RegistrationStatus,
    Student,
    Subject,
)
from app.services import allocation_service, capacity_service, slot_service, timetable_service
from app.services.allocation_service import GREEDY_CONFIG

COMPLEXITY = {
    "fifo": {
        "enqueue": "O(1)", "dequeue": "O(1)", "peek": "O(1)",
        "note": "Backed by collections.deque; queue_seq in the DB makes the order durable.",
    },
    "greedy": {
        "selection": "O(F) for F candidate faculties (single scan, C criteria = constant)",
        "ranking_for_display": "O(F log F)",
    },
    "graph_coloring": {
        "worst_case": "O(k^V) for V class parts and k candidate slots (NP-complete in general)",
        "practical": "highest-degree-first order, pre-placed offerings kept fixed, per-vertex slot domains, "
        "least-loaded/least-clashing slot first, room-count limit per period, step budget",
    },
    "max_flow": {
        "worst_case": "O(V * E^2) (Edmonds-Karp: BFS augmenting paths)",
        "bfs_per_augmentation": "O(E)",
    },
}


# --------------------------------------------------------------------------- #
# FIFO
# --------------------------------------------------------------------------- #
def fifo_insight(db: Session, class_id: int) -> Dict[str, Any]:
    cls = capacity_service.get_class(db, class_id)
    queue = capacity_service.hydrate_queue(db, class_id)
    before = [
        {"request_id": r.id, "queue_seq": r.queue_seq, "student": r.student.user.name, "requested_at": r.requested_at}
        for r in queue
    ]
    seats = cls.remaining if cls.status == ClassStatus.OPEN else 0
    res = serve_from_front(queue, seats)
    fmt = lambda r: {"request_id": r.id, "queue_seq": r.queue_seq, "student": r.student.user.name}  # noqa: E731
    return {
        "class": {
            "id": cls.id, "label": capacity_service.class_label(cls),
            "capacity": cls.capacity, "enrolled": cls.enrolled_count, "remaining": cls.remaining,
            "status": cls.status.value,
        },
        "queue_before": before,
        "simulation": {
            "seats_available": seats,
            "would_accept_in_order": [fmt(r) for r in res.served],
            # once the last seat is taken the class closes and everyone still waiting is turned away
            "would_be_turned_away_when_full": (
                [fmt(r) for r in res.remaining] if seats and len(res.served) == seats else []
            ),
            "would_remain_waiting": (
                [fmt(r) for r in res.remaining] if not (seats and len(res.served) == seats) else []
            ),
        },
        "order_is_arrival_order": [b["queue_seq"] for b in before] == sorted(b["queue_seq"] for b in before),
        "complexity": COMPLEXITY["fifo"],
    }


# --------------------------------------------------------------------------- #
# Greedy
# --------------------------------------------------------------------------- #
def greedy_insight(
    db: Session, subject_id: int, student_id: Optional[int], preferred_class_id: Optional[int]
) -> Dict[str, Any]:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError("Subject not found")
    result = allocation_service.greedy_pick(
        db, subject_id, student_id=student_id, preferred_class_id=preferred_class_id
    )
    cands = [sc.candidate for sc in result.considered]
    ranked = rank_candidates(cands, _pref(preferred_class_id), GREEDY_CONFIG)
    return {
        "subject": f"{subject.code} - {subject.name}",
        "criteria_order": list(result.criteria),
        "rule": "Keep the preferred class if it has a seat; otherwise take the available class with the "
        "lexicographically best priority vector; ties -> lowest class id.",
        "candidates": [
            {
                "class_id": sc.candidate.class_id,
                "faculty": sc.candidate.faculty_name,
                "remaining": sc.candidate.remaining_capacity,
                "queue_length": sc.candidate.queue_length,
                "slot_compatible": sc.candidate.slot_compatible,
                "available": sc.available,
                "score": list(sc.score),
                "rank": i + 1,
            }
            for i, sc in enumerate(ranked)
        ],
        "selected": (
            {"class_id": result.selected.class_id, "faculty": result.selected.faculty_name}
            if result.selected else None
        ),
        "preferred_honoured": result.preferred_honoured,
        "reason": result.reason,
        "complexity": COMPLEXITY["greedy"],
    }


def _pref(class_id):
    return Preference(class_id=class_id)


# --------------------------------------------------------------------------- #
# Graph colouring (dry run - nothing is stored)
# --------------------------------------------------------------------------- #
def coloring_insight(db: Session) -> Dict[str, Any]:
    """Dry run of the slot optimiser (nothing is saved): conflict edges, the placement it would make, backtracking."""
    report = timetable_service.auto_assign(db, dry_run=True)
    report["complexity"] = COMPLEXITY["graph_coloring"]
    return report


# --------------------------------------------------------------------------- #
# Edmonds-Karp
# --------------------------------------------------------------------------- #
SOURCE, SINK = "SOURCE", "SINK"


def max_flow_report(db: Session) -> Dict[str, Any]:
    demands = db.execute(
        select(Registration.student_id, Registration.subject_id)
        .where(Registration.status.in_([RegistrationStatus.SELECTED, RegistrationStatus.REQUESTED]))
        .order_by(Registration.subject_id, Registration.created_at, Registration.id)
    ).all()
    classes = list(
        db.scalars(
            select(ClassSection)
            .where(ClassSection.status == ClassStatus.OPEN, ClassSection.theory_slot_id.is_not(None))
            .order_by(ClassSection.id)
        )
    )
    cache = slot_service.slot_intervals(db)
    enrolled_iv: Dict[int, List] = {}
    for sid, c in db.execute(
        select(Registration.student_id, ClassSection)
        .join(ClassSection, ClassSection.id == Registration.class_id)
        .where(Registration.status == RegistrationStatus.ENROLLED)
    ):
        enrolled_iv.setdefault(sid, []).append(slot_service.class_intervals(c, cache))
    by_subject: Dict[int, List[ClassSection]] = {}
    for c in classes:
        by_subject.setdefault(c.subject_id, []).append(c)

    student_names = {
        s.user_id: s.user.name for s in db.scalars(select(Student).where(Student.user_id.in_({d[0] for d in demands} or {0})))
    }
    subjects = {s.id: s for s in db.scalars(select(Subject))}

    net = FlowNetwork()
    net.add_node(SOURCE)
    net.add_node(SINK)
    sink_edge: Dict[int, int] = {}
    for c in classes:
        sink_edge[c.id] = net.add_edge(f"C:{c.id}", SINK, c.remaining)  # class -> sink = free seats
    for sid, subj in demands:
        node = f"D:{sid}:{subj}"
        net.add_edge(SOURCE, node, 1)  # each (student, subject) demand needs exactly one seat
        for c in by_subject.get(subj, []):
            mine = slot_service.class_intervals(c, cache)
            if any(intervals_overlap(mine, h) for h in enrolled_iv.get(sid, [])):
                continue  # this offering would clash with a class the student is already enrolled in
            net.add_edge(node, f"C:{c.id}", 1)

    res = net.max_flow(SOURCE, SINK)
    flow = {(u, v): f for u, v, cap, f in res.edge_flows}
    placed = {(sid, subj): None for sid, subj in demands}
    for (u, v), f in flow.items():
        if f > 0 and u.startswith("D:") and v.startswith("C:"):
            _, sid, subj = u.split(":")
            placed[(int(sid), int(subj))] = int(v.split(":")[1])

    bottleneck_nodes = {u for u, v, cap in res.min_cut_edges if v == SINK}
    class_rows = []
    for c in classes:
        assigned = flow[(f"C:{c.id}", SINK)]
        class_rows.append(
            {
                "class_id": c.id,
                "subject_code": c.subject.code,
                "faculty_name": c.faculty.user.name,
                "free_seats": c.remaining,
                "assigned": assigned,
                "saturated": assigned >= c.remaining and c.remaining > 0,
                "bottleneck": f"C:{c.id}" in bottleneck_nodes,
            }
        )
    subj_rows = []
    for subj_id in sorted({d[1] for d in demands} | set(by_subject)):
        dem = [k for k in placed if k[1] == subj_id]
        ok = sum(1 for k in dem if placed[k] is not None)
        subj_rows.append(
            {
                "subject_id": subj_id,
                "code": subjects[subj_id].code,
                "demand": len(dem),
                "accommodated": ok,
                "unaccommodated": len(dem) - ok,
                "free_seats": sum(c.remaining for c in by_subject.get(subj_id, [])),
            }
        )
    total = len(demands)
    return {
        "summary": {
            "total_requested": total,
            "distinct_students": len({d[0] for d in demands}),
            "max_flow": res.max_flow,
            "unaccommodated": total - res.max_flow,
            "total_free_seats": sum(c.remaining for c in classes),
        },
        "network": {
            "nodes": net.node_count,
            "edges": net.edge_count,
            "layers": "source -> (student, subject) demand [cap 1] -> class [cap 1] -> sink [cap = free seats]",
            "augmenting_paths": len(res.augmenting_paths),
        },
        "classes": class_rows,
        "bottleneck_classes": [r for r in class_rows if r["bottleneck"]],
        "subjects": subj_rows,
        "allocation": [
            {
                "student": student_names.get(sid, str(sid)),
                "subject": subjects[subj].code,
                "class_id": cid,
            }
            for (sid, subj), cid in placed.items()
            if cid is not None
        ],
        "unaccommodated_students": [
            {"student": student_names.get(sid, str(sid)), "subject": subjects[subj].code}
            for (sid, subj), cid in placed.items()
            if cid is None
        ],
        "complexity": COMPLEXITY["max_flow"],
        "note": "Planning aid only: actual acceptance remains strictly first-come-first-served.",
    }


def run_and_record_max_flow(db: Session, admin_id: int) -> Dict[str, Any]:
    report = max_flow_report(db)
    db.add(
        AlgorithmRun(
            algorithm="edmonds_karp",
            status="SUCCESS",
            summary={**report["summary"], "bottleneck_classes": len(report["bottleneck_classes"])},
            triggered_by=admin_id,
        )
    )
    db.commit()
    return report


def recent_runs(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    rows = db.scalars(select(AlgorithmRun).order_by(AlgorithmRun.id.desc()).limit(limit))
    return [
        {"id": r.id, "algorithm": r.algorithm, "status": r.status, "summary": r.summary, "created_at": r.created_at}
        for r in rows
    ]
