# Database Backup Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a database backup library module that stores database zip backups as version-tree nodes, exposes stable node-based zip download endpoints, and renders a platform page with a tree/detail view plus static usage guidelines.

**Architecture:** Add a backend `DatabaseBackupNode` model plus a focused service/router pair that treat backup records as shared authenticated platform data while reusing `UploadedFile` for binary storage. On the frontend, add a dedicated platform route and page that fetch the tree, loads node details on selection, creates root/child nodes through `multipart/form-data`, edits only mutable fields, and renders a static guidelines tab.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React, Vite, Ant Design, TanStack Query, Pytest, Vitest

---

## Preflight

- Use `feature/database-backup-spec` as the source branch for implementation.
- Prefer a dedicated worktree before writing code.
- Treat backup nodes as shared platform records visible to authenticated users; do not filter tree results by `created_by`.

Run these baselines before touching code:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_files_api.py -q

cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/tool-registry/index.test.ts src/layouts/ShellLayout.test.tsx
```

Expected: both commands pass on the pre-feature branch so failures introduced later are attributable to the new work.

## File Structure

### Backend

- Create: `apps/server/app/api/database_backups.py`  
  Authenticated routes for tree/detail/create/update/main-root/download/head.

- Create: `apps/server/app/schemas/database_backups.py`  
  Response models for tree/detail payloads and the metadata-only patch body.

- Create: `apps/server/app/services/database_backup_service.py`  
  Tree assembly, zip validation/storage, node serialization, immutable-field enforcement, main-root switching, and zip resolution helpers.

- Create: `apps/server/tests/test_database_backups_api.py`  
  End-to-end API coverage for create/tree/detail/update/zip download/head behavior.

- Modify: `apps/server/app/models/entities.py`  
  Add the `DatabaseBackupNode` SQLAlchemy model.

- Modify: `apps/server/app/models/__init__.py`  
  Export `DatabaseBackupNode`.

- Modify: `apps/server/app/main.py`  
  Register the new router.

### Frontend

- Create: `apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx`  
  Module page with tree/detail layout, spec tab, and actions.

- Create: `apps/web/src/pages/database-backups/DatabaseBackupNodeForm.tsx`  
  Modal form used for root creation, child creation, and metadata-only editing.

- Create: `apps/web/src/pages/database-backups/databaseBackupSpec.ts`  
  Static guideline section content rendered under the spec tab.

- Create: `apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx`  
  Page rendering, tab switching, validation, and mutation behavior tests.

- Modify: `apps/web/src/routes/index.tsx`  
  Register `/database-backups`.

- Modify: `apps/web/src/tool-registry/index.ts`  
  Add the built-in platform entry.

- Modify: `apps/web/src/tool-registry/index.test.ts`  
  Update order/section expectations.

- Modify: `apps/web/src/shared/api/client.ts`  
  Add database-backup API methods, including a `FormData` submit path.

- Modify: `apps/web/src/shared/api/types.ts`  
  Add tree/detail record types and create/update payload types.

- Modify: `apps/web/src/app/styles.css`  
  Add layout and form styles for the database-backups page.

## Task 1: Add the Backend Model and Empty Tree Read Path

**Files:**
- Create: `apps/server/app/api/database_backups.py`
- Create: `apps/server/app/schemas/database_backups.py`
- Create: `apps/server/app/services/database_backup_service.py`
- Modify: `apps/server/app/models/entities.py`
- Modify: `apps/server/app/models/__init__.py`
- Modify: `apps/server/app/main.py`
- Test: `apps/server/tests/test_database_backups_api.py`

- [ ] **Step 1: Write the failing empty-tree API test**

Add this test to `apps/server/tests/test_database_backups_api.py`:

```python
from fastapi.testclient import TestClient


def test_database_backups_tree_returns_empty_state(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        response = client.get("/api/database-backups/tree")
        assert response.status_code == 200
        assert response.json() == {"main_root_id": None, "items": []}
```

- [ ] **Step 2: Run the backend test to verify it fails**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py::test_database_backups_tree_returns_empty_state -v
```

Expected: FAIL with `404` or import errors because the router, schemas, and model do not exist yet.

- [ ] **Step 3: Add the model, schema, service, and minimal tree endpoint**

Add the model to `apps/server/app/models/entities.py`:

```python
class DatabaseBackupNode(Base):
    __tablename__ = "database_backup_nodes"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(255), nullable=False)
    database_name = Column(String(255), nullable=False)
    odoo_version = Column(String(64), nullable=False)
    parent_id = Column(String(36), ForeignKey("database_backup_nodes.id"), nullable=True)
    source_type = Column(String(32), nullable=False)
    zip_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    is_main_root = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(100), nullable=False)
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
```

Export it from `apps/server/app/models/__init__.py`:

```python
from app.models.entities import (
    DatabaseBackupNode,
    SystemSetting,
    TranslationJob,
    TranslationJobChunk,
    TranslationRowResult,
    UploadedFile,
    User,
)

__all__ = [
    "DatabaseBackupNode",
    "GettextTranslationChunk",
    "GettextTranslationEntry",
    "GettextTranslationRun",
    "SystemSetting",
    "ToolArtifact",
    "ToolRun",
    "TranslationJob",
    "TranslationJobChunk",
    "TranslationRowResult",
    "UploadedFile",
    "User",
]
```

Create `apps/server/app/schemas/database_backups.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatabaseBackupTreeNodeResponse(BaseModel):
    id: str
    name: str
    database_name: str
    odoo_version: str
    parent_id: str | None = None
    source_type: str
    is_main_root: bool
    created_at: datetime
    children: list["DatabaseBackupTreeNodeResponse"] = Field(default_factory=list)


DatabaseBackupTreeNodeResponse.model_rebuild()


class DatabaseBackupTreeResponse(BaseModel):
    main_root_id: str | None = None
    items: list[DatabaseBackupTreeNodeResponse] = Field(default_factory=list)
```

Create `apps/server/app/services/database_backup_service.py` with a minimal tree builder:

```python
from __future__ import annotations

from app.models import DatabaseBackupNode
from app.schemas.database_backups import DatabaseBackupTreeNodeResponse, DatabaseBackupTreeResponse


def build_database_backup_tree_response(nodes: list[DatabaseBackupNode]) -> DatabaseBackupTreeResponse:
    response_nodes = {
        node.id: DatabaseBackupTreeNodeResponse(
            id=node.id,
            name=node.name,
            database_name=node.database_name,
            odoo_version=node.odoo_version,
            parent_id=node.parent_id,
            source_type=node.source_type,
            is_main_root=node.is_main_root,
            created_at=node.created_at,
            children=[],
        )
        for node in nodes
    }

    root_items: list[DatabaseBackupTreeNodeResponse] = []
    for node in nodes:
        current = response_nodes[node.id]
        if node.parent_id and node.parent_id in response_nodes:
            response_nodes[node.parent_id].children.append(current)
        else:
            root_items.append(current)

    main_root = next((item for item in root_items if item.is_main_root), None)
    ordered_roots = sorted(
        root_items,
        key=lambda item: (not item.is_main_root, -item.created_at.timestamp()),
    )
    return DatabaseBackupTreeResponse(
        main_root_id=main_root.id if main_root else None,
        items=ordered_roots,
    )
```

Create `apps/server/app/api/database_backups.py`:

```python
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
    del user
    nodes = db.execute(select(DatabaseBackupNode).order_by(DatabaseBackupNode.created_at.desc())).scalars().all()
    return build_database_backup_tree_response(nodes)
```

Register the router in `apps/server/app/main.py`:

```python
from app.api.database_backups import router as database_backups_router

app.include_router(database_backups_router, prefix="/api")
```

- [ ] **Step 4: Run the backend test to verify it passes**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py::test_database_backups_tree_returns_empty_state -v
```

Expected: PASS with `1 passed`.

- [ ] **Step 5: Commit the backend skeleton**

Run:

```bash
git add \
  apps/server/app/api/database_backups.py \
  apps/server/app/models/__init__.py \
  apps/server/app/models/entities.py \
  apps/server/app/schemas/database_backups.py \
  apps/server/app/services/database_backup_service.py \
  apps/server/app/main.py \
  apps/server/tests/test_database_backups_api.py
git commit -m "feat(database-backups): 新增备份树基础模型与查询接口"
```

## Task 2: Implement Node Creation, Zip Validation, and Tree Population

**Files:**
- Modify: `apps/server/app/api/database_backups.py`
- Modify: `apps/server/app/schemas/database_backups.py`
- Modify: `apps/server/app/services/database_backup_service.py`
- Test: `apps/server/tests/test_database_backups_api.py`

- [ ] **Step 1: Write the failing create-node tests**

Extend `apps/server/tests/test_database_backups_api.py` with these tests:

```python
import io


def test_database_backups_create_root_and_child_nodes(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"})

        root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-2026-04-21",
                "database_name": "prod_main",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "true",
                "note": "主线根节点",
            },
            files={"file": ("prod-main.zip", io.BytesIO(b"root zip bytes"), "application/zip")},
        )
        assert root_response.status_code == 200
        root_payload = root_response.json()
        assert root_payload["parent_id"] is None
        assert root_payload["is_main_root"] is True

        child_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "upgrade-18-202604",
                "database_name": "upgrade_18_test",
                "odoo_version": "18.0",
                "source_type": "branch",
                "parent_id": root_payload["id"],
                "is_main_root": "false",
                "note": "升级分支",
            },
            files={"file": ("upgrade-18.zip", io.BytesIO(b"child zip bytes"), "application/zip")},
        )
        assert child_response.status_code == 200
        child_payload = child_response.json()
        assert child_payload["parent_id"] == root_payload["id"]
        assert child_payload["is_main_root"] is False

        tree_response = client.get("/api/database-backups/tree")
        tree_payload = tree_response.json()
        assert tree_payload["main_root_id"] == root_payload["id"]
        assert tree_payload["items"][0]["children"][0]["id"] == child_payload["id"]


def test_database_backups_rejects_non_zip_upload_and_missing_parent(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"})

        bad_file_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "broken",
                "database_name": "broken_db",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "false",
                "note": "",
            },
            files={"file": ("broken.txt", io.BytesIO(b"plain text"), "text/plain")},
        )
        assert bad_file_response.status_code == 400

        missing_parent_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "missing-parent",
                "database_name": "missing_parent_db",
                "odoo_version": "18.0",
                "source_type": "branch",
                "parent_id": "not-found",
                "is_main_root": "false",
                "note": "",
            },
            files={"file": ("branch.zip", io.BytesIO(b"branch bytes"), "application/zip")},
        )
        assert missing_parent_response.status_code == 404
```

- [ ] **Step 2: Run the create-node tests to verify they fail**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py -k "create_root_and_child_nodes or rejects_non_zip_upload" -v
```

Expected: FAIL because `POST /api/database-backups/nodes` is not implemented.

- [ ] **Step 3: Implement create-node schemas, service logic, and route**

Extend `apps/server/app/schemas/database_backups.py`:

```python
class DatabaseBackupZipResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    mime_type: str
    sha256: str
    download_url: str


class DatabaseBackupDetailResponse(BaseModel):
    id: str
    name: str
    database_name: str
    odoo_version: str
    parent_id: str | None = None
    source_type: str
    is_main_root: bool
    note: str
    created_at: datetime
    updated_at: datetime
    zip: DatabaseBackupZipResponse
```

Add create helpers to `apps/server/app/services/database_backup_service.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DatabaseBackupNode, UploadedFile
from app.schemas.database_backups import DatabaseBackupDetailResponse, DatabaseBackupZipResponse


def ensure_zip_upload(upload: UploadFile) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix != ".zip":
        raise HTTPException(status_code=400, detail="数据库备份节点只接受 .zip 文件。")


def create_database_backup_node(
    db: Session,
    *,
    name: str,
    database_name: str,
    odoo_version: str,
    source_type: str,
    parent_id: str | None,
    is_main_root: bool,
    note: str,
    upload: UploadFile,
    username: str,
) -> DatabaseBackupNode:
    ensure_zip_upload(upload)

    parent = None
    if parent_id is not None:
        parent = db.get(DatabaseBackupNode, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="父节点不存在。")
        if source_type != "branch":
            raise HTTPException(status_code=400, detail="子节点的 source_type 必须为 branch。")
        if is_main_root:
            raise HTTPException(status_code=400, detail="只有根节点可以设置为主线节点。")
    elif source_type != "root":
        raise HTTPException(status_code=400, detail="根节点的 source_type 必须为 root。")

    file_bytes = upload.file.read()
    suffix = Path(upload.filename or "backup.zip").suffix or ".zip"
    stored_name = f"{uuid4()}{suffix}"
    destination = settings.upload_dir / stored_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    try:
        destination.write_bytes(file_bytes)
        uploaded_file = UploadedFile(
            original_name=upload.filename or "backup.zip",
            stored_path=str(destination),
            mime_type=upload.content_type or "application/zip",
            size=len(file_bytes),
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            created_by=username,
        )
        db.add(uploaded_file)
        db.flush()

        if is_main_root:
            db.execute(
                update(DatabaseBackupNode)
                .where(DatabaseBackupNode.is_main_root.is_(True))
                .values(is_main_root=False)
            )

        node = DatabaseBackupNode(
            name=name,
            database_name=database_name,
            odoo_version=odoo_version,
            parent_id=parent.id if parent else None,
            source_type=source_type,
            zip_file_id=uploaded_file.id,
            is_main_root=is_main_root,
            created_by=username,
            note=note,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        return node
    except Exception:
        db.rollback()
        if destination.exists():
            destination.unlink()
        raise


def serialize_database_backup_detail(node: DatabaseBackupNode, file_record: UploadedFile) -> DatabaseBackupDetailResponse:
    return DatabaseBackupDetailResponse(
        id=node.id,
        name=node.name,
        database_name=node.database_name,
        odoo_version=node.odoo_version,
        parent_id=node.parent_id,
        source_type=node.source_type,
        is_main_root=node.is_main_root,
        note=node.note,
        created_at=node.created_at,
        updated_at=node.updated_at,
        zip=DatabaseBackupZipResponse(
            file_id=file_record.id,
            filename=file_record.original_name,
            size=file_record.size,
            mime_type=file_record.mime_type,
            sha256=file_record.sha256,
            download_url=f"/api/database-backups/nodes/{node.id}/zip",
        ),
    )
```

Add the create route to `apps/server/app/api/database_backups.py`:

```python
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.services.database_backup_service import (
    build_database_backup_tree_response,
    create_database_backup_node,
    serialize_database_backup_detail,
)


@router.post("/database-backups/nodes", response_model=DatabaseBackupDetailResponse)
def create_database_backup(
    name: str = Form(...),
    database_name: str = Form(...),
    odoo_version: str = Form(...),
    source_type: str = Form(...),
    parent_id: str | None = Form(None),
    is_main_root: bool = Form(False),
    note: str = Form(""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node = create_database_backup_node(
        db,
        name=name,
        database_name=database_name,
        odoo_version=odoo_version,
        source_type=source_type,
        parent_id=parent_id,
        is_main_root=is_main_root,
        note=note,
        upload=file,
        username=user.username,
    )
    file_record = db.get(UploadedFile, node.zip_file_id)
    assert file_record is not None
    return serialize_database_backup_detail(node, file_record)
```

- [ ] **Step 4: Run the create-node tests to verify they pass**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py -k "create_root_and_child_nodes or rejects_non_zip_upload" -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit create-node support**

Run:

```bash
git add \
  apps/server/app/api/database_backups.py \
  apps/server/app/schemas/database_backups.py \
  apps/server/app/services/database_backup_service.py \
  apps/server/tests/test_database_backups_api.py
git commit -m "feat(database-backups): 新增备份节点创建与zip校验"
```

## Task 3: Add Detail, Immutable Patch, Main-Root Switching, and Zip Download/HEAD

**Files:**
- Modify: `apps/server/app/api/database_backups.py`
- Modify: `apps/server/app/schemas/database_backups.py`
- Modify: `apps/server/app/services/database_backup_service.py`
- Test: `apps/server/tests/test_database_backups_api.py`

- [ ] **Step 1: Write the failing detail/update/download tests**

Append these tests to `apps/server/tests/test_database_backups_api.py`:

```python
import io


def test_database_backups_detail_patch_mark_main_root_and_zip_download(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"})

        first_root = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-a",
                "database_name": "prod_main_a",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "true",
                "note": "A",
            },
            files={"file": ("a.zip", io.BytesIO(b"a-bytes"), "application/zip")},
        ).json()

        second_root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-b",
                "database_name": "prod_main_b",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "false",
                "note": "B",
            },
            files={"file": ("b.zip", io.BytesIO(b"b-bytes"), "application/zip")},
        )
        assert second_root_response.status_code == 200
        second_root = second_root_response.json()

        detail_response = client.get(f"/api/database-backups/nodes/{first_root['id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["zip"]["download_url"].endswith(f"/{first_root['id']}/zip")

        patch_response = client.patch(
            f"/api/database-backups/nodes/{first_root['id']}",
            json={"name": "prod-main-a-renamed", "note": "updated"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["name"] == "prod-main-a-renamed"
        assert patch_response.json()["note"] == "updated"

        forbidden_patch = client.patch(
            f"/api/database-backups/nodes/{first_root['id']}",
            json={"database_name": "should_fail"},
        )
        assert forbidden_patch.status_code == 400

        mark_response = client.post(f"/api/database-backups/nodes/{second_root['id']}/mark-main-root")
        assert mark_response.status_code == 200
        assert mark_response.json()["is_main_root"] is True

        tree_response = client.get("/api/database-backups/tree")
        assert tree_response.json()["main_root_id"] == second_root["id"]

        zip_response = client.get(f"/api/database-backups/nodes/{first_root['id']}/zip")
        assert zip_response.status_code == 200
        assert zip_response.content == b"a-bytes"
        assert zip_response.headers["content-type"] == "application/zip"

        head_response = client.head(f"/api/database-backups/nodes/{first_root['id']}/zip")
        assert head_response.status_code == 200
        assert head_response.headers["x-file-sha256"] == detail_response.json()["zip"]["sha256"]
        assert head_response.headers["content-length"] == str(len(b"a-bytes"))
```

- [ ] **Step 2: Run the detail/update/download tests to verify they fail**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py::test_database_backups_detail_patch_mark_main_root_and_zip_download -v
```

Expected: FAIL because detail, patch, mark-main-root, and zip endpoints do not exist yet.

- [ ] **Step 3: Implement detail, patch, mark-main-root, and zip routes**

Extend `apps/server/app/schemas/database_backups.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class DatabaseBackupPatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    note: str | None = None
```

Add helper functions to `apps/server/app/services/database_backup_service.py`:

```python
from email.utils import formatdate
from pathlib import Path

from fastapi import HTTPException


def get_database_backup_node_or_404(db: Session, node_id: str) -> DatabaseBackupNode:
    node = db.get(DatabaseBackupNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="备份节点不存在。")
    return node


def get_database_backup_file_or_404(db: Session, node: DatabaseBackupNode) -> UploadedFile:
    file_record = db.get(UploadedFile, node.zip_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return file_record


def update_database_backup_metadata(
    db: Session,
    *,
    node: DatabaseBackupNode,
    name: str | None,
    note: str | None,
) -> DatabaseBackupNode:
    if name is None and note is None:
        raise HTTPException(status_code=400, detail="只允许修改 name 和 note。")
    if name is not None:
        node.name = name
    if note is not None:
        node.note = note
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def set_database_backup_main_root(db: Session, *, node: DatabaseBackupNode) -> DatabaseBackupNode:
    if node.parent_id is not None:
        raise HTTPException(status_code=400, detail="只有根节点可以设置为主线节点。")
    db.execute(update(DatabaseBackupNode).values(is_main_root=False))
    node.is_main_root = True
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def build_zip_head_headers(file_record: UploadedFile, stored_path: Path) -> dict[str, str]:
    stat = stored_path.stat()
    return {
        "Content-Length": str(file_record.size),
        "Content-Type": file_record.mime_type,
        "ETag": file_record.sha256,
        "X-File-Sha256": file_record.sha256,
        "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
    }
```

Extend `apps/server/app/api/database_backups.py`:

```python
from pathlib import Path

from fastapi import Response
from fastapi.responses import FileResponse

from app.schemas.database_backups import (
    DatabaseBackupDetailResponse,
    DatabaseBackupPatchRequest,
    DatabaseBackupTreeResponse,
)
from app.services.database_backup_service import (
    build_database_backup_tree_response,
    build_zip_head_headers,
    create_database_backup_node,
    get_database_backup_file_or_404,
    get_database_backup_node_or_404,
    serialize_database_backup_detail,
    set_database_backup_main_root,
    update_database_backup_metadata,
)


@router.get("/database-backups/nodes/{node_id}", response_model=DatabaseBackupDetailResponse)
def get_database_backup_detail(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    del user
    node = get_database_backup_node_or_404(db, node_id)
    file_record = get_database_backup_file_or_404(db, node)
    return serialize_database_backup_detail(node, file_record)


@router.patch("/database-backups/nodes/{node_id}", response_model=DatabaseBackupDetailResponse)
def patch_database_backup(
    node_id: str,
    payload: DatabaseBackupPatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    del user
    if payload.model_dump(exclude_none=True).keys() - {"name", "note"}:
        raise HTTPException(status_code=400, detail="只允许修改 name 和 note。")
    node = get_database_backup_node_or_404(db, node_id)
    node = update_database_backup_metadata(db, node=node, name=payload.name, note=payload.note)
    file_record = get_database_backup_file_or_404(db, node)
    return serialize_database_backup_detail(node, file_record)


@router.post("/database-backups/nodes/{node_id}/mark-main-root", response_model=DatabaseBackupDetailResponse)
def mark_database_backup_main_root(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    del user
    node = get_database_backup_node_or_404(db, node_id)
    node = set_database_backup_main_root(db, node=node)
    file_record = get_database_backup_file_or_404(db, node)
    return serialize_database_backup_detail(node, file_record)


@router.get("/database-backups/nodes/{node_id}/zip")
def download_database_backup_zip(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    del user
    node = get_database_backup_node_or_404(db, node_id)
    file_record = get_database_backup_file_or_404(db, node)
    path = Path(file_record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return FileResponse(path, media_type=file_record.mime_type, filename=file_record.original_name)


@router.head("/database-backups/nodes/{node_id}/zip")
def head_database_backup_zip(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    del user
    node = get_database_backup_node_or_404(db, node_id)
    file_record = get_database_backup_file_or_404(db, node)
    path = Path(file_record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return Response(status_code=200, headers=build_zip_head_headers(file_record, path))
```

- [ ] **Step 4: Run the detail/update/download tests to verify they pass**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py::test_database_backups_detail_patch_mark_main_root_and_zip_download -v
```

Expected: PASS.

- [ ] **Step 5: Commit the read/write endpoint set**

Run:

```bash
git add \
  apps/server/app/api/database_backups.py \
  apps/server/app/schemas/database_backups.py \
  apps/server/app/services/database_backup_service.py \
  apps/server/tests/test_database_backups_api.py
git commit -m "feat(database-backups): 完善备份节点详情与zip访问接口"
```

## Task 4: Add Frontend Route, Sidebar Entry, Shared Types, and Client Methods

**Files:**
- Modify: `apps/web/src/routes/index.tsx`
- Modify: `apps/web/src/tool-registry/index.ts`
- Modify: `apps/web/src/tool-registry/index.test.ts`
- Modify: `apps/web/src/shared/api/client.ts`
- Modify: `apps/web/src/shared/api/types.ts`
- Test: `apps/web/src/tool-registry/index.test.ts`

- [ ] **Step 1: Write the failing sidebar-order test**

Update `apps/web/src/tool-registry/index.test.ts` expectations:

```ts
expect(items.map((item) => item.id)).toEqual([
  "home",
  "csv-translation",
  "runs",
  "database-backups",
  "files",
  "settings",
  "po-translation",
]);
```

and

```ts
expect(items.map((item) => ({ id: item.id, section: (item as { section?: string }).section }))).toEqual([
  { id: "home", section: "platform" },
  { id: "csv-translation", section: "tool" },
  { id: "runs", section: "platform" },
  { id: "database-backups", section: "platform" },
  { id: "files", section: "platform" },
  { id: "settings", section: "platform" },
]);
```

- [ ] **Step 2: Run the sidebar-order test to verify it fails**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/tool-registry/index.test.ts
```

Expected: FAIL because the `database-backups` platform entry does not exist yet.

- [ ] **Step 3: Add the built-in route, shared types, and API helpers**

Extend `apps/web/src/shared/api/types.ts`:

```ts
export type DatabaseBackupTreeNodeRecord = {
  id: string;
  name: string;
  database_name: string;
  odoo_version: string;
  parent_id?: string | null;
  source_type: "root" | "branch";
  is_main_root: boolean;
  created_at: string;
  children: DatabaseBackupTreeNodeRecord[];
};

export type DatabaseBackupTreeRecord = {
  main_root_id?: string | null;
  items: DatabaseBackupTreeNodeRecord[];
};

export type DatabaseBackupDetailRecord = {
  id: string;
  name: string;
  database_name: string;
  odoo_version: string;
  parent_id?: string | null;
  source_type: "root" | "branch";
  is_main_root: boolean;
  note: string;
  created_at: string;
  updated_at: string;
  zip: {
    file_id: string;
    filename: string;
    size: number;
    mime_type: string;
    sha256: string;
    download_url: string;
  };
};
```

Add client helpers to `apps/web/src/shared/api/client.ts`:

```ts
  databaseBackupTree: () => request<DatabaseBackupTreeRecord>("/api/database-backups/tree"),
  databaseBackupNode: (nodeId: string) =>
    request<DatabaseBackupDetailRecord>(`/api/database-backups/nodes/${nodeId}`),
  createDatabaseBackupNode: async (payload: {
    name: string;
    database_name: string;
    odoo_version: string;
    source_type: "root" | "branch";
    parent_id?: string | null;
    is_main_root: boolean;
    note: string;
    file: File;
  }) => {
    const formData = new FormData();
    formData.append("name", payload.name);
    formData.append("database_name", payload.database_name);
    formData.append("odoo_version", payload.odoo_version);
    formData.append("source_type", payload.source_type);
    if (payload.parent_id) {
      formData.append("parent_id", payload.parent_id);
    }
    formData.append("is_main_root", String(payload.is_main_root));
    formData.append("note", payload.note);
    formData.append("file", payload.file);

    const response = await fetch("/api/database-backups/nodes", {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error("创建数据库备份节点失败");
    }
    return (await response.json()) as DatabaseBackupDetailRecord;
  },
  updateDatabaseBackupNode: (nodeId: string, payload: { name?: string; note?: string }) =>
    request<DatabaseBackupDetailRecord>(`/api/database-backups/nodes/${nodeId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  markDatabaseBackupMainRoot: (nodeId: string) =>
    request<DatabaseBackupDetailRecord>(`/api/database-backups/nodes/${nodeId}/mark-main-root`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  databaseBackupZipUrl: (nodeId: string) => `/api/database-backups/nodes/${nodeId}/zip`,
```

Add the built-in entry in `apps/web/src/tool-registry/index.ts`:

```ts
  {
    id: "database-backups",
    title: "数据库备份库",
    description: "管理数据库 zip 备份版本树、主线节点与使用规范。",
    route: "/database-backups",
    icon: "folder",
    category: "platform",
    enabled: true,
    order: 21,
    capabilities: ["database-backups"],
    section: "platform",
  },
```

Register the route in `apps/web/src/routes/index.tsx`:

```tsx
import { DatabaseBackupsPage } from "../pages/database-backups/DatabaseBackupsPage";

<Route path="/database-backups" element={<DatabaseBackupsPage />} />
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/tool-registry/index.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit the platform integration layer**

Run:

```bash
git add \
  apps/web/src/routes/index.tsx \
  apps/web/src/shared/api/client.ts \
  apps/web/src/shared/api/types.ts \
  apps/web/src/tool-registry/index.ts \
  apps/web/src/tool-registry/index.test.ts
git commit -m "feat(database-backups): 接入前端路由与平台入口"
```

## Task 5: Build the Database Backups Page Skeleton and Static Spec Tab

**Files:**
- Create: `apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx`
- Create: `apps/web/src/pages/database-backups/databaseBackupSpec.ts`
- Modify: `apps/web/src/app/styles.css`
- Test: `apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx`

- [ ] **Step 1: Write the failing page-render test**

Create `apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  databaseBackupTree: vi.fn(),
  databaseBackupNode: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    databaseBackupTree: apiMock.databaseBackupTree,
    databaseBackupNode: apiMock.databaseBackupNode,
    databaseBackupZipUrl: (nodeId: string) => `/api/database-backups/nodes/${nodeId}/zip`,
  },
}));

import { DatabaseBackupsPage } from "./DatabaseBackupsPage";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DatabaseBackupsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DatabaseBackupsPage", () => {
  beforeEach(() => {
    apiMock.databaseBackupTree.mockResolvedValue({
      main_root_id: "root-1",
      items: [
        {
          id: "root-1",
          name: "prod-main-2026-04-21",
          database_name: "prod_main",
          odoo_version: "18.0",
          parent_id: null,
          source_type: "root",
          is_main_root: true,
          created_at: "2026-04-21T03:00:00Z",
          children: [],
        },
      ],
    });
    apiMock.databaseBackupNode.mockResolvedValue({
      id: "root-1",
      name: "prod-main-2026-04-21",
      database_name: "prod_main",
      odoo_version: "18.0",
      parent_id: null,
      source_type: "root",
      is_main_root: true,
      note: "主线备份节点",
      created_at: "2026-04-21T03:00:00Z",
      updated_at: "2026-04-21T03:00:00Z",
      zip: {
        file_id: "file-1",
        filename: "prod-main.zip",
        size: 1024,
        mime_type: "application/zip",
        sha256: "abc123",
        download_url: "/api/database-backups/nodes/root-1/zip",
      },
    });
  });

  it("renders the tree detail view and guideline tab", async () => {
    renderPage();

    expect(await screen.findByText("数据库备份库")).toBeInTheDocument();
    expect(await screen.findByText("prod-main-2026-04-21")).toBeInTheDocument();
    expect(await screen.findByText("主线备份节点")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "命名与升级规范" }));
    expect(await screen.findByText("数据库命名规范")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the page-render test to verify it fails**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/pages/database-backups/DatabaseBackupsPage.test.tsx
```

Expected: FAIL because `DatabaseBackupsPage` and the spec content module do not exist yet.

- [ ] **Step 3: Implement the page skeleton, static spec content, and styles**

Create `apps/web/src/pages/database-backups/databaseBackupSpec.ts`:

```ts
export const databaseBackupSpecSections = [
  {
    key: "naming",
    title: "数据库命名规范",
    items: [
      "主线数据库使用 prod-main-YYYYMMDD 形式归档。",
      "升级分支统一使用 upgrade-目标版本-日期 或场景名。",
      "演示或客户验证分支必须在名称中体现用途。",
    ],
  },
  {
    key: "usage",
    title: "主线与分支使用规则",
    items: [
      "主线根节点只能人工切换，不依赖创建顺序自动推断。",
      "所有分支节点必须从明确父节点派生。",
      "备份节点创建后不得替换 zip 或重排父子关系。",
    ],
  },
  {
    key: "upgrade",
    title: "升级测试与回写规则",
    items: [
      "升级测试分支必须记录目标 Odoo 版本和关键备注。",
      "测试完成后通过备注记录结论，不回写修改备份文件。",
      "失效分支保留归档记录，后续通过命名约定识别废弃状态。",
    ],
  },
] as const;
```

Create `apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx`:

```tsx
import { Button, Card, Descriptions, Empty, Spin, Tabs, Tree, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../shared/api/client";
import { databaseBackupSpecSections } from "./databaseBackupSpec";

function mapTree(nodes: Array<{
  id: string;
  name: string;
  is_main_root: boolean;
  children: Array<any>;
}>) {
  return nodes.map((node) => ({
    key: node.id,
    title: node.is_main_root ? `主线 · ${node.name}` : node.name,
    children: mapTree(node.children),
  }));
}

export function DatabaseBackupsPage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const treeQuery = useQuery({
    queryKey: ["database-backups", "tree"],
    queryFn: api.databaseBackupTree,
  });
  const detailQuery = useQuery({
    queryKey: ["database-backups", "detail", selectedNodeId],
    queryFn: () => api.databaseBackupNode(selectedNodeId!),
    enabled: Boolean(selectedNodeId),
  });

  useEffect(() => {
    if (!selectedNodeId && treeQuery.data) {
      setSelectedNodeId(treeQuery.data.main_root_id ?? treeQuery.data.items[0]?.id ?? null);
    }
  }, [selectedNodeId, treeQuery.data]);

  const treeData = useMemo(() => mapTree(treeQuery.data?.items ?? []), [treeQuery.data]);

  return (
    <div className="page-stack database-backups-page">
      <section className="workspace-hero compact">
        <div className="workspace-copy-group">
          <Typography.Title level={2} className="workspace-title">
            数据库备份库
          </Typography.Title>
          <Typography.Text className="workspace-copy">
            维护数据库 zip 备份的主线节点、分支关系和使用规范。
          </Typography.Text>
        </div>
      </section>

      <Tabs
        items={[
          {
            key: "tree",
            label: "版本树",
            children: (
              <div className="database-backups-layout">
                <Card className="panel-card database-backups-tree-panel">
                  {treeQuery.isLoading ? (
                    <div className="database-backups-loading">
                      <Spin />
                    </div>
                  ) : treeData.length ? (
                    <Tree
                      selectedKeys={selectedNodeId ? [selectedNodeId] : []}
                      treeData={treeData}
                      onSelect={(keys) => setSelectedNodeId((keys[0] as string | undefined) ?? null)}
                    />
                  ) : (
                    <Empty description="当前还没有数据库备份节点。" />
                  )}
                </Card>

                <Card className="panel-card database-backups-detail-panel">
                  {detailQuery.isLoading ? (
                    <div className="database-backups-loading">
                      <Spin />
                    </div>
                  ) : detailQuery.data ? (
                    <>
                      <div className="database-backups-detail-header">
                        <div>
                          <Typography.Title level={3} className="panel-title">
                            {detailQuery.data.name}
                          </Typography.Title>
                          <Typography.Text className="panel-copy">
                            {detailQuery.data.is_main_root ? "主线根节点" : "分支节点"}
                          </Typography.Text>
                        </div>
                        <Button href={api.databaseBackupZipUrl(detailQuery.data.id)}>下载 zip</Button>
                      </div>
                      <Descriptions column={2} size="small">
                        <Descriptions.Item label="数据库名">{detailQuery.data.database_name}</Descriptions.Item>
                        <Descriptions.Item label="Odoo 版本">{detailQuery.data.odoo_version}</Descriptions.Item>
                        <Descriptions.Item label="来源类型">{detailQuery.data.source_type}</Descriptions.Item>
                        <Descriptions.Item label="创建时间">
                          {new Date(detailQuery.data.created_at).toLocaleString("zh-CN")}
                        </Descriptions.Item>
                        <Descriptions.Item label="备注" span={2}>
                          {detailQuery.data.note || "暂无备注"}
                        </Descriptions.Item>
                        <Descriptions.Item label="zip 文件">{detailQuery.data.zip.filename}</Descriptions.Item>
                        <Descriptions.Item label="SHA256">{detailQuery.data.zip.sha256}</Descriptions.Item>
                      </Descriptions>
                    </>
                  ) : (
                    <Empty description="请选择一个备份节点查看详情。" />
                  )}
                </Card>
              </div>
            ),
          },
          {
            key: "spec",
            label: "命名与升级规范",
            children: (
              <div className="database-backups-spec-grid">
                {databaseBackupSpecSections.map((section) => (
                  <Card key={section.key} className="panel-card">
                    <Typography.Title level={4} className="panel-title">
                      {section.title}
                    </Typography.Title>
                    <ul className="database-backups-spec-list">
                      {section.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </Card>
                ))}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
```

Add styles to `apps/web/src/app/styles.css`:

```css
.database-backups-layout {
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  gap: 20px;
}

.database-backups-tree-panel,
.database-backups-detail-panel {
  min-height: 420px;
}

.database-backups-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.database-backups-spec-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}

.database-backups-spec-list {
  margin: 0;
  padding-left: 20px;
  color: rgba(18, 38, 58, 0.78);
}

.database-backups-loading {
  min-height: 280px;
  display: grid;
  place-items: center;
}
```

- [ ] **Step 4: Run the page-render test to verify it passes**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/pages/database-backups/DatabaseBackupsPage.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the page skeleton**

Run:

```bash
git add \
  apps/web/src/app/styles.css \
  apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx \
  apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx \
  apps/web/src/pages/database-backups/databaseBackupSpec.ts
git commit -m "feat(database-backups): 新增备份库页面骨架与规范页"
```

## Task 6: Add Root/Child Creation, Metadata Editing, and Main-Root Actions to the Page

**Files:**
- Create: `apps/web/src/pages/database-backups/DatabaseBackupNodeForm.tsx`
- Modify: `apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx`
- Modify: `apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx`
- Modify: `apps/web/src/app/styles.css`

- [ ] **Step 1: Write the failing mutation-and-validation tests**

Extend `apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx` with mutation mocks and tests:

```tsx
const apiMock = vi.hoisted(() => ({
  databaseBackupTree: vi.fn(),
  databaseBackupNode: vi.fn(),
  createDatabaseBackupNode: vi.fn(),
  updateDatabaseBackupNode: vi.fn(),
  markDatabaseBackupMainRoot: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    databaseBackupTree: apiMock.databaseBackupTree,
    databaseBackupNode: apiMock.databaseBackupNode,
    createDatabaseBackupNode: apiMock.createDatabaseBackupNode,
    updateDatabaseBackupNode: apiMock.updateDatabaseBackupNode,
    markDatabaseBackupMainRoot: apiMock.markDatabaseBackupMainRoot,
    databaseBackupZipUrl: (nodeId: string) => `/api/database-backups/nodes/${nodeId}/zip`,
  },
}));

it("requires a zip file when creating a root node", async () => {
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "新建根节点" }));
  fireEvent.click(screen.getByRole("button", { name: "确认" }));
  expect(await screen.findByText("请上传 zip 备份文件")).toBeInTheDocument();
});

it("submits editable fields only when saving metadata", async () => {
  apiMock.updateDatabaseBackupNode.mockResolvedValue({
    id: "root-1",
    name: "prod-main-renamed",
    database_name: "prod_main",
    odoo_version: "18.0",
    parent_id: null,
    source_type: "root",
    is_main_root: true,
    note: "updated",
    created_at: "2026-04-21T03:00:00Z",
    updated_at: "2026-04-21T03:10:00Z",
    zip: {
      file_id: "file-1",
      filename: "prod-main.zip",
      size: 1024,
      mime_type: "application/zip",
      sha256: "abc123",
      download_url: "/api/database-backups/nodes/root-1/zip",
    },
  });

  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "编辑节点" }));
  fireEvent.change(screen.getByLabelText("节点名"), { target: { value: "prod-main-renamed" } });
  fireEvent.change(screen.getByLabelText("备注"), { target: { value: "updated" } });
  fireEvent.click(screen.getByRole("button", { name: "确认" }));

  expect(apiMock.updateDatabaseBackupNode).toHaveBeenCalledWith("root-1", {
    name: "prod-main-renamed",
    note: "updated",
  });
});

it("calls the main-root mutation from the detail panel", async () => {
  apiMock.markDatabaseBackupMainRoot.mockResolvedValue({
    id: "root-1",
    name: "prod-main-2026-04-21",
    database_name: "prod_main",
    odoo_version: "18.0",
    parent_id: null,
    source_type: "root",
    is_main_root: true,
    note: "主线备份节点",
    created_at: "2026-04-21T03:00:00Z",
    updated_at: "2026-04-21T03:00:00Z",
    zip: {
      file_id: "file-1",
      filename: "prod-main.zip",
      size: 1024,
      mime_type: "application/zip",
      sha256: "abc123",
      download_url: "/api/database-backups/nodes/root-1/zip",
    },
  });

  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "设为主线" }));
  expect(apiMock.markDatabaseBackupMainRoot).toHaveBeenCalledWith("root-1");
});
```

- [ ] **Step 2: Run the page test to verify the new assertions fail**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/pages/database-backups/DatabaseBackupsPage.test.tsx
```

Expected: FAIL because the page has no form, no edit button, and no mutation hooks yet.

- [ ] **Step 3: Implement the form component and page mutations**

Create `apps/web/src/pages/database-backups/DatabaseBackupNodeForm.tsx`:

```tsx
import { Form, Input, Modal, Upload } from "antd";
import type { UploadProps } from "antd";

export type DatabaseBackupNodeFormMode = "create-root" | "create-child" | "edit";

export type DatabaseBackupNodeFormValues = {
  name: string;
  database_name: string;
  odoo_version: string;
  note: string;
  file?: File;
};

type Props = {
  mode: DatabaseBackupNodeFormMode;
  open: boolean;
  initialValues?: Partial<DatabaseBackupNodeFormValues>;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (values: DatabaseBackupNodeFormValues) => Promise<void>;
};

export function DatabaseBackupNodeForm({ mode, open, initialValues, submitting, onCancel, onSubmit }: Props) {
  const [form] = Form.useForm<DatabaseBackupNodeFormValues>();
  const isEdit = mode === "edit";

  const beforeUpload: UploadProps["beforeUpload"] = (file) => {
    form.setFieldValue("file", file as File);
    return false;
  };

  return (
    <Modal
      open={open}
      title={isEdit ? "编辑节点" : mode === "create-root" ? "新建根节点" : "新增子节点"}
      confirmLoading={submitting}
      onCancel={onCancel}
      onOk={() => form.submit()}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues}
        onFinish={onSubmit}
      >
        <Form.Item name="name" label="节点名" rules={[{ required: true, message: "请输入节点名" }]}>
          <Input />
        </Form.Item>
        <Form.Item
          name="database_name"
          label="数据库名"
          rules={[{ required: !isEdit, message: "请输入数据库名" }]}
        >
          <Input disabled={isEdit} />
        </Form.Item>
        <Form.Item
          name="odoo_version"
          label="Odoo 版本"
          rules={[{ required: !isEdit, message: "请输入 Odoo 版本" }]}
        >
          <Input disabled={isEdit} />
        </Form.Item>
        <Form.Item name="note" label="备注">
          <Input.TextArea rows={4} />
        </Form.Item>
        {!isEdit ? (
          <Form.Item
            name="file"
            label="zip 备份文件"
            rules={[{ required: true, message: "请上传 zip 备份文件" }]}
            valuePropName="file"
          >
            <Upload beforeUpload={beforeUpload} maxCount={1} accept=".zip">
              <a>选择 zip 文件</a>
            </Upload>
          </Form.Item>
        ) : null}
      </Form>
    </Modal>
  );
}
```

Update `apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx` to wire the mutations:

```tsx
import { Button, Card, Descriptions, Empty, Spin, Tabs, Tree, Typography, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { DatabaseBackupNodeForm, type DatabaseBackupNodeFormMode } from "./DatabaseBackupNodeForm";

type ModalState =
  | { mode: "create-root" }
  | { mode: "create-child"; parentId: string }
  | { mode: "edit" };

const [modalState, setModalState] = useState<ModalState | null>(null);
const queryClient = useQueryClient();

const createMutation = useMutation({
  mutationFn: api.createDatabaseBackupNode,
  onSuccess: async (payload) => {
    await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
    await queryClient.invalidateQueries({ queryKey: ["database-backups", "detail", payload.id] });
    setSelectedNodeId(payload.id);
    setModalState(null);
    message.success("数据库备份节点已创建");
  },
});

const updateMutation = useMutation({
  mutationFn: ({ nodeId, payload }: { nodeId: string; payload: { name?: string; note?: string } }) =>
    api.updateDatabaseBackupNode(nodeId, payload),
  onSuccess: async (payload) => {
    await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
    await queryClient.invalidateQueries({ queryKey: ["database-backups", "detail", payload.id] });
    setModalState(null);
    message.success("节点信息已更新");
  },
});

const markMainRootMutation = useMutation({
  mutationFn: api.markDatabaseBackupMainRoot,
  onSuccess: async (payload) => {
    await queryClient.invalidateQueries({ queryKey: ["database-backups", "tree"] });
    await queryClient.invalidateQueries({ queryKey: ["database-backups", "detail", payload.id] });
    message.success("已切换主线根节点");
  },
});
```

Update the page action area:

```tsx
<div className="database-backups-page-actions">
  <Button onClick={() => setModalState({ mode: "create-root" })}>新建根节点</Button>
  <Button
    disabled={!detailQuery.data}
    onClick={() => detailQuery.data && setModalState({ mode: "create-child", parentId: detailQuery.data.id })}
  >
    新增子节点
  </Button>
  <Button disabled={!detailQuery.data} onClick={() => setModalState({ mode: "edit" })}>
    编辑节点
  </Button>
  <Button
    disabled={!detailQuery.data || detailQuery.data.parent_id !== null || detailQuery.data.is_main_root}
    onClick={() => detailQuery.data && markMainRootMutation.mutate(detailQuery.data.id)}
  >
    设为主线
  </Button>
</div>
```

Add the modal submit handler:

```tsx
<DatabaseBackupNodeForm
  open={modalState !== null}
  mode={(modalState?.mode ?? "create-root") as DatabaseBackupNodeFormMode}
  initialValues={
    modalState?.mode === "edit" && detailQuery.data
      ? {
          name: detailQuery.data.name,
          database_name: detailQuery.data.database_name,
          odoo_version: detailQuery.data.odoo_version,
          note: detailQuery.data.note,
        }
      : undefined
  }
  submitting={createMutation.isPending || updateMutation.isPending}
  onCancel={() => setModalState(null)}
  onSubmit={async (values) => {
    if (!modalState) return;
    if (modalState.mode === "edit" && detailQuery.data) {
      await updateMutation.mutateAsync({
        nodeId: detailQuery.data.id,
        payload: {
          name: values.name,
          note: values.note,
        },
      });
      return;
    }

    await createMutation.mutateAsync({
      name: values.name,
      database_name: values.database_name,
      odoo_version: values.odoo_version,
      source_type: modalState.mode === "create-root" ? "root" : "branch",
      parent_id: modalState.mode === "create-child" ? modalState.parentId : null,
      is_main_root: modalState.mode === "create-root" && (treeQuery.data?.items.length ?? 0) === 0,
      note: values.note,
      file: values.file!,
    });
  }}
/>
```

Add styles to `apps/web/src/app/styles.css`:

```css
.database-backups-page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
```

- [ ] **Step 4: Run the page test to verify it passes**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/pages/database-backups/DatabaseBackupsPage.test.tsx
```

Expected: PASS for render, validation, edit, and main-root actions.

- [ ] **Step 5: Commit the interactive page behavior**

Run:

```bash
git add \
  apps/web/src/app/styles.css \
  apps/web/src/pages/database-backups/DatabaseBackupNodeForm.tsx \
  apps/web/src/pages/database-backups/DatabaseBackupsPage.test.tsx \
  apps/web/src/pages/database-backups/DatabaseBackupsPage.tsx
git commit -m "feat(database-backups): 新增节点创建编辑与主线切换操作"
```

## Task 7: Run Verification and Final Integration Checks

**Files:**
- Modify as needed: any file touched in Tasks 1-6 if verification reveals a mismatch

- [ ] **Step 1: Run the focused backend suite**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_database_backups_api.py tests/test_files_api.py -q
```

Expected: PASS with all database-backup API tests green and the existing file API regression test still green.

- [ ] **Step 2: Run the focused frontend suite**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run test -- src/tool-registry/index.test.ts src/pages/database-backups/DatabaseBackupsPage.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run the frontend production build**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run build
```

Expected: PASS with no TypeScript errors.

- [ ] **Step 4: Do a manual smoke check in the browser**

Run:

```bash
cd /Users/majianhang/Code/Company/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd /Users/majianhang/Code/Company/odoo-toolbox/apps/web
npm run dev -- --host 0.0.0.0 --port 5173
```

Expected manual results:

- `/database-backups` appears in the platform sidebar
- empty state appears before creating any nodes
- creating the first root node auto-selects it and marks it as the main root
- creating a child node nests it beneath the selected parent
- detail panel updates when selecting nodes
- the zip download button hits `/api/database-backups/nodes/{id}/zip`
- the guideline tab renders the three static sections

- [ ] **Step 5: Commit any verification-driven fixes and the final feature state**

Run:

```bash
git add apps/server apps/web
git commit -m "feat(database-backups): 完成数据库备份库模块实现"
```
