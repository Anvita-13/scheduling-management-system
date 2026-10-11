"""Sample dataset modelled on VIT's FFCS structure (everything except the faculty names, which are fake).

    python -m app.db.seed --reset                 # structure + slot optimisation + simulated registration
    python -m app.db.seed --reset --no-activity   # structure + slots only (no student requests)

What it contains
  * VIT-style slot chart: theory packages A1+TA1, B1+TB1+TBB1 ... (morning "1" / afternoon "2" families) and
    2-period lab packages L1+L2 ... L59+L60. Theory and lab slots overlap in time exactly as in the real chart.
  * VIT-style course codes: BMAT101L Calculus, BCSE202L Data Structures and Algorithms, ... The "L" course is the
    theory part; courses with a lab (the "P" part) are ONE selectable unit with their own lab slot per faculty.
  * 122 students; every student picks any subjects they like within a chosen credit load (no groups, no
    compulsory subjects).
  * Exactly two courses are offered with faculty OPTIONS: BMAT101L (4 faculty, theory only) and BCSE202L (5 faculty,
    theory + lab; each faculty has its own lab slot and two of them share one lab slot). All other courses have
    a single faculty.
  * Faculty teach 1-3 courses each; the automatic scheduler places everything else without any faculty clash.

Run ``alembic upgrade head`` first (or pass --create-tables). Demo passwords are for local use only.
"""
import argparse
import os
import random
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core.errors import DomainError
from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.models import (
    ClassSection, Faculty, Registration, RegistrationStatus, Role, Room, RoomKind, Slot, Student,
    Subject, User,
)
from app.services import (
    admin_service, allocation_service, capacity_service, faculty_service, registration_service, slot_service,
    timetable_service,
)

DEFAULT_ADMIN_PASSWORD = "Admin@123"
# Set SEED_ADMIN_PASSWORD for any deployment reachable by other people; the default is public (it is in the docs).
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@college.edu", os.environ.get("SEED_ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD
FACULTY_PASSWORD, STUDENT_PASSWORD = "Faculty@123", "Student@123"
MIN_CREDITS, MAX_CREDITS = 16, 27  # VIT-style credit range

# department code -> (display name, headcount). Faculty names are assigned from a fake-name pool.
DEPARTMENTS = {
    "CSE": ("School of Computer Science", 12), "ECE": ("School of Electronics", 4), "MAT": ("Mathematics", 4),
    "PHY": ("Physics", 1), "CHY": ("Chemistry", 1), "EEE": ("Electrical Engineering", 1),
    "HUM": ("Humanities and Languages", 2), "MGT": ("Management Studies", 1),
}
FIRST_NAMES = [
    "Aarav", "Meera", "Rohan", "Ananya", "Vikram", "Kavya", "Arjun", "Divya", "Karthik", "Lakshmi", "Suresh", "Pooja",
    "Naveen", "Ritu", "Harish", "Nisha", "Manoj", "Swati", "Rajesh", "Priya", "Sanjay", "Anita", "Deepak", "Shalini",
    "Gopal", "Radhika", "Mohan", "Sunita", "Ashok", "Vidya", "Prakash", "Neha", "Ramesh", "Geeta", "Satish", "Uma",
]
LAST_NAMES = [
    "Iyer", "Nair", "Menon", "Pillai", "Reddy", "Naidu", "Rao", "Sharma", "Verma", "Kulkarni", "Joshi", "Desai", "Patel",
    "Mehta", "Banerjee", "Chatterjee", "Das", "Bose", "Singh", "Gupta", "Krishnan", "Subramanian", "Venkatesh", "Raman",
    "Natarajan", "Balaji", "Murthy", "Hegde", "Shetty", "Kamath",
]

# code, name, teaching dept, theory credits, lab credits, seats per offering (len = number of faculty options),
# pinned placements per offering [(theory slot, lab slot)] (only for the two option courses)
COURSES: List[Dict] = [
    # ---- first year -----------------------------------------------------------------
    dict(code="BMAT101L", name="Calculus", dept="MAT", t=4, l=0, seats=[12, 12, 10, 10],
         pins=[("A1+TA1+TAA1", None), ("B1+TB1+TBB1", None), ("D2+TD2+TDD2", None), ("C2+TC2+TCC2", None)]),
    dict(code="BENG101L", name="Technical English Communication", dept="HUM", t=2, l=1, seats=[40]),
    dict(code="BPHY101L", name="Engineering Physics", dept="PHY", t=3, l=1, seats=[36]),
    dict(code="BCHY101L", name="Engineering Chemistry", dept="CHY", t=3, l=1, seats=[36]),
    dict(code="BEEE101L", name="Basic Electrical and Electronics Engineering", dept="EEE", t=3, l=1, seats=[36]),
    dict(code="BCSE101E", name="Computer Programming: Python", dept="CSE", t=2, l=2, seats=[36]),
    dict(code="BHUM101L", name="Ethics and Values", dept="HUM", t=2, l=0, seats=[40]),
    dict(code="BFRE101L", name="Foreign Language: French", dept="HUM", t=2, l=0, seats=[30]),
    dict(code="BMGT101L", name="Principles of Management", dept="MGT", t=3, l=0, seats=[40]),
    # ---- CSE semester 3 -------------------------------------------------------------
    dict(code="BCSE202L", name="Data Structures and Algorithms", dept="CSE", t=3, l=1, seats=[12, 10, 10, 8, 8],
         pins=[("C1+TC1", "L1+L2"), ("D1+TD1", "L1+L2"), ("E2+TE2", "L9+L10"), ("F2+TF2", "L33+L34"), ("G1+TG1", "L43+L44")]),
    dict(code="BMAT202L", name="Probability and Statistics", dept="MAT", t=3, l=1, seats=[60]),
    dict(code="BCSE204L", name="Design and Analysis of Algorithms", dept="CSE", t=3, l=1, seats=[30]),
    dict(code="BCSE205L", name="Computer Architecture and Organization", dept="CSE", t=3, l=0, seats=[36]),
    dict(code="BECE102L", name="Digital Systems Design", dept="ECE", t=3, l=1, seats=[30]),
    dict(code="BMAT205L", name="Discrete Mathematics", dept="MAT", t=3, l=0, seats=[40]),
    dict(code="BCSE203E", name="Web Programming", dept="CSE", t=2, l=1, seats=[30]),
    # ---- CSE semester 5 -------------------------------------------------------------
    dict(code="BCSE302L", name="Database Systems", dept="CSE", t=3, l=1, seats=[35]),
    dict(code="BCSE303L", name="Operating Systems", dept="CSE", t=3, l=1, seats=[35]),
    dict(code="BCSE304L", name="Theory of Computation", dept="CSE", t=3, l=0, seats=[30]),
    dict(code="BCSE301L", name="Software Engineering", dept="CSE", t=3, l=1, seats=[30]),
    dict(code="BCSE308L", name="Computer Networks", dept="CSE", t=3, l=1, seats=[30]),
    dict(code="BCSE306L", name="Artificial Intelligence", dept="CSE", t=3, l=1, seats=[8]),
    dict(code="BCSE307L", name="Compiler Design", dept="CSE", t=3, l=1, seats=[6]),
    dict(code="BCSE309L", name="Cryptography and Network Security", dept="CSE", t=3, l=1, seats=[12]),
    dict(code="BCSE305L", name="Embedded Systems", dept="CSE", t=3, l=0, seats=[30]),
    # ---- ECE semester 3 -------------------------------------------------------------
    dict(code="BECE204L", name="Microprocessors and Microcontrollers", dept="ECE", t=3, l=1, seats=[30]),
    dict(code="BECE203L", name="Signals and Systems", dept="ECE", t=3, l=0, seats=[30]),
    dict(code="BECE205L", name="Electromagnetic Fields and Waves", dept="ECE", t=3, l=0, seats=[30]),
    dict(code="BECE201L", name="Analog Electronic Circuits", dept="ECE", t=3, l=1, seats=[30]),
]

STUDENT_COUNT, ROLL_PREFIX = 122, "25BCE"
POPULARITY = {"BCSE306L": 3.0, "BCSE307L": 2.0, "BCSE309L": 2.0, "BCSE308L": 1.5, "BHUM101L": 0.7}


def wipe(db: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        if table.name != "alembic_version":
            db.execute(table.delete())
    db.commit()


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def build_structure(db: Session, rng: random.Random) -> None:
    admin_hash, fac_hash, stu_hash = (hash_password(p) for p in (ADMIN_PASSWORD, FACULTY_PASSWORD, STUDENT_PASSWORD))
    admin = User(name="Administrator", email=ADMIN_EMAIL, password_hash=admin_hash, role=Role.ADMIN)
    db.add(admin)

    # faculty: fake, unique names; department only in the faculty record
    names = [f"{f} {l}" for f in FIRST_NAMES for l in LAST_NAMES]
    rng.shuffle(names)
    pools: Dict[str, List[int]] = {d: [] for d in DEPARTMENTS}
    n = 0
    for dept, (dept_name, count) in DEPARTMENTS.items():
        for _ in range(count):
            full = names[n]
            title = "Dr." if n % 3 else "Prof."
            u = User(name=f"{title} {full}", email=f"{full.lower().replace(' ', '.')}@college.edu", password_hash=fac_hash, role=Role.FACULTY)
            u.faculty = Faculty(employee_code=f"E{10000 + n}", department=dept_name)
            db.add(u)
            db.flush()
            pools[dept].append(u.id)
            n += 1

    for seq in range(1, STUDENT_COUNT + 1):
        u = User(name=f"stu{seq}", email=f"stu{seq}@college.edu", password_hash=stu_hash, role=Role.STUDENT)
        u.student = Student(roll_number=f"{ROLL_PREFIX}{seq:04d}", max_credits=rng.choice([MAX_CREDITS] * 9 + [24]))
        db.add(u)

    subjects: Dict[str, Subject] = {}
    for c in COURSES:
        subjects[c["code"]] = Subject(code=c["code"], name=c["name"], credits=c["t"], lab_credits=c["l"])
    db.add_all(subjects.values())
    db.flush()
    slot_service.load_standard_chart(db)
    for i, cap in enumerate([120, 120, 90, 90, 60, 60, 60, 60, 60, 60], start=1):
        db.add(Room(name=f"LH-{100 + i}", kind=RoomKind.LECTURE, capacity=cap))
    for i in range(1, 9):
        db.add(Room(name=f"LAB-{100 + i}", kind=RoomKind.LAB, capacity=60))
    s = registration_service.get_registration_settings(db)
    s.min_credits, s.max_credits = MIN_CREDITS, MAX_CREDITS
    db.commit()

    # offerings: each department hands out its faculty round-robin, so faculty end up with 1-3 courses each
    slot_ids = {sl.name: sl.id for sl in db.scalars(select(Slot))}
    pointer = {d: 0 for d in pools}
    for c in COURSES:
        pool = pools[c["dept"]]
        chosen = [pool[(pointer[c["dept"]] + i) % len(pool)] for i in range(len(c["seats"]))]
        pointer[c["dept"]] = (pointer[c["dept"]] + len(c["seats"])) % len(pool)
        for i, fid in enumerate(chosen):
            theory = lab = None
            if c.get("pins"):
                t_name, l_name = c["pins"][i]
                theory, lab = slot_ids[t_name], (slot_ids[l_name] if l_name else None)
            admin_service.create_offering(db, subjects[c["code"]].id, fid, c["seats"][i], theory, lab)

    report = timetable_service.auto_assign(db, admin.id)  # the automatic scheduler places every remaining offering
    if report["status"] != "OK":  # pragma: no cover - would indicate a data/algorithm regression
        raise SystemExit(f"Automatic scheduling failed: {report['message']}")
    print(
        f"  slots placed: {report['to_place']} offerings (backtracks {report['backtracks']})"
    )


# --------------------------------------------------------------------------- #
# Simulated registration
# --------------------------------------------------------------------------- #
def _offering_order(rng: random.Random, offerings: List[ClassSection], weights: Dict[int, float]) -> List[ClassSection]:
    """A student's preference order over the faculty options of one subject (popularity-skewed)."""
    pool, order = list(offerings), []
    while pool:
        pick = rng.choices(pool, [weights[c.id] for c in pool])[0]
        order.append(pick)
        pool.remove(pick)
    return order


def _try_request(db: Session, student_id: int, order: List[ClassSection]) -> bool:
    for cls in order:
        try:
            out = registration_service.submit_request(db, student_id, cls.id)
        except DomainError:
            db.rollback()
            continue  # slot clash / not schedulable: the student simply looks at the next faculty option
        if out.outcome == "QUEUED":
            return True
    return False


def simulate_registration(db: Session, rng: random.Random) -> None:
    subj = {s.code: s for s in db.scalars(select(Subject))}
    offerings: Dict[int, List[ClassSection]] = {}
    for c in db.scalars(select(ClassSection).order_by(ClassSection.id)):
        offerings.setdefault(c.subject_id, []).append(c)
    weights: Dict[int, float] = {}
    for sid, cs in offerings.items():
        skew = [1.0 / (i + 1) ** 1.2 for i in range(len(cs))]
        rng.shuffle(skew)
        for c, w in zip(cs, skew):
            weights[c.id] = w * POPULARITY.get(c.subject.code, 1.0)

    students = list(db.scalars(select(Student).order_by(Student.user_id)))
    plans: Dict[int, List[Subject]] = {}
    for st in students:
        target = max(MIN_CREDITS, min(st.max_credits, rng.choice([16, 18, 20, 21, 22, 24, 27])))
        registration_service.set_credits(db, st.user_id, target)
        # popular subjects are picked more often; subjects that cannot be combined (same time) are skipped
        wanted = sorted(subj.values(), key=lambda s: -POPULARITY.get(s.code, 1.0) * rng.random())
        chosen: List[Subject] = []
        for s in wanted:
            if registration_service.committed_credits(db, st.user_id) + s.total_credits > target:
                continue
            try:
                out = registration_service.select_subject(db, st.user_id, s.id)
            except DomainError:
                db.rollback()
                continue
            chosen.append(s)
            # a subject with several faculty still needs a choice; a single-faculty subject was requested automatically
            if out["status"] == "SELECTED" and len(offerings[s.id]) > 1:
                _try_request(db, st.user_id, _offering_order(rng, offerings[s.id], weights))
        plans[st.user_id] = chosen

    # faculty process their queues in order; a few "lazy" classes leave their queue pending for the demo
    lazy = {c.id for cs in offerings.values() for c in cs if c.id % 7 == 0}

    def process_all() -> None:
        for cs in offerings.values():
            for c in cs:
                if c.id in lazy:
                    continue
                while True:
                    db.refresh(c)
                    if c.status.value != "OPEN" or not capacity_service.pending_requests_in_order(db, c.id):
                        break
                    try:
                        faculty_service.accept_next(db, c.faculty_id, c.id)
                    except DomainError:
                        db.rollback()
                        break

    process_all()
    # students turned away re-request via the Greedy suggestion (two rounds), then queues are processed again
    for _ in range(2):
        for st in students:
            for s in plans[st.user_id]:
                reg = db.scalar(select(Registration).where(Registration.student_id == st.user_id, Registration.subject_id == s.id))
                if reg is None or reg.status != RegistrationStatus.SELECTED:
                    continue
                pick = allocation_service.greedy_pick(db, s.id, student_id=st.user_id)
                if pick.selected is not None:
                    _try_request(db, st.user_id, [db.get(ClassSection, pick.selected.class_id)])
        process_all()


# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the VIT-style sample dataset")
    parser.add_argument("--reset", action="store_true", help="delete all existing application data first")
    parser.add_argument("--no-activity", action="store_true", help="structure and slots only; no student requests")
    parser.add_argument("--create-tables", action="store_true", help="create tables directly (skip Alembic)")
    parser.add_argument("--seed", type=int, default=2026, help="random seed (same seed => identical dataset)")
    args = parser.parse_args()

    if args.create_tables:
        Base.metadata.create_all(engine)
    rng = random.Random(args.seed)
    with SessionLocal() as db:
        if args.reset:
            wipe(db)
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit("Database already contains users. Use --reset to wipe it first.")
        build_structure(db, rng)
        if not args.no_activity:
            simulate_registration(db, rng)
    print("Sample dataset loaded.")
    if ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
        print(f"  Admin    : {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    else:
        print(f"  Admin    : {ADMIN_EMAIL} / (the value of SEED_ADMIN_PASSWORD)")
    print(f"  Faculty  : see Admin > People (e-mail = first.last@college.edu) / {FACULTY_PASSWORD}")
    print(f"  Students : stu1@college.edu ... / {STUDENT_PASSWORD}")


if __name__ == "__main__":
    main()
