from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ToolRun, User
from app.schemas.platform_runs import ToolRunResponse


router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[ToolRunResponse])
def list_runs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ToolRunResponse]:
    runs = (
        db.execute(
            select(ToolRun)
            .where(ToolRun.created_by == user.username)
            .order_by(ToolRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [ToolRunResponse.model_validate(run, from_attributes=True) for run in runs]
