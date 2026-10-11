"""Automatic room assignment.

Admin never enters "these classes share a room". Two offerings whose periods overlap simply cannot be given the
same room, and a lab part needs a LAB room while a theory part needs a LECTURE room of enough seats.

Rule (deterministic): parts are handled biggest class first; each takes the *smallest* room of the right kind that
is large enough and free during all of its periods. If none is free the part is reported as unassigned.
"""
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms.backtracking_graph_coloring import Interval, intervals_overlap
from app.models import ClassSection, Room, RoomKind
from app.services import slot_service


def assign_rooms(db: Session) -> Dict[str, Any]:
    """Recompute rooms for every scheduled offering. Does not commit."""
    cache = slot_service.slot_intervals(db)
    rooms = list(db.scalars(select(Room).order_by(Room.capacity, Room.id)))
    by_kind = {k: [r for r in rooms if r.kind == k] for k in (RoomKind.LECTURE, RoomKind.LAB)}
    busy: Dict[int, List[Interval]] = {r.id: [] for r in rooms}

    classes = list(db.scalars(select(ClassSection).where(ClassSection.theory_slot_id.is_not(None))))
    unscheduled = list(db.scalars(select(ClassSection).where(ClassSection.theory_slot_id.is_(None))))
    for c in unscheduled:
        c.room_id = c.lab_room_id = None

    parts: List[Tuple[ClassSection, str, int, RoomKind]] = []
    for c in classes:
        parts.append((c, "room_id", c.theory_slot_id, RoomKind.LECTURE))
        if c.lab_slot_id is not None:
            parts.append((c, "lab_room_id", c.lab_slot_id, RoomKind.LAB))
    parts.sort(key=lambda p: (-p[0].capacity, p[0].id, p[1]))

    unassigned: List[int] = []
    for cls, attr, slot_id, kind in parts:
        need = cache.get(slot_id, [])
        if not by_kind[kind]:  # no rooms of this type defined at all: nothing to assign, nothing to complain about
            setattr(cls, attr, None)
            continue
        chosen = None
        for room in by_kind[kind]:
            if room.capacity >= cls.capacity and not intervals_overlap(need, busy[room.id]):
                chosen = room
                break
        if chosen is None:
            setattr(cls, attr, None)
            unassigned.append(cls.id)
        else:
            busy[chosen.id].extend(need)
            setattr(cls, attr, chosen.id)
    for c in classes:
        if c.lab_slot_id is None:
            c.lab_room_id = None
    db.flush()
    return {"assigned_parts": sum(1 for c, a, _, _ in parts if getattr(c, a) is not None), "unassigned_class_ids": sorted(set(unassigned))}
