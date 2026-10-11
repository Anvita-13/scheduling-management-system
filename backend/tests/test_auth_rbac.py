import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from tests.factories import PASSWORD, headers, make_admin, make_class, make_faculty, make_student, make_subject


def test_passwords_are_hashed_not_stored_plaintext(db):
    u = make_student(db)
    assert u.password_hash != PASSWORD and u.password_hash.startswith("$2")
    assert verify_password(PASSWORD, u.password_hash) and not verify_password("wrong", u.password_hash)
    assert hash_password("x") != hash_password("x")  # salted


def test_login_success_and_failure(client, db):
    u = make_faculty(db)
    ok = client.post("/api/auth/login", json={"email": u.email, "password": PASSWORD})
    assert ok.status_code == 200
    body = ok.json()
    assert body["user"]["role"] == "FACULTY" and "password" not in str(body)
    assert client.post("/api/auth/login", json={"email": u.email, "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ghost@t.edu", "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"}).status_code == 422


def test_me_requires_a_valid_token(client, db):
    u = make_student(db)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/auth/me", headers=headers(u)).json()["email"] == u.email


def test_expired_and_forged_tokens_are_rejected(client, db):
    u = make_student(db)
    expired = create_access_token(u.id, "STUDENT", expires_minutes=-5)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged = jwt.encode({"sub": str(u.id), "role": "ADMIN"}, "some-other-secret", algorithm="HS256")
    assert client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_role_claim_must_match_database_role(client, db):
    u = make_student(db)
    escalated = create_access_token(u.id, "ADMIN")  # validly signed but claims a role the user does not have
    assert client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {escalated}"}).status_code == 401


ADMIN_ROUTES = [("get", "/api/admin/dashboard"), ("get", "/api/admin/subjects"), ("get", "/api/admin/demand"),
                ("get", "/api/admin/insights/max-flow"), ("post", "/api/admin/scheduling/auto-assign")]
FACULTY_ROUTES = [("get", "/api/faculty/dashboard"), ("get", "/api/faculty/classes")]
STUDENT_ROUTES = [("get", "/api/student/profile"), ("get", "/api/student/subjects"), ("get", "/api/student/requests")]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES + FACULTY_ROUTES + STUDENT_ROUTES)
def test_every_protected_route_requires_authentication(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_roles_cannot_reach_each_others_routes(client, db):
    admin, fac, stu = make_admin(db), make_faculty(db), make_student(db)
    matrix = {
        "ADMIN": (admin, FACULTY_ROUTES + STUDENT_ROUTES),
        "FACULTY": (fac, ADMIN_ROUTES + STUDENT_ROUTES),
        "STUDENT": (stu, ADMIN_ROUTES + FACULTY_ROUTES),
    }
    for _role, (user, forbidden) in matrix.items():
        for method, path in forbidden:
            r = getattr(client, method)(path, headers=headers(user))
            assert r.status_code == 403, f"{_role} reached {path}"
    assert client.get("/api/admin/dashboard", headers=headers(admin)).status_code == 200
    assert client.get("/api/faculty/dashboard", headers=headers(fac)).status_code == 200
    assert client.get("/api/student/profile", headers=headers(stu)).status_code == 200


def test_faculty_cannot_manage_other_faculty_class_via_api(client, db):
    owner, other = make_faculty(db), make_faculty(db)
    cid = make_class(db, make_subject(db), owner)
    for method, path in [("get", f"/api/faculty/classes/{cid}"), ("post", f"/api/faculty/classes/{cid}/accept-next"),
                         ("post", f"/api/faculty/classes/{cid}/close")]:
        assert getattr(client, method)(path, headers=headers(other)).status_code == 403
    assert client.get(f"/api/faculty/classes/{cid}", headers=headers(owner)).status_code == 200


def test_students_only_see_their_own_data(client, db):
    a, b = make_student(db), make_student(db)
    subj = make_subject(db)
    make_class(db, subj, make_faculty(db))
    assert client.post(f"/api/student/subjects/{subj.id}/select", headers=headers(a)).status_code == 201
    assert client.get("/api/student/requests", headers=headers(b)).json() == []
    other_subjects = client.get("/api/student/subjects", headers=headers(b)).json()
    assert all(not s["selected"] for s in other_subjects)
    # cannot read the class options of a subject the student has not selected
    assert client.get(f"/api/student/subjects/{subj.id}/classes", headers=headers(b)).status_code == 422


def test_users_only_read_their_own_notifications(client, db):
    from app.services import notification_service as ns
    from app.models import NotificationType

    a, b = make_student(db), make_student(db)
    n = ns.notify(db, a.id, NotificationType.INFO, "hello a")
    db.commit()
    assert [x["message"] for x in client.get("/api/notifications", headers=headers(a)).json()] == ["hello a"]
    assert client.get("/api/notifications", headers=headers(b)).json() == []
    assert client.post(f"/api/notifications/{n.id}/read", headers=headers(b)).status_code == 404
    assert client.post(f"/api/notifications/{n.id}/read", headers=headers(a)).status_code == 200
    assert client.get("/api/notifications/unread-count", headers=headers(a)).json() == {"unread": 0}


def test_input_validation_rejects_bad_payloads(client, db):
    admin = make_admin(db)
    h = headers(admin)
    assert client.post("/api/admin/subjects", json={"code": "X", "name": "n", "credits": 99}, headers=h).status_code == 422
    assert client.post("/api/admin/subjects", json={"code": "OK1", "name": "Valid", "credits": 3}, headers=h).status_code == 201
    assert client.post("/api/admin/subjects", json={"code": "OK1", "name": "Dup", "credits": 3}, headers=h).status_code == 409
    assert client.patch("/api/admin/classes/1/capacity", json={"capacity": -5}, headers=h).status_code == 422
