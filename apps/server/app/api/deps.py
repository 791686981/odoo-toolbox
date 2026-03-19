from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import read_session_token
from app.db.session import get_db
from app.models import User


def get_current_user(
    toolbox_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not toolbox_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录。")

    username = read_session_token(toolbox_session)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期。")

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在。")
    return user
