from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.settings import SettingsResponse, UpdateSettingsRequest
from app.services.settings_service import get_runtime_settings, update_runtime_settings


router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
def read_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    return get_runtime_settings(db)


@router.put("/settings", response_model=SettingsResponse)
def write_settings(
    payload: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    return update_runtime_settings(db, payload)
