from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import ToolArtifact, ToolRun, UploadedFile, User
from app.schemas.files import StoredFileResponse, UploadedFileResponse
from app.services.file_service import store_upload


router = APIRouter(tags=["files"])


def serialize_file(
    record: UploadedFile,
    artifact: ToolArtifact | None = None,
    tool_run: ToolRun | None = None,
) -> StoredFileResponse:
    stored_path = Path(record.stored_path).resolve()
    output_root = settings.output_dir.resolve()
    kind = "generated" if stored_path.is_relative_to(output_root) else "upload"
    return StoredFileResponse(
        id=record.id,
        original_name=record.original_name,
        mime_type=record.mime_type,
        size=record.size,
        created_at=record.created_at,
        kind=kind,
        run_id=artifact.run_id if artifact is not None else None,
        tool_id=tool_run.tool_id if tool_run is not None else None,
        artifact_label=artifact.label if artifact is not None else None,
    )


@router.get("/files", response_model=list[StoredFileResponse])
def list_files(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StoredFileResponse]:
    records = (
        db.execute(
            select(UploadedFile)
            .where(UploadedFile.created_by == user.username)
            .order_by(UploadedFile.created_at.desc())
        )
        .scalars()
        .all()
    )
    artifacts = (
        db.execute(select(ToolArtifact).where(ToolArtifact.file_id.in_([record.id for record in records])))
        .scalars()
        .all()
        if records
        else []
    )
    artifact_by_file_id = {artifact.file_id: artifact for artifact in artifacts}
    run_by_id: dict[str, ToolRun] = {}
    if artifacts:
        runs = (
            db.execute(select(ToolRun).where(ToolRun.id.in_([artifact.run_id for artifact in artifacts])))
            .scalars()
            .all()
        )
        run_by_id = {run.id: run for run in runs}

    return [
        serialize_file(
            record,
            artifact_by_file_id.get(record.id),
            run_by_id.get(artifact_by_file_id[record.id].run_id) if record.id in artifact_by_file_id else None,
        )
        for record in records
    ]


@router.post("/files/upload", response_model=UploadedFileResponse)
def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadedFileResponse:
    record = store_upload(db, file, user.username)
    return UploadedFileResponse.model_validate(record, from_attributes=True)


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    record = db.get(UploadedFile, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="文件不存在。")

    path = Path(record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已丢失。")

    return FileResponse(path, media_type=record.mime_type, filename=record.original_name)
