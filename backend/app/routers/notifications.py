from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.models import User
from app.schemas.schemas import NotificationOut
from app.services import notification_service as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [
        NotificationOut(id=n.id, type=n.type.value, message=n.message, is_read=n.is_read, created_at=n.created_at)
        for n in svc.list_for_user(db, user.id, unread_only)
    ]


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unread": svc.unread_count(db, user.id)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.mark_read(db, user.id, notification_id)
    return {"read": True}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"updated": svc.mark_all_read(db, user.id)}
