from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import read_session_token
from app.db.session import get_db
from app.models import User

_bearer_scheme = HTTPBearer(auto_error=False)


def _read_user_from_session(
    toolbox_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> tuple[User | None, str]:
    if not toolbox_session:
        return None, "未登录。"

    username = read_session_token(toolbox_session)
    if not username:
        return None, "登录已过期。"

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        return None, "用户不存在。"
    return user, ""


def get_current_user(
    toolbox_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    user, detail = _read_user_from_session(toolbox_session, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    return user


def verify_mcp_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> None:
    if not settings.mcp_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MCP 未启用。")
    if credentials is None or credentials.credentials != settings.mcp_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MCP API Key 无效。")


def verify_database_backup_download_access(
    toolbox_session: Optional[str] = Cookie(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    user, detail = _read_user_from_session(toolbox_session, db)
    if user is not None:
        return user

    if settings.download_api_key and credentials and credentials.credentials == settings.download_api_key:
        return None

    if credentials is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="下载 API Key 无效。")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def verify_database_backup_write_access(
    toolbox_session: Optional[str] = Cookie(default=None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    user, detail = _read_user_from_session(toolbox_session, db)
    if user is not None:
        return user

    if (
        settings.database_backup_write_api_key
        and credentials
        and credentials.credentials == settings.database_backup_write_api_key
    ):
        return None

    if credentials is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="数据库备份写入 API Key 无效。")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
