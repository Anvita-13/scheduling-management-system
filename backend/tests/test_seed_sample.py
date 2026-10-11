"""The VIT-style sample dataset: structure, option courses, automatic scheduling and (once) the simulated registration."""
import random
import re

import pytest
from sqlalchemy import func, select

from app.algorithms.backtracking_graph_coloring import intervals_overlap
from app.db.seed import COURSES, STUDENT_COUNT, build_structure, simulate_registration
from app.models import ClassSection, Faculty, Registration, RegistrationStatus, Room, Slot, Student, Subject, User
from app.services import slot_service, timetable_service


@pytest.fixture()
def seeded(db):
    build_structure(db, random.Random(2026))
    return db


def test_structure_follows_the_requested_shape(seeded):
    db = seeded
    names = [n for (n,) in db.execute(select(User.name).join(Faculty, Faculty.user_id == User.id))]
    assert len(names) == 26 and len(set(names)) == 26
    assert all(re.fullmatch(r"(Dr\.|Prof\.) [A-Z][a-z]+ [A-Z][a-z]+", n) for n in names)  # fake personal names, not fac1..N
    assert not any(re.search(r"fac\d", n) for n in names)

    offerings = dict(db.execute(select(Subject.code, func.count(ClassSection.id)).join(ClassSection, ClassSection.subject_id == Subject.id).group_by(Subject.code)).all())
    options = {c for c, n in offerings.items() if n > 1}
    assert options == {"BMAT101L", "BCSE202L"}  # exactly two courses come with faculty options
    assert offerings["BMAT101L"] == 4 and offerings["BCSE202L"] == 5

    codes = {c["code"]: c for c in COURSES}
    assert codes["BMAT101L"]["l"] == 0 and codes["BCSE202L"]["l"] == 1  # one theory-only, one theory+lab
    assert db.scalar(select(func.count(Student.user_id))) == STUDENT_COUNT == 122  # one pool of students, no groups

    assert db.scalar(select(func.count(Slot.id))) == 66 and db.scalar(select(func.count(Room.id))) == 18


def test_every_offering_is_scheduled_with_rooms_and_no_clashes(seeded):
    db = seeded
    classes = list(db.scalars(select(ClassSection)))
    assert all(c.theory_slot_id and c.room_id for c in classes)
    assert all((c.lab_slot_id and c.lab_room_id) for c in classes if c.subject.has_lab)
    assert all(c.lab_slot_id is None for c in classes if not c.subject.has_lab)
    report = timetable_service.clash_report(db)
    assert report["hard_clashes"] == [] and report["unscheduled"] == [] and report["no_room"] == []
    cache = slot_service.slot_intervals(db)
    by_faculty = {}
    for c in classes:
        by_faculty.setdefault(c.faculty_id, []).append(slot_service.class_intervals(c, cache))
    for ivs in by_faculty.values():  # a teacher is never in two places at once
        assert not any(intervals_overlap(a, b) for i, a in enumerate(ivs) for b in ivs[i + 1:])
    # room double-booking is impossible too
    rooms = {}
    for c in classes:
        for rid, sid in ((c.room_id, c.theory_slot_id), (c.lab_room_id, c.lab_slot_id)):
            if rid:
                rooms.setdefault(rid, []).append(cache[sid])
    for ivs in rooms.values():
        assert not any(intervals_overlap(a, b) for i, a in enumerate(ivs) for b in ivs[i + 1:])


def test_dsa_faculty_each_own_a_theory_lab_pair_and_two_share_a_lab_slot(seeded):
    db = seeded
    dsa = list(db.scalars(select(ClassSection).join(Subject).where(Subject.code == "BCSE202L").order_by(ClassSection.id)))
    assert [c.theory_slot.name for c in dsa] == ["C1+TC1", "D1+TD1", "E2+TE2", "F2+TF2", "G1+TG1"]
    assert dsa[0].lab_slot_id == dsa[1].lab_slot_id and dsa[0].lab_room_id != dsa[1].lab_room_id  # shared lab slot -> 2 rooms
    assert len({c.lab_slot_id for c in dsa}) == 4


def test_simulated_registration_never_creates_a_student_clash_or_overbooking(seeded):
    db = seeded
    simulate_registration(db, random.Random(2026))
    assert timetable_service.clash_report(db)["student_clashes"] == []
    assert all(c.enrolled_count <= c.capacity for c in db.scalars(select(ClassSection)))
    statuses = {s for (s,) in db.execute(select(Registration.status).distinct())}
    assert RegistrationStatus.ENROLLED in statuses
    # every student chose subjects freely: nobody is forced into any subject, and nobody holds subjects that clash
    n_students = db.scalar(select(func.count(Student.user_id)))
    assert db.scalar(select(func.count(Registration.id))) >= 3 * n_students
    assert all(s.selected_credits for s in db.scalars(select(Student)))
