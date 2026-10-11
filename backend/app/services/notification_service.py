"""In-app notifications. Functions never commit - the calling service owns the transaction."""
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Notification, NotificationType, Role, User


def notify(
    db: Session,
    user_id: int,
    type_: NotificationType,
    message: str,
    dedupe_key: Optional[str] = None,
) -> Optional[Notification]:
    """Create a notification. If ``dedupe_key`` is given and an *unread* notification with the
    same key already exists for the user, nothing is created (prevents alert floods)."""
    if dedupe_key:
        existing = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.dedupe_key == dedupe_key,
                Notification.is_read.is_(False),
            )
        )
        if existing:
            return None
    n = Notification(user_id=user_id, type=type_, message=message, dedupe_key=dedupe_key)
    db.add(n)
    return n


def notify_admins(
    db: Session, type_: NotificationType, message: str, dedupe_key: Optional[str] = None
) -> int:
    admin_ids = db.scalars(select(User.id).where(User.role == Role.ADMIN, User.is_active.is_(True))).all()
    return sum(1 for uid in admin_ids if notify(db, uid, type_, message, dedupe_key))


def notify_all_with_role(db: Session, role: Role, type_: NotificationType, message: str) -> int:
    ids = db.scalars(select(User.id).where(User.role == role, User.is_active.is_(True))).all()
    for uid in ids:
        notify(db, uid, type_, message)
    return len(ids)


def list_for_user(db: Session, user_id: int, unread_only: bool = False, limit: int = 100) -> List[Notification]:
    q = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        q = q.where(Notification.is_read.is_(False))
    return list(db.scalars(q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)))


def unread_count(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
    ) or 0


def mark_read(db: Session, user_id: int, notification_id: int) -> Notification:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user_id:  # users can only touch their own notifications
        raise NotFoundError("Notification not found")
    n.is_read = True
    db.commit()
    return n


def mark_all_read(db: Session, user_id: int) -> int:
    res = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return res.rowcount or 0
