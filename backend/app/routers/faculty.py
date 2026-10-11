from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_faculty
from app.db.database import get_db
from app.models import User
from app.services import faculty_service as svc

router = APIRouter(prefix="/faculty", tags=["faculty"], dependencies=[Depends(require_faculty)])


@router.get("/dashboard")
def dashboard(user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    return svc.dashboard(db, user.id)


@router.get("/classes")
def classes(user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    return svc.list_classes(db, user.id)


@router.get("/classes/{class_id}")
def class_detail(class_id: int, user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    """Class summary + pending requests in FIFO order + accepted students."""
    return svc.class_detail(db, user.id, class_id)


@router.get("/classes/{class_id}/requests")
def pending_requests(class_id: int, user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    return svc.class_detail(db, user.id, class_id)["queue"]


@router.get("/classes/{class_id}/students")
def accepted_students(class_id: int, user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    return svc.accepted_students(db, user.id, class_id)


@router.post("/classes/{class_id}/accept-next")
def accept_next(
    class_id: int,
    request_id: Optional[int] = None,
    user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
):
    """Accept the request at the FRONT of the queue. If ``request_id`` is given it must be the front."""
    req = svc.accept_next(db, user.id, class_id, request_id)
    return {"accepted_request_id": req.id, "student_id": req.student_id}


@router.post("/classes/{class_id}/reject-next")
def reject_next(
    class_id: int,
    request_id: Optional[int] = None,
    user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
):
    req = svc.reject_next(db, user.id, class_id, request_id)
    return {"rejected_request_id": req.id, "student_id": req.student_id}


@router.post("/classes/{class_id}/close")
def close_class(class_id: int, user: User = Depends(require_faculty), db: Session = Depends(get_db)):
    cls = svc.close_class(db, user.id, class_id)
    return {"id": cls.id, "status": cls.status.value}
