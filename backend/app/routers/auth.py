"""Registration, login, logout, and the current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Profile, User
from app.schemas import LoginIn, RegisterIn, UserOut
from app.security import current_user, end_session, hash_password, start_session, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# A real hash to verify against when the username does not exist, so both paths take similar time.
_DUMMY_HASH = hash_password("venn-timing-equalizer")


def _out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, display_name=user.display_name)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is taken.")
    user = User(
        username=body.username,
        display_name=body.display_name.strip() or body.username,
        password_hash=hash_password(body.password),
    )
    user.profile = Profile()
    db.add(user)
    db.commit()
    start_session(db, user, response)
    return _out(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    throttle = request.app.state.login_throttle
    username = body.username.strip().lower()
    if throttle.blocked(username):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(User.username == username))
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if not user or not ok:
        throttle.record_failure(username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")
    throttle.reset(username)
    start_session(db, user, response)
    return _out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    end_session(db, request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return _out(user)
