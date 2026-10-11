from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password, hash_password
from app.db.database import get_db
from app.models import User
from app.schemas.schemas import LoginRequest, PasswordChange, ProfileUpdate, TokenResponse, UserOut
from app.services import account_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the e-mail is unknown, so response time does not reveal which e-mails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, user=UserOut(id=user.id, name=user.name, email=user.email, role=user.role.value))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, name=user.name, email=user.email, role=user.role.value)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change your display name and/or sign-in e-mail (changing the e-mail needs your current password)."""
    u = account_service.update_profile(db, user, body.name, body.email, body.current_password)
    return UserOut(id=u.id, name=u.name, email=u.email, role=u.role.value)


@router.post("/change-password")
def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account_service.change_password(db, user, body.current_password, body.new_password)
    return {"changed": True}
