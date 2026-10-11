from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models import Role, User
from app.services import timetable_service as svc

router = APIRouter(prefix="/timetable", tags=["timetable"])


@router.get("")
def my_timetable(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Role-specific weekly view: admin sees all placed offerings, faculty their own, students their enrolments."""
    if user.role == Role.ADMIN:
        return svc.all_entries(db)
    if user.role == Role.FACULTY:
        return svc.faculty_entries(db, user.id)
    return svc.student_entries(db, user.id)
