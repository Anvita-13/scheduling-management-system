"""Account settings for every role: change your display name, sign-in e-mail and password."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, ValidationFailed
from app.core.security import hash_password, verify_password
from app.models import User


def _require_changes_allowed() -> None:
    if settings.LOCK_ACCOUNT_CHANGES:
        raise ForbiddenError(
            "Account changes are switched off on this shared demo, so that everyone can keep signing in with the sample accounts.",
            code="ACCOUNT_CHANGES_LOCKED",
        )


def _require_current_password(user: User, current_password: Optional[str]) -> None:
    if not current_password or not verify_password(current_password, user.password_hash):
        raise ValidationFailed("Your current password is not correct.", code="WRONG_PASSWORD")


def update_profile(
    db: Session, user: User, name: Optional[str], email: Optional[str], current_password: Optional[str]
) -> User:
    _require_changes_allowed()
    new_email = email.lower() if email else None
    changing_email = new_email is not None and new_email != user.email
    if changing_email:
        _require_current_password(user, current_password)  # the e-mail is the sign-in name, so confirm it is you
        if db.scalar(select(User.id).where(User.email == new_email, User.id != user.id)):
            raise ConflictError("Another account already uses this e-mail address.", code="EMAIL_TAKEN")
        user.email = new_email
    if name is not None and name.strip():
        user.name = name.strip()
    db.commit()
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    _require_changes_allowed()
    _require_current_password(user, current_password)
    if new_password == current_password:
        raise ValidationFailed("Your new password must be different from the current one.", code="SAME_PASSWORD")
    user.password_hash = hash_password(new_password)
    db.commit()
