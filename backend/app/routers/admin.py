from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.database import get_db
from app.models import User
from app.schemas import schemas as s
from app.services import admin_service as svc
from app.services import capacity_service, insights_service, room_service, slot_service, timetable_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return svc.dashboard(db)


# ---- people ---------------------------------------------------------------- #
@router.get("/faculty")
def faculty(db: Session = Depends(get_db)):
    return svc.list_faculty(db)


@router.post("/faculty", status_code=201)
def create_faculty(body: s.FacultyCreate, db: Session = Depends(get_db)):
    u = svc.create_faculty(db, body.name, body.email, body.password, body.employee_code, body.department)
    return {"user_id": u.id}


@router.get("/students")
def students(db: Session = Depends(get_db)):
    return svc.list_students(db)


@router.post("/students", status_code=201)
def create_student(body: s.StudentCreate, db: Session = Depends(get_db)):
    u = svc.create_student(db, body.name, body.email, body.password, body.roll_number, body.max_credits)
    return {"user_id": u.id}


# ---- subjects and offerings (faculty + slots) -------------------------------------- #
@router.get("/subjects")
def subjects(db: Session = Depends(get_db)):
    return svc.list_subjects(db)


@router.post("/subjects", status_code=201)
def create_subject(body: s.SubjectCreate, db: Session = Depends(get_db)):
    sub = svc.create_subject(db, body.code, body.name, body.credits, body.lab_credits)
    return {"id": sub.id}


@router.put("/subjects/{subject_id}")
def update_subject(subject_id: int, body: s.SubjectUpdate, db: Session = Depends(get_db)):
    sub = svc.update_subject(db, subject_id, body.name, body.credits, body.lab_credits)
    return {"id": sub.id}


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    svc.delete_subject(db, subject_id)


@router.get("/slots")
def slots(kind: Optional[str] = Query(default=None, pattern="^(THEORY|LAB)$"), credits: Optional[int] = None, db: Session = Depends(get_db)):
    return slot_service.list_slots(db, kind, credits)


@router.post("/slots/load-standard", status_code=201)
def load_standard_slots(db: Session = Depends(get_db)):
    n = slot_service.load_standard_chart(db)
    db.commit()
    return {"created": n}


@router.get("/eligible-faculty")
def eligible_faculty(
    subject_id: int, theory_slot_id: Optional[int] = None, lab_slot_id: Optional[int] = None, db: Session = Depends(get_db)
):
    """Faculty who can take this subject in these slots: anyone teaching at an overlapping time is left out."""
    return slot_service.eligible_faculty(db, subject_id, theory_slot_id, lab_slot_id)


@router.post("/offerings", status_code=201)
def create_offering(body: s.OfferingCreate, db: Session = Depends(get_db)):
    return svc.create_offering(db, body.subject_id, body.faculty_id, body.capacity, body.theory_slot_id, body.lab_slot_id)


@router.patch("/offerings/{class_id}/slots")
def place_offering(class_id: int, body: s.PlacementUpdate, db: Session = Depends(get_db)):
    return slot_service.set_placement(db, class_id, body.theory_slot_id, body.lab_slot_id)


@router.delete("/offerings/{class_id}", status_code=204)
def delete_offering(class_id: int, db: Session = Depends(get_db)):
    svc.delete_offering(db, class_id)


# ---- seats / status of an offering ------------------------------------------------------ #
@router.get("/classes")
def classes(db: Session = Depends(get_db)):
    return svc.list_classes(db)


@router.patch("/classes/{class_id}/capacity")
def update_capacity(class_id: int, body: s.CapacityUpdate, db: Session = Depends(get_db)):
    c = capacity_service.update_capacity(db, class_id, body.capacity)
    return {"id": c.id, "capacity": c.capacity, "enrolled_count": c.enrolled_count, "status": c.status.value}


@router.post("/classes/{class_id}/close")
def close_class(class_id: int, db: Session = Depends(get_db)):
    c = capacity_service.close_class(db, class_id)
    return {"id": c.id, "status": c.status.value}


@router.post("/classes/{class_id}/reopen")
def reopen_class(class_id: int, db: Session = Depends(get_db)):
    c = capacity_service.reopen_class(db, class_id)
    return {"id": c.id, "status": c.status.value}


@router.post("/classes/{class_id}/decline-reopen")
def decline_reopen(class_id: int, db: Session = Depends(get_db)):
    """Turn down a faculty member's request to reopen a closed class (the class stays closed)."""
    c = capacity_service.decline_reopen(db, class_id)
    return {"id": c.id, "status": c.status.value}


# ---- registration period & demand ----------------------------------------------------- #
@router.get("/registration")
def registration(db: Session = Depends(get_db)):
    info = svc.registration_info(db)
    db.commit()  # persists the settings row if it was lazily created
    return info


@router.put("/registration")
def update_registration(body: s.RegistrationUpdate, db: Session = Depends(get_db)):
    return svc.update_registration(db, body.phase, body.min_credits, body.max_credits)


@router.get("/demand")
def demand(db: Session = Depends(get_db)):
    return svc.demand_report(db)


# ---- rooms (type + size only; assignment to classes is automatic) ----------------------------- #
@router.get("/rooms", response_model=List[s.RoomOut])
def rooms(db: Session = Depends(get_db)):
    return svc.list_rooms(db)


@router.post("/rooms", response_model=s.RoomOut, status_code=201)
def create_room(body: s.RoomCreate, db: Session = Depends(get_db)):
    return svc.create_room(db, body.name, body.kind, body.capacity)


@router.delete("/rooms/{room_id}", status_code=204)
def delete_room(room_id: int, db: Session = Depends(get_db)):
    svc.delete_room(db, room_id)


# ---- scheduling optimisation ----------------------------------------------------------------- #
@router.get("/slot-chart")
def slot_chart(db: Session = Depends(get_db)):
    return timetable_service.slot_chart(db)


@router.get("/scheduling/clashes")
def clashes(db: Session = Depends(get_db)):
    return timetable_service.clash_report(db)


@router.post("/scheduling/auto-assign")
def auto_assign(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Suggest and save slots for every offering that has none (placed offerings stay put)."""
    return timetable_service.auto_assign(db, admin.id)


@router.post("/scheduling/assign-rooms")
def assign_rooms(db: Session = Depends(get_db)):
    res = room_service.assign_rooms(db)
    db.commit()
    return res


@router.post("/scheduling/clear")
def clear_unlocked(db: Session = Depends(get_db)):
    """Un-place offerings with no enrolled/waiting students so they can be re-optimised."""
    return {"cleared": timetable_service.clear_unlocked(db)}


# ---- algorithm insights (read-only demo / planning) --------------------------------------------- #
@router.get("/insights/fifo/{class_id}")
def insight_fifo(class_id: int, db: Session = Depends(get_db)):
    return insights_service.fifo_insight(db, class_id)


@router.get("/insights/greedy")
def insight_greedy(
    subject_id: int,
    student_id: Optional[int] = Query(default=None),
    preferred_class_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    return insights_service.greedy_insight(db, subject_id, student_id, preferred_class_id)


@router.get("/insights/graph-coloring")
def insight_coloring(db: Session = Depends(get_db)):
    return insights_service.coloring_insight(db)


@router.get("/insights/max-flow")
def insight_max_flow(db: Session = Depends(get_db)):
    return insights_service.max_flow_report(db)


@router.post("/insights/max-flow/run")
def run_max_flow(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Same report, but recorded in the algorithm-run history."""
    return insights_service.run_and_record_max_flow(db, admin.id)


@router.get("/algorithm-runs")
def algorithm_runs(db: Session = Depends(get_db)):
    return insights_service.recent_runs(db)
