import pytest
from sqlalchemy import select

from app.core.errors import ConflictError, ForbiddenError, ValidationFailed
from app.models import (
    ClassSection, ClassStatus, JoinRequest, Notification, NotificationType, Registration,
    RegistrationStatus, RequestStatus, Role, User,
)
from app.services import admin_service, capacity_service, faculty_service, registration_service as reg
from tests.factories import make_admin, make_class, make_faculty, make_student, make_subject, pick


def notes(db, user_id, type_=None):
    q = select(Notification).where(Notification.user_id == user_id)
    if type_:
        q = q.where(Notification.type == type_)
    return list(db.scalars(q))


@pytest.fixture()
def world(db):
    admin = make_admin(db)
    fac = make_faculty(db)
    subj = make_subject(db, "CS101", 3)
    cid = make_class(db, subj, fac, capacity=2)
    return dict(admin=admin, fac=fac, subj=subj, cid=cid)


# ----------------------------- credits & subjects ---------------------------- #
def test_credit_range_is_enforced(db, world):
    s = make_student(db, credits=None)
    with pytest.raises(ValidationFailed) as e:
        reg.set_credits(db, s.id, 40)
    assert e.value.code == "CREDITS_OUT_OF_RANGE"
    with pytest.raises(ValidationFailed):
        reg.set_credits(db, s.id, 5)
    assert reg.set_credits(db, s.id, 15)["selected_credits"] == 15


def test_student_max_credits_caps_the_range(db, world):
    s = make_student(db, credits=None, max_credits=18)
    with pytest.raises(ValidationFailed):
        reg.set_credits(db, s.id, 20)


def test_cannot_select_subjects_before_credits_or_beyond_load(db, world):
    s = make_student(db, credits=None)
    with pytest.raises(ValidationFailed) as e:
        reg.select_subject(db, s.id, world["subj"].id)
    assert e.value.code == "CREDITS_NOT_SET"
    reg.set_credits(db, s.id, 12)
    extra = [make_subject(db, credits=6) for _ in range(3)]
    reg.select_subject(db, s.id, extra[0].id)
    reg.select_subject(db, s.id, extra[1].id)  # 12 / 12
    with pytest.raises(ValidationFailed) as e:
        reg.select_subject(db, s.id, extra[2].id)
    assert e.value.code == "CREDIT_LIMIT_EXCEEDED"


def test_same_subject_cannot_be_registered_twice(db, world):
    s = make_student(db)
    reg.select_subject(db, s.id, world["subj"].id)
    with pytest.raises(ConflictError) as e:
        reg.select_subject(db, s.id, world["subj"].id)
    assert e.value.code == "ALREADY_REGISTERED"


def test_registration_closed_blocks_everything(db, world):
    s = make_student(db)
    reg.select_subject(db, s.id, world["subj"].id)
    admin_service.update_registration(db, "CLOSED", None, None)
    with pytest.raises(ConflictError) as e:
        reg.submit_request(db, s.id, world["cid"])
    assert e.value.code == "REGISTRATION_CLOSED"


# ------------------------------------ FIFO ------------------------------------ #
def test_requests_queue_in_arrival_order_with_positions(db, world):
    studs = [make_student(db) for _ in range(3)]
    outs = [pick(db, s, world["subj"], world["cid"]) for s in studs]
    assert [o.queue_position for o in outs] == [1, 2, 3]
    queue = capacity_service.pending_requests_in_order(db, world["cid"])
    assert [r.student_id for r in queue] == [s.id for s in studs]
    assert [r.queue_seq for r in queue] == [1, 2, 3]
    # faculty is told about every new request
    assert len(notes(db, world["fac"].id, NotificationType.NEW_JOIN_REQUEST)) == 3


def test_queue_order_survives_a_new_session_and_cancellation(db, world, session_factory):
    a, b, c = (make_student(db) for _ in range(3))
    ra, rb, rc = (pick(db, s, world["subj"], world["cid"]) for s in (a, b, c))
    reg.cancel_request(db, b.id, rb.request.id)
    fresh = session_factory()  # simulates a server restart: order comes from the database only
    order = [r.student_id for r in capacity_service.pending_requests_in_order(fresh, world["cid"])]
    assert order == [a.id, c.id]
    assert reg.queue_position(fresh, fresh.get(JoinRequest, rc.request.id)) == 2
    fresh.close()


def test_student_has_one_active_request_per_subject(db, world):
    fac2 = make_faculty(db)
    cid2 = make_class(db, world["subj"], fac2, capacity=2)
    s = make_student(db)
    pick(db, s, world["subj"], world["cid"])
    with pytest.raises(ConflictError) as e:
        reg.submit_request(db, s.id, cid2)
    assert e.value.code == "REQUEST_ALREADY_PENDING"
    # cancel -> choose another faculty
    req = db.scalar(select(JoinRequest).where(JoinRequest.student_id == s.id))
    reg.cancel_request(db, s.id, req.id)
    assert reg.submit_request(db, s.id, cid2).outcome == "QUEUED"


# ---------------------------- faculty acceptance -------------------------------- #
def test_faculty_accepts_strictly_from_the_front(db, world):
    a, b = make_student(db), make_student(db)
    pick(db, a, world["subj"], world["cid"])
    rb = pick(db, b, world["subj"], world["cid"])
    # trying to accept the second request first is refused
    with pytest.raises(ConflictError) as e:
        faculty_service.accept_next(db, world["fac"].id, world["cid"], expected_request_id=rb.request.id)
    assert e.value.code == "NOT_FRONT_OF_QUEUE"
    first = faculty_service.accept_next(db, world["fac"].id, world["cid"])
    assert first.student_id == a.id
    assert reg._registration(db, a.id, world["subj"].id).status == RegistrationStatus.ENROLLED
    assert notes(db, a.id, NotificationType.REQUEST_ACCEPTED)


def test_class_becomes_full_closes_and_notifies_waiting_students(db, world):
    a, b, c, d = (make_student(db) for _ in range(4))
    for s in (a, b, c, d):
        pick(db, s, world["subj"], world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])  # capacity 2 reached

    cls = db.get(ClassSection, world["cid"])
    db.refresh(cls)
    assert cls.enrolled_count == 2 and cls.status == ClassStatus.FULL
    # the two students who got the seats stay ACCEPTED (the full-class drain must not touch them)
    for s in (a, b):
        req = db.scalar(select(JoinRequest).where(JoinRequest.student_id == s.id))
        assert req.status == RequestStatus.ACCEPTED
        assert reg._registration(db, s.id, world["subj"].id).status == RegistrationStatus.ENROLLED
        assert not notes(db, s.id, NotificationType.CLASS_FULL)
    # remaining queue drained, in order, with a CLASS_FULL notification each
    for s in (c, d):
        assert notes(db, s.id, NotificationType.CLASS_FULL)
        assert reg._registration(db, s.id, world["subj"].id).status == RegistrationStatus.SELECTED
    assert not capacity_service.pending_requests_in_order(db, world["cid"])
    # class closed -> faculty & admin are told; no other faculty => admin alert
    assert notes(db, world["fac"].id, NotificationType.CLASS_CLOSED)
    assert notes(db, world["admin"].id, NotificationType.NO_FACULTY_AVAILABLE)
    # faculty can no longer accept
    with pytest.raises(ConflictError):
        faculty_service.accept_next(db, world["fac"].id, world["cid"])


def test_new_request_to_full_class_is_rejected_with_reason_and_suggestion(db, world):
    fac2 = make_faculty(db)
    cid2 = make_class(db, world["subj"], fac2, capacity=5)
    a, b, late = make_student(db), make_student(db), make_student(db)
    pick(db, a, world["subj"], world["cid"])
    pick(db, b, world["subj"], world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])

    out = pick(db, late, world["subj"], world["cid"])
    assert out.outcome == "REJECTED_FULL"
    assert "full" in out.message
    assert out.suggestion["class_id"] == cid2  # Greedy Faculty Allocation's pick
    stored = db.get(JoinRequest, out.request.id)
    assert stored.status == RequestStatus.REJECTED and stored.decision_reason == "CLASS_FULL"
    assert notes(db, late.id, NotificationType.CLASS_FULL)
    # the student keeps the subject and can immediately choose the other faculty
    assert reg.submit_request(db, late.id, cid2).outcome == "QUEUED"
    # since another faculty has seats, admin is NOT alerted
    assert not notes(db, world["admin"].id, NotificationType.NO_FACULTY_AVAILABLE)


def test_no_faculty_available_alerts_admin_when_student_selects_subject(db, world):
    a, b, late = make_student(db), make_student(db), make_student(db)
    pick(db, a, world["subj"], world["cid"])
    pick(db, b, world["subj"], world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    for n in notes(db, world["admin"].id):
        n.is_read = True  # admin has read earlier alerts
    db.commit()
    out = pick(db, late, world["subj"], world["cid"])
    assert out.outcome == "REJECTED_FULL" and "No other faculty" in out.message
    assert notes(db, world["admin"].id, NotificationType.NO_FACULTY_AVAILABLE)


def test_faculty_reject_next_and_close_class(db, world):
    a, b = make_student(db), make_student(db)
    pick(db, a, world["subj"], world["cid"])
    pick(db, b, world["subj"], world["cid"])
    rej = faculty_service.reject_next(db, world["fac"].id, world["cid"])
    assert rej.student_id == a.id and rej.status == RequestStatus.REJECTED
    assert notes(db, a.id, NotificationType.REQUEST_REJECTED)
    faculty_service.close_class(db, world["fac"].id, world["cid"])
    cls = db.get(ClassSection, world["cid"])
    assert cls.status == ClassStatus.CLOSED
    assert notes(db, b.id, NotificationType.CLASS_CLOSED)  # waiting student told the class closed
    out = pick(db, make_student(db), world["subj"], world["cid"])
    assert out.outcome == "REJECTED_FULL"


def test_faculty_cannot_touch_another_faculty_class(db, world):
    other = make_faculty(db)
    with pytest.raises(ForbiddenError):
        faculty_service.class_detail(db, other.id, world["cid"])
    with pytest.raises(ForbiddenError):
        faculty_service.accept_next(db, other.id, world["cid"])
    with pytest.raises(ForbiddenError):
        faculty_service.close_class(db, other.id, world["cid"])


def test_enrolled_count_never_exceeds_capacity(db, world):
    studs = [make_student(db) for _ in range(5)]
    for s in studs:
        pick(db, s, world["subj"], world["cid"])
    for _ in range(5):
        try:
            faculty_service.accept_next(db, world["fac"].id, world["cid"])
        except ConflictError:
            pass
    cls = db.get(ClassSection, world["cid"])
    db.refresh(cls)
    assert cls.enrolled_count == cls.capacity == 2
    assert db.scalar(select(ClassSection.enrolled_count)) <= db.scalar(select(ClassSection.capacity))


# ---------------------------- admin capacity adjustment --------------------------- #
def test_admin_capacity_increase_reopens_full_class_and_notifies(db, world):
    a, b, waiting = make_student(db), make_student(db), make_student(db)
    pick(db, a, world["subj"], world["cid"])
    pick(db, b, world["subj"], world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    pick(db, waiting, world["subj"], world["cid"])  # turned away: class is full

    cls = capacity_service.update_capacity(db, world["cid"], 4)
    assert cls.status == ClassStatus.OPEN and cls.remaining == 2
    assert notes(db, world["fac"].id, NotificationType.CAPACITY_INCREASED)
    assert notes(db, waiting.id, NotificationType.CAPACITY_INCREASED)  # unmet student told a seat is available
    # the subject has a single faculty, so the waiting student was put in the queue automatically
    with pytest.raises(ConflictError) as e:
        reg.submit_request(db, waiting.id, world["cid"])
    assert e.value.code == "REQUEST_ALREADY_PENDING"
    assert [r.student_id for r in capacity_service.pending_requests_in_order(db, world["cid"])] == [waiting.id]


def test_admin_cannot_set_capacity_below_enrolled(db, world):
    a, b = make_student(db), make_student(db)
    pick(db, a, world["subj"], world["cid"])
    pick(db, b, world["subj"], world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    with pytest.raises(ConflictError) as e:
        capacity_service.update_capacity(db, world["cid"], 1)
    assert e.value.code == "CAPACITY_BELOW_ENROLLED"
    with pytest.raises(ValidationFailed):
        capacity_service.update_capacity(db, world["cid"], -1)


def test_admin_demand_report_counts_unmet_students(db, world):
    a, b, c = make_student(db), make_student(db), make_student(db)
    for s in (a, b, c):
        pick(db, s, world["subj"], world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])
    faculty_service.accept_next(db, world["fac"].id, world["cid"])  # c drained => unmet
    report = admin_service.demand_report(db)
    row = next(r for r in report["subjects"] if r["code"] == "CS101")
    assert (row["demand"], row["enrolled"], row["unmet"], row["turned_away"]) == (3, 2, 1, 1)
    assert row["no_faculty_available"] is True
    assert [w["student_id"] for w in report["waitlist"]] == [c.id]
