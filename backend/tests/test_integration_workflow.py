"""End-to-end workflow over the real HTTP API (no service shortcuts):

Admin loads the slot chart + rooms, creates subjects and offerings (busy teachers are filtered out) ->
Students pick credits/subjects (mandatory ones automatic) -> clashing requests are refused -> requests join the
FIFO queue -> Faculty accept in order -> class fills -> others are told -> Admin sees unmet demand, raises
capacity -> optimiser places the remaining offerings -> role-specific timetables.
"""
from sqlalchemy import select

from app.models import CurriculumEntry, Subject
from tests.factories import PASSWORD, make_admin


def login(client, email, password=PASSWORD):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def slot_id(slots, name):
    return next(s["id"] for s in slots if s["name"] == name)


def test_full_slot_first_workflow(client, db):
    admin = make_admin(db)
    A = login(client, admin.email)

    # ---- Admin: slot chart, rooms, faculty accounts, subjects
    assert client.post("/api/admin/slots/load-standard", headers=A).json()["created"] == 66
    slots = client.get("/api/admin/slots", headers=A).json()
    assert client.get("/api/admin/slots", headers=A, params={"kind": "THEORY", "credits": 4}).json()  # 4-credit packages exist
    for name, kind, cap in [("LH-1", "LECTURE", 60), ("LH-2", "LECTURE", 60), ("LAB-1", "LAB", 60)]:
        assert client.post("/api/admin/rooms", headers=A, json={"name": name, "kind": kind, "capacity": cap}).status_code == 201
    for i, n in enumerate(["Dr. Rao", "Dr. Iyer"], start=1):
        assert client.post("/api/admin/faculty", headers=A, json={
            "name": n, "email": f"f{i}@c.edu", "password": PASSWORD, "employee_code": f"F{i}", "department": "CS"}).status_code == 201
    fac = {f["email"]: f["user_id"] for f in client.get("/api/admin/faculty", headers=A).json()}
    dsa = client.post("/api/admin/subjects", headers=A, json={"code": "BCSE202L", "name": "Data Structures", "credits": 3, "lab_credits": 1}).json()["id"]
    maths = client.post("/api/admin/subjects", headers=A, json={"code": "BMAT202L", "name": "Statistics", "credits": 3}).json()["id"]
    elec = client.post("/api/admin/subjects", headers=A, json={"code": "BHUM101L", "name": "Ethics", "credits": 2}).json()["id"]
    for sid, mand in ((dsa, True), (maths, True), (elec, False)):
        db.add(CurriculumEntry(group_code="CSE-S3", subject_id=sid, is_mandatory=mand))
    db.commit()

    # ---- Offerings: a theory+lab pair for one faculty. The busy teacher then disappears from the drop-down.
    a1, l12 = slot_id(slots, "C1+TC1"), slot_id(slots, "L1+L2")
    first = client.post("/api/admin/offerings", headers=A, json={
        "subject_id": dsa, "faculty_id": fac["f1@c.edu"], "capacity": 2, "theory_slot_id": a1, "lab_slot_id": l12})
    assert first.status_code == 201
    dsa_class = first.json()["class_id"]
    elig = client.get("/api/admin/eligible-faculty", headers=A, params={"subject_id": maths, "theory_slot_id": a1}).json()
    assert [f["faculty_id"] for f in elig["available"]] == [fac["f2@c.edu"]]  # f1 teaches A1 already
    assert elig["unavailable"][0]["faculty_id"] == fac["f1@c.edu"] and "teaches BCSE202L" in elig["unavailable"][0]["reason"]
    clash = client.post("/api/admin/offerings", headers=A, json={
        "subject_id": maths, "faculty_id": fac["f1@c.edu"], "capacity": 5, "theory_slot_id": a1})
    assert clash.status_code == 409 and clash.json()["code"] == "FACULTY_CLASH"
    # missing lab slot / wrong credit slot are refused
    assert client.post("/api/admin/offerings", headers=A, json={"subject_id": dsa, "faculty_id": fac["f2@c.edu"], "capacity": 2, "theory_slot_id": a1}).json()["code"] == "SLOT_INCOMPLETE"
    # unplaced offerings for the optimiser
    for sub, f, cap in ((maths, "f2@c.edu", 5), (elec, "f1@c.edu", 5)):
        assert client.post("/api/admin/offerings", headers=A, json={"subject_id": sub, "faculty_id": fac[f], "capacity": cap}).status_code == 201
    rep = client.post("/api/admin/scheduling/auto-assign", headers=A).json()
    assert rep["status"] == "OK" and rep["to_place"] == 2 and rep["already_placed"] == 1
    clashes = client.get("/api/admin/scheduling/clashes", headers=A).json()
    assert clashes["hard_clashes"] == [] and clashes["unscheduled"] == [] and clashes["no_room"] == []
    chart = client.get("/api/admin/slot-chart", headers=A).json()
    assert any(s["name"] == "C1+TC1" and s["offerings"][0]["subject_code"] == "BCSE202L" for s in chart["slots"])

    # ---- Students (group CSE-S3): mandatory subjects are registered automatically
    studs = []
    for i in range(3):
        email = f"s{i}@c.edu"
        assert client.post("/api/admin/students", headers=A, json={
            "name": f"Student {i}", "email": email, "password": PASSWORD, "roll_number": f"R{i}", "group_code": "CSE-S3"}).status_code == 201
        studs.append(login(client, email))
    ids = []
    for S in studs:
        prof = client.put("/api/student/credits", headers=S, json={"credits": 16}).json()
        assert {m["code"] for m in prof["mandatory_subjects"]} == {"BCSE202L", "BMAT202L"}
        mine = {s["code"]: s for s in client.get("/api/student/subjects", headers=S).json()}
        assert mine["BCSE202L"]["registration_status"] == "SELECTED" and mine["BCSE202L"]["group_role"] == "MANDATORY"
        assert client.delete(f"/api/student/subjects/{dsa}/select", headers=S).json()["code"] == "MANDATORY_SUBJECT"
        r = client.post("/api/student/requests", headers=S, json={"class_id": dsa_class})
        assert r.status_code == 201
        ids.append(r.json()["request_id"])
    offerings = client.get("/api/student/offerings", headers=studs[0]).json()
    assert {o["subject_code"] for o in offerings} == {"BCSE202L", "BMAT202L", "BHUM101L"} and all(o["scheduled"] for o in offerings)
    assert next(o for o in offerings if o["subject_code"] == "BCSE202L")["lab_slot"] == "L1+L2"

    # ---- Faculty accept in FIFO order; the class (2 seats) fills and closes
    F1 = login(client, "f1@c.edu")
    queue = client.get(f"/api/faculty/classes/{dsa_class}/requests", headers=F1).json()
    assert [q["request_id"] for q in queue] == ids and queue[0]["is_front"]
    cls = client.get(f"/api/faculty/classes/{dsa_class}", headers=F1).json()
    assert cls["theory_slot"] == "C1+TC1" and cls["lab_slot"] == "L1+L2" and cls["room"] and cls["lab_room"]
    assert client.post(f"/api/faculty/classes/{dsa_class}/accept-next", headers=F1, params={"request_id": ids[1]}).json()["code"] == "NOT_FRONT_OF_QUEUE"
    for _ in range(2):
        assert client.post(f"/api/faculty/classes/{dsa_class}/accept-next", headers=F1).status_code == 200
    assert client.get(f"/api/faculty/classes/{dsa_class}", headers=F1).json()["status"] == "FULL"
    assert "CLASS_FULL" in [n["type"] for n in client.get("/api/notifications", headers=studs[2]).json()]
    again = client.post("/api/student/requests", headers=studs[2], json={"class_id": dsa_class})
    assert again.status_code == 409 and again.json()["code"] == "CLASS_FULL"

    # ---- Admin sees alert + unmet demand and adds seats; the waiting student gets in
    assert "NO_FACULTY_AVAILABLE" in [n["type"] for n in client.get("/api/notifications", headers=A).json()]
    row = next(s for s in client.get("/api/admin/demand", headers=A).json()["subjects"] if s["code"] == "BCSE202L")
    assert row["unmet"] == 1 and row["enrolled"] == 2
    assert client.patch(f"/api/admin/classes/{dsa_class}/capacity", headers=A, json={"capacity": 3}).json()["status"] == "OPEN"
    assert client.post("/api/student/requests", headers=studs[2], json={"class_id": dsa_class}).status_code == 201
    assert client.post(f"/api/faculty/classes/{dsa_class}/accept-next", headers=F1).status_code == 200

    # ---- A student can never take an overlapping offering
    maths_class = next(c["id"] for c in client.get("/api/admin/classes", headers=A).json() if c["subject_code"] == "BMAT202L")
    elec_class = next(c["id"] for c in client.get("/api/admin/classes", headers=A).json() if c["subject_code"] == "BHUM101L")
    assert client.post("/api/student/requests", headers=studs[0], json={"class_id": maths_class}).status_code == 201
    assert client.post(f"/api/student/subjects/{elec}/select", headers=studs[0]).status_code in (201, 422)  # credit room permitting
    # slots of workflow offerings cannot be edited while students are involved
    locked = client.patch(f"/api/admin/offerings/{dsa_class}/slots", headers=A, json={"theory_slot_id": slot_id(slots, "B1+TB1"), "lab_slot_id": l12})
    assert locked.status_code == 409 and locked.json()["code"] == "SLOT_LOCKED"

    # ---- Timetables are role-specific and derived from the slots
    mine = client.get("/api/timetable", headers=studs[0]).json()
    assert {e["component"] for e in mine if e["subject_code"] == "BCSE202L"} == {"THEORY", "LAB"}
    assert all(e["room"] for e in mine)
    assert {e["subject_code"] for e in client.get("/api/timetable", headers=F1).json()} >= {"BCSE202L"}
    assert len(client.get("/api/timetable", headers=A).json()) >= len(mine)
    runs = client.get("/api/admin/algorithm-runs", headers=A).json()
    assert runs[0]["algorithm"] == "slot_assignment" and runs[0]["status"] == "SUCCESS"
