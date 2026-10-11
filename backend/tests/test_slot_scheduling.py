import pytest
from sqlalchemy import select

from app.algorithms.backtracking_graph_coloring import intervals_overlap
from app.core.errors import ConflictError, ValidationFailed
from app.models import ClassSection, Registration, RegistrationStatus, Slot, SlotKind
from app.services import (
    admin_service,
    faculty_service,
    insights_service,
    registration_service as reg,
    room_service,
    slot_service,
    timetable_service,
)
from tests.factories import (
    make_admin, make_class, make_faculty, make_rooms, make_slot, make_student, make_subject, pick,
)


def slot_by_name(db, name):
    return db.scalar(select(Slot).where(Slot.name == name))


# ------------------------------ the slot chart ------------------------------ #
def test_standard_chart_has_vit_style_packages(db):
    assert slot_service.load_standard_chart(db) == 66 and slot_service.load_standard_chart(db) == 0  # idempotent
    db.commit()
    theory = db.scalars(select(Slot).where(Slot.kind == SlotKind.THEORY)).all()
    labs = db.scalars(select(Slot).where(Slot.kind == SlotKind.LAB)).all()
    assert len(theory) == 36 and len(labs) == 30
    assert {s.credits for s in theory} == {2, 3, 4} and {s.credits for s in labs} == {1}
    a = slot_by_name(db, "A1+TA1")
    assert [(p.day, p.start_time.strftime("%H:%M")) for p in a.periods] == [("Mon", "08:00"), ("Wed", "09:00"), ("Fri", "10:00")]
    assert len(slot_by_name(db, "A1+TA1+TAA1").periods) == 4 and len(slot_by_name(db, "A1").periods) == 2
    assert len(slot_by_name(db, "L1+L2").periods) == 2


def test_theory_and_lab_slots_overlap_by_time_not_by_name(db):
    slot_service.load_standard_chart(db)
    db.commit()
    cache = slot_service.slot_intervals(db)
    iv = lambda name: cache[slot_by_name(db, name).id]  # noqa: E731
    assert intervals_overlap(iv("A1+TA1"), iv("L1+L2"))  # Mon 08:00 theory vs Mon 08:00-09:40 lab
    assert intervals_overlap(iv("F1+TF1"), iv("L1+L2"))  # Mon 09:00 theory vs lab period 08:51-09:40
    assert not intervals_overlap(iv("B1+TB1"), iv("L1+L2"))  # Tue/Thu vs Monday lab
    assert not intervals_overlap(iv("A1+TA1"), iv("A2+TA2"))  # morning vs afternoon family
    assert intervals_overlap(iv("A1+TA1"), iv("A1+TA1+TAA1"))  # same family, different package


# ------------------------- placing offerings, eligibility -------------------- #
def test_busy_teacher_is_absent_from_the_eligible_list(db):
    fac1, fac2 = make_faculty(db), make_faculty(db)
    s1, s2 = make_subject(db, credits=3), make_subject(db, credits=3)
    slot_a = make_slot(db, "THEORY", 3, periods=[("Mon", "09:00", "09:50")])
    slot_clash = make_slot(db, "THEORY", 3, periods=[("Mon", "09:30", "10:20")])  # overlaps in time, different slot
    slot_free = make_slot(db, "THEORY", 3, periods=[("Tue", "09:00", "09:50")])
    make_class(db, s1, fac1, theory_slot=slot_a)

    res = slot_service.eligible_faculty(db, s2.id, slot_clash.id)
    assert [f["faculty_id"] for f in res["available"]] == [fac2.id]
    assert fac1.id not in [f["faculty_id"] for f in res["available"]]
    assert any(f["faculty_id"] == fac1.id and "teaches" in f["reason"] for f in res["unavailable"])
    # in a free slot both teachers are listed
    assert {f["faculty_id"] for f in slot_service.eligible_faculty(db, s2.id, slot_free.id)["available"]} == {fac1.id, fac2.id}
    # a teacher who already teaches the subject is not offered again
    assert fac1.id not in [f["faculty_id"] for f in slot_service.eligible_faculty(db, s1.id, None)["available"]]


def test_assigning_a_clashing_teacher_is_refused(db):
    fac = make_faculty(db)
    s1, s2 = make_subject(db, credits=3), make_subject(db, credits=3)
    a = make_slot(db, "THEORY", 3, periods=[("Mon", "09:00", "09:50")])
    b = make_slot(db, "THEORY", 3, periods=[("Mon", "09:30", "10:20")])
    make_class(db, s1, fac, theory_slot=a)
    with pytest.raises(ConflictError) as e:
        make_class(db, s2, fac, theory_slot=b)
    assert e.value.code == "FACULTY_CLASH"


def test_slot_must_match_subject_credits_and_pair_rules(db):
    fac = make_faculty(db)
    sub = make_subject(db, credits=3, lab_credits=1)
    t3 = make_slot(db, "THEORY", 3)
    t4 = make_slot(db, "THEORY", 4)
    lab = make_slot(db, "LAB", 1)
    with pytest.raises(ValidationFailed) as e:
        admin_service.create_offering(db, sub.id, fac.id, 5, t4.id, lab.id)
    assert e.value.code == "SLOT_MISMATCH"
    with pytest.raises(ValidationFailed) as e:  # theory+lab course needs both parts
        admin_service.create_offering(db, sub.id, fac.id, 5, t3.id, None)
    assert e.value.code == "SLOT_INCOMPLETE"
    overlapping_lab = make_slot(db, "LAB", 1, periods=[(t3.periods[0].day, t3.periods[0].start_time.strftime("%H:%M"), "23:00")])
    with pytest.raises(ValidationFailed) as e:  # the pair may not overlap itself
        admin_service.create_offering(db, sub.id, fac.id, 5, t3.id, overlapping_lab.id)
    assert e.value.code == "SLOT_SELF_CLASH"
    ok = admin_service.create_offering(db, sub.id, fac.id, 5, t3.id, lab.id)
    cls = db.get(ClassSection, ok["class_id"])
    assert (cls.theory_slot_id, cls.lab_slot_id) == (t3.id, lab.id)


def test_each_faculty_has_its_own_lab_slot_and_the_pair_is_one_unit(db):
    sub = make_subject(db, credits=3, lab_credits=1)
    f1, f2 = make_faculty(db), make_faculty(db)
    shared_lab = make_slot(db, "LAB", 1)  # two offerings may share a lab slot (they then need two lab rooms)
    c1 = make_class(db, sub, f1, capacity=5, lab_slot=shared_lab)
    c2 = make_class(db, sub, f2, capacity=5, lab_slot=shared_lab)
    make_rooms(db, lecture=2, lab=2)
    room_service.assign_rooms(db)
    db.commit()
    a, b = db.get(ClassSection, c1), db.get(ClassSection, c2)
    assert a.lab_slot_id == b.lab_slot_id and a.theory_slot_id != b.theory_slot_id
    assert a.lab_room_id and b.lab_room_id and a.lab_room_id != b.lab_room_id  # same slot => different rooms, automatically
    # one request covers theory + that faculty's lab: nothing to mix and match
    s = make_student(db)
    out = pick(db, s, sub, c1)
    assert out.request.class_id == c1


def test_slot_is_locked_once_students_are_involved(db):
    fac = make_faculty(db)
    sub = make_subject(db)
    cid = make_class(db, sub, fac, capacity=3)
    pick(db, make_student(db), sub, cid)
    other = make_slot(db, "THEORY", 3)
    with pytest.raises(ConflictError) as e:
        slot_service.set_placement(db, cid, other.id, None)
    assert e.value.code == "SLOT_LOCKED"
    with pytest.raises(ConflictError):
        admin_service.delete_offering(db, cid)


def test_rooms_are_typed_sized_and_never_double_booked(db):
    sub = make_subject(db)
    f1, f2, f3 = make_faculty(db), make_faculty(db), make_faculty(db)
    shared = make_slot(db, "THEORY", 3)
    make_class(db, sub, f1, capacity=10, theory_slot=shared)
    sub2, sub3 = make_subject(db), make_subject(db)
    make_class(db, sub2, f2, capacity=10, theory_slot=shared)
    make_rooms(db, lecture=2, lab=0, capacity=50)
    res = room_service.assign_rooms(db)
    db.commit()
    rooms = [c.room_id for c in db.scalars(select(ClassSection))]
    assert None not in rooms and len(set(rooms)) == 2  # same slot -> two different rooms
    with pytest.raises(ConflictError) as e:  # a third class in the same slot has no lecture room left
        make_class(db, sub3, f3, capacity=10, theory_slot=shared)
    assert e.value.code == "NO_ROOM"
    assert res["unassigned_class_ids"] == []


# ------------------------------ students and clashes ---------------------- #
def test_student_cannot_hold_two_overlapping_offerings(db):
    """A student who holds one class cannot request another that overlaps its time."""
    from app.models import ClassStatus
    from app.core.errors import ConflictError
    
    s_held, s_target = make_subject(db, credits=3), make_subject(db, credits=3)
    held_slot = make_slot(db, "THEORY", 3, periods=[("Mon", "09:10", "10:00")])
    clash_slot = make_slot(db, "THEORY", 3, periods=[("Mon", "09:30", "10:20")])  # overlaps held_slot
    ok_slot = make_slot(db, "THEORY", 3, periods=[("Wed", "09:00", "09:50")])  # does not overlap
    
    f1, f2, f3 = make_faculty(db), make_faculty(db), make_faculty(db)
    c_held = make_class(db, s_held, f1, 5, theory_slot=held_slot)
    c_clash = make_class(db, s_target, f2, 5, theory_slot=clash_slot)  # clashes with held
    c_ok = make_class(db, s_target, f3, 5, theory_slot=ok_slot)  # does not clash
    
    stu = make_student(db)
    reg.select_subject(db, stu.id, s_held.id)
    reg.submit_request(db, stu.id, c_held).outcome == "QUEUED"
    faculty_service.accept_next(db, f1.id, c_held)  # student now holds c_held
    
    reg.select_subject(db, stu.id, s_target.id)
    # cannot request c_clash: it overlaps with held_slot
    with pytest.raises(ConflictError) as e:
        reg.submit_request(db, stu.id, c_clash)
    assert e.value.code == "SLOT_CLASH"
    # but can request c_ok: no overlap
    assert reg.submit_request(db, stu.id, c_ok).outcome == "QUEUED"



def test_auto_assign_respects_faculty_and_pair_rules(db):
    admin = make_admin(db)
    _scheduling_world(db)
    f1, f2, f3 = make_faculty(db), make_faculty(db), make_faculty(db)
    sub1 = make_subject(db, credits=3, lab_credits=1)
    sub2 = make_subject(db, credits=4)
    sub3, sub4 = make_subject(db, credits=3), make_subject(db, credits=3)
    c_m1 = make_class(db, sub1, f1, 10, placed=False)
    c_m2 = make_class(db, sub2, f2, 10, placed=False)
    c_o1 = make_class(db, sub3, f1, 10, placed=False)  # same faculty as c_m1
    c_o2 = make_class(db, sub4, f3, 10, placed=False)
    db.commit()

    dry = timetable_service.auto_assign(db, dry_run=True)
    assert dry["status"] == "OK" and dry["to_place"] == 4 and db.get(ClassSection, c_m1).theory_slot_id is None  # nothing saved

    rep = timetable_service.auto_assign(db, admin.id)
    assert rep["status"] == "OK" and rep["to_place"] == 4
    ids = [c_m1, c_m2, c_o1, c_o2]
    assert all(db.get(ClassSection, i).theory_slot_id for i in ids) and db.get(ClassSection, c_m1).lab_slot_id
    assert not _overlap_of(db, c_m1, c_o1)  # same faculty
    assert len({db.get(ClassSection, i).theory_slot_id for i in ids}) == 4  # spread over different slots where possible
    m1 = db.get(ClassSection, c_m1)
    cache = slot_service.slot_intervals(db)
    assert not intervals_overlap(cache[m1.theory_slot_id], cache[m1.lab_slot_id])  # theory vs its own lab
    assert rep["rooms_unassigned"] == [] and m1.room_id and m1.lab_room_id
    report = timetable_service.clash_report(db)
    assert report["hard_clashes"] == [] and report["unscheduled"] == [] and report["no_room"] == []


def test_auto_assign_keeps_already_placed_offerings(db):
    admin = make_admin(db)
    _scheduling_world(db)
    f1, f2 = make_faculty(db), make_faculty(db)
    s1, s2 = make_subject(db, credits=3), make_subject(db, credits=3)
    pinned = slot_by_name(db, "A1+TA1")
    c1 = make_class(db, s1, f1, 10, theory_slot=pinned)
    c2 = make_class(db, s2, f2, 10, placed=False)
    db.commit()
    rep = timetable_service.auto_assign(db, admin.id)
    assert rep["already_placed"] == 1 and rep["to_place"] == 1
    assert db.get(ClassSection, c1).theory_slot_id == pinned.id
    assert not _overlap_of(db, c1, c2)


def test_auto_assign_reports_infeasible_and_saves_nothing(db):
    admin = make_admin(db)
    make_slot(db, "THEORY", 3, periods=[("Mon", "09:00", "09:50")])  # only ONE 3-credit slot exists
    f = make_faculty(db)
    s1, s2 = make_subject(db, credits=3), make_subject(db, credits=3)
    make_class(db, s1, f, 5, placed=False)
    c2 = make_class(db, s2, f, 5, placed=False)  # same faculty => cannot share the only slot
    with pytest.raises(ValidationFailed) as e:
        timetable_service.auto_assign(db, admin.id)
    assert e.value.code == "PLACEMENT_INFEASIBLE"
    assert db.get(ClassSection, c2).theory_slot_id is None


def test_auto_assign_without_a_slot_chart_explains_what_to_do(db):
    admin = make_admin(db)
    make_class(db, make_subject(db), make_faculty(db), 5, placed=False)
    with pytest.raises(ValidationFailed) as e:
        timetable_service.auto_assign(db, admin.id)
    assert e.value.code == "NO_SLOTS" and "slot chart" in e.value.message


def test_room_shortage_limits_parallel_classes(db):
    admin = make_admin(db)
    slot_service.load_standard_chart(db)
    make_rooms(db, lecture=1, lab=0, capacity=100)  # one lecture room: at most one class per period
    subs = [make_subject(db, credits=2) for _ in range(3)]
    cids = [make_class(db, s, make_faculty(db), 10, placed=False) for s in subs]
    db.commit()
    timetable_service.auto_assign(db, admin.id)
    assert not any(_overlap_of(db, a, b) for i, a in enumerate(cids) for b in cids[i + 1:])
    assert timetable_service.clash_report(db)["no_room"] == []


# ---------------------------- charts, views, insights ------------------------ #
def test_slot_chart_groups_alternatives_and_lists_unscheduled(db):
    f1, f2, f3 = make_faculty(db), make_faculty(db), make_faculty(db)
    s1, s2, s3 = make_subject(db), make_subject(db), make_subject(db)
    shared = make_slot(db, "THEORY", 3, name="SHARED")
    make_class(db, s1, f1, 5, theory_slot=shared)
    make_class(db, s2, f2, 5, theory_slot=shared)
    make_class(db, s3, f3, 5, placed=False)
    chart = timetable_service.slot_chart(db)
    entry = next(s for s in chart["slots"] if s["name"] == "SHARED")
    assert {o["subject_code"] for o in entry["offerings"]} == {s1.code, s2.code}  # alternatives in the same slot
    assert [u["subject_code"] for u in chart["unscheduled"]] == [s3.code]


def test_role_specific_timetable_views(db):
    fac = make_faculty(db)
    sub = make_subject(db, credits=3, lab_credits=1)
    cid = make_class(db, sub, fac, 5)
    stu, other = make_student(db), make_student(db)
    pick(db, stu, sub, cid)
    faculty_service.accept_next(db, fac.id, cid)
    mine = timetable_service.student_entries(db, stu.id)
    assert {e["component"] for e in mine} == {"THEORY", "LAB"}
    assert timetable_service.student_entries(db, other.id) == []
    assert len(timetable_service.faculty_entries(db, fac.id)) == len(mine)
    assert len(timetable_service.all_entries(db)) == len(mine)


