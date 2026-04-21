from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import DatabaseBackupNode, User
from app.schemas.database_backups import DatabaseBackupTreeResponse
from app.services.database_backup_service import build_database_backup_tree_response


router = APIRouter(tags=["database-backups"])


@router.get("/database-backups/tree", response_model=DatabaseBackupTreeResponse)
def get_database_backup_tree(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupTreeResponse:
    nodes = db.execute(select(DatabaseBackupNode)).scalars().all()
    return build_database_backup_tree_response(nodes)

