from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_session_token, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, UserResponse


router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误。")

    response.set_cookie(
        key="toolbox_session",
        value=create_session_token(user.username),
        httponly=True,
        samesite="lax",
    )
    return UserResponse(username=user.username)


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("toolbox_session")
    return {"ok": True}


@router.get("/auth/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(username=user.username)
