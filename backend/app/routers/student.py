from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import require_student
from app.db.database import get_db
from app.models import User
from app.schemas.schemas import CreditsUpdate, JoinRequestCreate
from app.services import registration_service as svc

router = APIRouter(prefix="/student", tags=["student"], dependencies=[Depends(require_student)])


@router.get("/profile")
def profile(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.profile(db, user.id)


@router.put("/credits")
def set_credits(body: CreditsUpdate, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.set_credits(db, user.id, body.credits)


@router.get("/subjects")
def subjects(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.list_subjects(db, user.id)


@router.post("/subjects/{subject_id}/select", status_code=201)
def select_subject(subject_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.select_subject(db, user.id, subject_id)


@router.delete("/subjects/{subject_id}/select", status_code=204)
def deselect_subject(subject_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    svc.deselect_subject(db, user.id, subject_id)


@router.get("/subjects/{subject_id}/classes")
def class_options(
    subject_id: int,
    preferred_class_id: Optional[int] = Query(default=None),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return svc.class_options(db, user.id, subject_id, preferred_class_id)


@router.get("/offerings")
def offerings(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """All scheduled offerings with their slots and clash status (group by slot to see alternatives)."""
    return svc.student_offerings(db, user.id)


@router.post("/requests")
def submit_request(body: JoinRequestCreate, user: User = Depends(require_student), db: Session = Depends(get_db)):
    out = svc.submit_request(db, user.id, body.class_id)
    payload = {
        "outcome": out.outcome,
        "message": out.message,
        "request_id": out.request.id,
        "class_id": out.request.class_id,
        "queue_position": out.queue_position,
        "suggestion": out.suggestion,
    }
    if out.outcome == "REJECTED_FULL":
        # Clear, machine-readable "class is full" answer; the student keeps the subject and can pick another faculty.
        return JSONResponse(status_code=409, content={"detail": out.message, "code": "CLASS_FULL", **payload})
    return JSONResponse(status_code=201, content=payload)


@router.get("/requests")
def requests(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return svc.list_requests(db, user.id)


@router.delete("/requests/{request_id}")
def cancel_request(request_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    svc.cancel_request(db, user.id, request_id)
    return {"cancelled": True}
