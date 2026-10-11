"""Race-condition tests. They need real row locks, so they run only against PostgreSQL
(set TEST_DATABASE_URL); on the default in-memory SQLite run they are skipped."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.errors import ConflictError
from app.models import ClassSection, JoinRequest, RequestStatus
from app.services import faculty_service, registration_service
from tests.conftest import IS_POSTGRES
from tests.factories import make_admin, make_class, make_faculty, make_student, make_subject, pick

pytestmark = pytest.mark.skipif(not IS_POSTGRES, reason="needs PostgreSQL row-level locking")


def _run_parallel(session_factory, fn, args_list):
    def task(args):
        s = session_factory()
        try:
            return fn(s, *args)
        except ConflictError as e:
            return e
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=len(args_list)) as pool:
        return list(pool.map(task, args_list))


def test_concurrent_accepts_never_overbook_the_last_seat(db, session_factory):
    make_admin(db)
    fac = make_faculty(db)
    subj = make_subject(db)
    cid = make_class(db, subj, fac, capacity=1)
    for _ in range(8):
        pick(db, make_student(db), subj, cid)

    results = _run_parallel(
        session_factory,
        lambda s, fid, c: faculty_service.accept_next(s, fid, c),
        [(fac.id, cid)] * 8,
    )
    successes = [r for r in results if isinstance(r, JoinRequest)]
    assert len(successes) == 1
    assert all(isinstance(r, ConflictError) for r in results if r not in successes)

    db.expire_all()
    cls = db.get(ClassSection, cid)
    assert cls.enrolled_count == 1 and cls.status.value == "FULL"
    statuses = [r.status for r in db.scalars(select(JoinRequest).where(JoinRequest.class_id == cid))]
    assert statuses.count(RequestStatus.ACCEPTED) == 1


def test_concurrent_submissions_get_unique_gapless_queue_positions(db, session_factory):
    make_admin(db)
    fac = make_faculty(db)
    subj = make_subject(db)
    cid = make_class(db, subj, fac, capacity=5)
    studs = [make_student(db) for _ in range(10)]
    for s in studs:
        registration_service.select_subject(db, s.id, subj.id)

    results = _run_parallel(
        session_factory,
        lambda s, uid, c: registration_service.submit_request(s, uid, c),
        [(s.id, cid) for s in studs],
    )
    assert all(r.outcome == "QUEUED" for r in results)
    db.expire_all()
    seqs = sorted(r.queue_seq for r in db.scalars(select(JoinRequest).where(JoinRequest.class_id == cid)))
    assert seqs == list(range(1, 11))


def test_same_student_double_submit_creates_only_one_active_request(db, session_factory):
    make_admin(db)
    subj = make_subject(db)
    f1, f2 = make_faculty(db), make_faculty(db)
    c1, c2 = make_class(db, subj, f1, 3), make_class(db, subj, f2, 3)
    stu = make_student(db)
    registration_service.select_subject(db, stu.id, subj.id)

    results = _run_parallel(
        session_factory,
        lambda s, uid, c: registration_service.submit_request(s, uid, c),
        [(stu.id, c1), (stu.id, c2), (stu.id, c1), (stu.id, c2)],
    )
    assert sum(1 for r in results if not isinstance(r, Exception)) == 1
    db.expire_all()
    active = [
        r for r in db.scalars(select(JoinRequest).where(JoinRequest.student_id == stu.id))
        if r.status in (RequestStatus.PENDING, RequestStatus.ACCEPTED)
    ]
    assert len(active) == 1
