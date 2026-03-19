# Gettext Translation Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增一个独立的 Gettext 翻译工具，支持上传 `.po/.pot`、按策略筛选待翻条目、人工修订，并导出保真的 `.po` 文件。

**Architecture:** 后端新增 `gettext_translation` 工具包，沿用平台现有的 `UploadedFile`、`ToolRun`、Celery 和文件导出链路，工具私有状态单独建模。解析和导出统一使用 `polib`，不手写 Gettext 文本拼接。前端新增独立工具页，交互风格尽量与 CSV 工具保持一致，但针对 `.po/.pot` 加入处理模式与 plural 编辑能力。

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Pydantic, `polib`, React, Vite, TypeScript, Ant Design, React Query, Vitest

---

### Task 1: 引入 `polib` 并完成 Gettext 解析/导出基础能力

**Files:**
- Modify: `apps/server/pyproject.toml`
- Modify: `apps/server/uv.lock`
- Create: `apps/server/app/tools/gettext_translation/__init__.py`
- Create: `apps/server/app/tools/gettext_translation/parser.py`
- Create: `apps/server/app/tools/gettext_translation/exporter.py`
- Test: `apps/server/tests/test_gettext_translation_core.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_parse_pot_collects_context_plural_and_flags(tmp_path: Path) -> None:
    source = tmp_path / "sample.pot"
    source.write_text(
        '''
msgid ""
msgstr ""
"Project-Id-Version: demo\\n"

#, fuzzy
msgctxt "button"
msgid "Save"
msgstr ""

msgid "File"
msgid_plural "Files"
msgstr[0] ""
msgstr[1] ""
'''.strip(),
        encoding="utf-8",
    )

    from app.tools.gettext_translation.parser import parse_gettext_file

    parsed = parse_gettext_file(source)

    assert parsed.file_type == "pot"
    assert len(parsed.entries) == 2
    assert parsed.entries[0].msgctxt == "button"
    assert parsed.entries[0].is_fuzzy is True
    assert parsed.entries[1].is_plural is True


def test_export_po_prefers_manual_edits_and_preserves_metadata(tmp_path: Path) -> None:
    source = tmp_path / "sample.po"
    source.write_text(
        '''
msgid ""
msgstr ""
"Language: en_US\\n"

msgid "Save"
msgstr "Save"
'''.strip(),
        encoding="utf-8",
    )

    from app.tools.gettext_translation.exporter import export_gettext_file
    from app.tools.gettext_translation.parser import parse_gettext_file

    parsed = parse_gettext_file(source)
    content = export_gettext_file(
        parsed,
        target_language="zh_CN",
        entry_results={1: {"translated_value": "保存", "edited_value": "保存按钮"}},
    )

    assert 'Language: zh_CN\\n' in content.decode("utf-8")
    assert 'msgstr "保存按钮"' in content.decode("utf-8")
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_core.py -q`
Expected: FAIL，提示缺少 `polib` 依赖或 `app.tools.gettext_translation` 模块不存在

**Step 3: Write minimal implementation**

```python
# apps/server/app/tools/gettext_translation/parser.py
from dataclasses import dataclass
from pathlib import Path

import polib


@dataclass
class ParsedGettextEntry:
    entry_index: int
    msgctxt: str
    msgid: str
    msgid_plural: str
    msgstr: str
    msgstr_plural: dict[int, str]
    flags: list[str]
    comment: str
    tcomment: str
    occurrences: list[tuple[str, str]]
    is_plural: bool
    is_fuzzy: bool


@dataclass
class ParsedGettextFile:
    file_type: str
    path: Path
    metadata: dict[str, str]
    entries: list[ParsedGettextEntry]


def parse_gettext_file(path: Path) -> ParsedGettextFile:
    catalog = polib.pofile(path)
    entries = []
    for index, entry in enumerate(catalog):
        if entry.obsolete or not entry.msgid:
            continue
        entries.append(
            ParsedGettextEntry(
                entry_index=index + 1,
                msgctxt=entry.msgctxt or "",
                msgid=entry.msgid,
                msgid_plural=entry.msgid_plural or "",
                msgstr=entry.msgstr or "",
                msgstr_plural={int(key): value for key, value in entry.msgstr_plural.items()},
                flags=list(entry.flags),
                comment=entry.comment or "",
                tcomment=entry.tcomment or "",
                occurrences=list(entry.occurrences),
                is_plural=bool(entry.msgid_plural),
                is_fuzzy="fuzzy" in entry.flags,
            )
        )
    return ParsedGettextFile(
        file_type=path.suffix.lstrip("."),
        path=path,
        metadata=dict(catalog.metadata),
        entries=entries,
    )
```

```python
# apps/server/app/tools/gettext_translation/exporter.py
from io import BytesIO

import polib


def export_gettext_file(parsed, target_language: str, entry_results: dict[int, dict]) -> bytes:
    catalog = polib.pofile(parsed.path)
    catalog.metadata["Language"] = target_language
    for index, entry in enumerate(catalog):
        if entry.obsolete or not entry.msgid:
            continue
        result = entry_results.get(index + 1, {})
        value = result.get("edited_value") or result.get("translated_value") or entry.msgstr
        entry.msgstr = value
    buffer = BytesIO()
    buffer.write(catalog.__unicode__().encode("utf-8"))
    return buffer.getvalue()
```

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_core.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/server/pyproject.toml apps/server/uv.lock apps/server/app/tools/gettext_translation/__init__.py apps/server/app/tools/gettext_translation/parser.py apps/server/app/tools/gettext_translation/exporter.py apps/server/tests/test_gettext_translation_core.py
git commit -m "feat: add gettext parser and exporter"
```

### Task 2: 建立待翻译项筛选、分块逻辑和工具私有模型

**Files:**
- Create: `apps/server/app/models/tools/__init__.py`
- Create: `apps/server/app/models/tools/gettext_translation.py`
- Modify: `apps/server/app/models/__init__.py`
- Create: `apps/server/app/tools/gettext_translation/schemas.py`
- Create: `apps/server/app/tools/gettext_translation/task_runner.py`
- Test: `apps/server/tests/test_gettext_translation_core.py`

**Step 1: Write the failing test**

```python
def test_build_gettext_chunks_respects_mode_and_skips_obsolete() -> None:
    from app.tools.gettext_translation.schemas import GettextEntryCandidate
    from app.tools.gettext_translation.task_runner import build_gettext_chunks

    candidates = [
        GettextEntryCandidate(entry_index=1, msgid="Save", msgstr="", is_plural=False, is_fuzzy=False, obsolete=False),
        GettextEntryCandidate(entry_index=2, msgid="Cancel", msgstr="取消", is_plural=False, is_fuzzy=True, obsolete=False),
        GettextEntryCandidate(entry_index=3, msgid="Archive", msgstr="归档", is_plural=False, is_fuzzy=False, obsolete=False),
    ]

    chunks = build_gettext_chunks(candidates, chunk_size=1, translation_mode="blank_and_fuzzy")

    assert [[item.entry_index for item in chunk] for chunk in chunks] == [[1], [2]]
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_core.py -q`
Expected: FAIL，提示 `GettextEntryCandidate` 或 `build_gettext_chunks` 未定义

**Step 3: Write minimal implementation**

```python
# apps/server/app/tools/gettext_translation/schemas.py
from pydantic import BaseModel


class GettextEntryCandidate(BaseModel):
    entry_index: int
    msgid: str
    msgstr: str
    is_plural: bool
    is_fuzzy: bool
    obsolete: bool = False
```

```python
# apps/server/app/tools/gettext_translation/task_runner.py
def should_translate_entry(candidate, translation_mode: str) -> bool:
    if candidate.obsolete:
        return False
    if translation_mode == "overwrite_all":
        return True
    if translation_mode == "blank_and_fuzzy":
        return not candidate.msgstr.strip() or candidate.is_fuzzy
    return not candidate.msgstr.strip()


def build_gettext_chunks(candidates, chunk_size: int, translation_mode: str):
    selected = [item for item in candidates if should_translate_entry(item, translation_mode)]
    return [selected[index : index + chunk_size] for index in range(0, len(selected), chunk_size)]
```

```python
# apps/server/app/models/tools/gettext_translation.py
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base
from app.models.entities import new_id, utcnow


class GettextTranslationRun(Base):
    __tablename__ = "gettext_translation_runs"
    id = Column(String(36), primary_key=True, default=new_id)
    tool_id = Column(String(100), nullable=False, default="gettext-translation")
    status = Column(String(50), nullable=False, default="queued")
    progress = Column(Integer, nullable=False, default=0)
    input_file_type = Column(String(10), nullable=False)
    translation_mode = Column(String(32), nullable=False)
    source_language = Column(String(32), nullable=False)
    target_language = Column(String(32), nullable=False)
    context_text = Column(Text, nullable=False, default="")
    chunk_size = Column(Integer, nullable=False)
    concurrency = Column(Integer, nullable=False)
    total_entries = Column(Integer, nullable=False, default=0)
    processed_entries = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=False, default="")
    uploaded_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    exported_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
```

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_core.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/server/app/models/tools/__init__.py apps/server/app/models/tools/gettext_translation.py apps/server/app/models/__init__.py apps/server/app/tools/gettext_translation/schemas.py apps/server/app/tools/gettext_translation/task_runner.py apps/server/tests/test_gettext_translation_core.py
git commit -m "feat: add gettext run models and chunking"
```

### Task 3: 接通 Gettext API、任务执行和工具注册

**Files:**
- Create: `apps/server/app/schemas/gettext_translation.py`
- Create: `apps/server/app/tools/gettext_translation/manifest.py`
- Create: `apps/server/app/tools/gettext_translation/prompt_builder.py`
- Create: `apps/server/app/tools/gettext_translation/router.py`
- Modify: `apps/server/app/tools/registry.py`
- Modify: `apps/server/app/api/jobs.py`
- Modify: `apps/server/app/models/platform/tool_artifact.py`
- Test: `apps/server/tests/test_gettext_translation_api.py`
- Modify: `apps/server/tests/test_tools_api.py`

**Step 1: Write the failing test**

```python
def test_gettext_translation_flow_supports_po_and_pot(tmp_path: Path) -> None:
    import io
    from fastapi.testclient import TestClient

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
        upload_response = client.post(
            "/api/files/upload",
            files={"file": ("sample.pot", io.BytesIO(b'msgid ""\\nmsgstr ""\\n\\nmsgid "Save"\\nmsgstr ""\\n'), "text/plain")},
        )
        run_response = client.post(
            "/api/tools/gettext-translation/jobs",
            json={
                "uploaded_file_id": upload_response.json()["id"],
                "source_language": "en_US",
                "target_language": "zh_CN",
                "context_text": "统一用 Odoo 后台术语。",
                "translation_mode": "blank",
                "chunk_size": 10,
                "concurrency": 1,
            },
        )
        assert run_response.status_code == 200
        assert run_response.json()["tool_id"] == "gettext-translation"
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_api.py apps/server/tests/test_tools_api.py -q`
Expected: FAIL，提示路由、manifest 或响应模型缺失

**Step 3: Write minimal implementation**

```python
# apps/server/app/tools/gettext_translation/manifest.py
TOOL_MANIFEST = {
    "id": "gettext-translation",
    "title": "Gettext 翻译",
    "description": "上传 .po/.pot，按策略翻译、人工修订并导出 .po。",
    "route": "/tools/gettext-translation",
    "icon": "translation",
    "category": "translation",
    "enabled": True,
    "order": 12,
    "capabilities": ["upload", "translation", "edit", "export"],
}
```

```python
# apps/server/app/tools/gettext_translation/router.py
from fastapi import APIRouter

router = APIRouter(prefix="/tools/gettext-translation", tags=["gettext-translation"])


@router.post("/jobs")
def create_gettext_job():
    ...
```

```python
# apps/server/app/tools/registry.py
from app.tools.gettext_translation.manifest import TOOL_MANIFEST as GETTEXT_TRANSLATION_TOOL_MANIFEST
from app.tools.gettext_translation.router import router as gettext_translation_router

REGISTERED_TOOLS = [
    ToolRegistration(manifest=CSV_TRANSLATION_TOOL_MANIFEST, router=csv_translation_router),
    ToolRegistration(manifest=GETTEXT_TRANSLATION_TOOL_MANIFEST, router=gettext_translation_router),
]
```

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_api.py apps/server/tests/test_tools_api.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/server/app/schemas/gettext_translation.py apps/server/app/tools/gettext_translation/manifest.py apps/server/app/tools/gettext_translation/prompt_builder.py apps/server/app/tools/gettext_translation/router.py apps/server/app/tools/registry.py apps/server/app/api/jobs.py apps/server/app/models/platform/tool_artifact.py apps/server/tests/test_gettext_translation_api.py apps/server/tests/test_tools_api.py
git commit -m "feat: add gettext translation backend flow"
```

### Task 4: 扩展前端类型、API 客户端和工具注册

**Files:**
- Modify: `apps/web/src/shared/api/types.ts`
- Modify: `apps/web/src/shared/api/client.ts`
- Create: `apps/web/src/tools/gettext-translation/index.ts`
- Modify: `apps/web/src/tools/registry/index.ts`
- Modify: `apps/web/src/tool-registry/index.ts`
- Test: `apps/web/src/tools/registry/index.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

import { getToolRunDetailPath, toolPageRegistrations } from "./index";

describe("toolPageRegistrations", () => {
  it("registers the gettext translation page as a standard tool page", () => {
    expect(toolPageRegistrations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "gettext-translation",
          route: "/tools/gettext-translation",
        }),
      ]),
    );
  });

  it("builds the gettext translation run detail path", () => {
    expect(getToolRunDetailPath("gettext-translation", "run-123")).toBe(
      "/tools/gettext-translation?runId=run-123",
    );
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm test -- src/tools/registry/index.test.ts`
Expected: FAIL，提示 `gettext-translation` 未注册

**Step 3: Write minimal implementation**

```ts
// apps/web/src/tools/gettext-translation/index.ts
import { GettextTranslationPage } from "./GettextTranslationPage";

export const gettextTranslationToolPage = {
  id: "gettext-translation",
  route: "/tools/gettext-translation",
  component: GettextTranslationPage,
  buildRunDetailPath: (runId: string) => `/tools/gettext-translation?runId=${encodeURIComponent(runId)}`,
};
```

```ts
// apps/web/src/tools/registry/index.ts
import { csvTranslationToolPage } from "../csv-translation";
import { gettextTranslationToolPage } from "../gettext-translation";

export const toolPageRegistrations = [csvTranslationToolPage, gettextTranslationToolPage];
```

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm test -- src/tools/registry/index.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/src/shared/api/types.ts apps/web/src/shared/api/client.ts apps/web/src/tools/gettext-translation/index.ts apps/web/src/tools/registry/index.ts apps/web/src/tool-registry/index.ts apps/web/src/tools/registry/index.test.ts
git commit -m "feat: register gettext translation tool in web"
```

### Task 5: 实现 Gettext 工具页和人工修订交互

**Files:**
- Create: `apps/web/src/tools/gettext-translation/GettextTranslationPage.tsx`
- Create: `apps/web/src/tools/gettext-translation/GettextTranslationPage.test.tsx`
- Modify: `apps/web/src/routes/index.tsx`
- Modify: `apps/web/src/app/styles.css`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { GettextTranslationPage } from "./GettextTranslationPage";

test("shows translation mode only for po uploads", async () => {
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <GettextTranslationPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );

  expect(screen.getByText("上传与任务设置")).toBeInTheDocument();
  expect(screen.queryByLabelText("处理模式")).not.toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm test -- src/tools/gettext-translation/GettextTranslationPage.test.tsx`
Expected: FAIL，提示页面组件不存在

**Step 3: Write minimal implementation**

```tsx
export function GettextTranslationPage() {
  return (
    <div className="page-stack">
      <Card className="panel-card step-card">
        <Typography.Text className="section-kicker">Step 01</Typography.Text>
        <Typography.Title level={3} className="panel-title">
          上传与任务设置
        </Typography.Title>
      </Card>
    </div>
  );
}
```

后续在同一任务内补齐：

- `.po/.pot` 上传
- `.po` 时显示处理模式
- 结果表格
- plural 详情编辑弹窗
- 导出按钮

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm test -- src/tools/gettext-translation/GettextTranslationPage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/src/tools/gettext-translation/GettextTranslationPage.tsx apps/web/src/tools/gettext-translation/GettextTranslationPage.test.tsx apps/web/src/routes/index.tsx apps/web/src/app/styles.css
git commit -m "feat: add gettext translation workspace"
```

### Task 6: 端到端补强与回归验证

**Files:**
- Modify: `apps/server/tests/test_gettext_translation_api.py`
- Modify: `apps/server/tests/test_gettext_translation_core.py`
- Modify: `apps/web/src/tools/gettext-translation/GettextTranslationPage.test.tsx`
- Optional: `README.md`

**Step 1: Write the failing test**

```python
def test_exported_po_preserves_plural_and_context(tmp_path: Path) -> None:
    ...
```

```tsx
test("supports editing a plural entry in the detail modal", async () => {
  ...
});
```

**Step 2: Run test to verify it fails**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_core.py apps/server/tests/test_gettext_translation_api.py -q`
Expected: FAIL，暴露 plural 回填或上下文显示问题

Run: `cd apps/web && npm test -- src/tools/gettext-translation/GettextTranslationPage.test.tsx`
Expected: FAIL，暴露 plural 编辑交互缺口

**Step 3: Write minimal implementation**

```python
def merge_plural_values(original: dict[int, str], translated: dict[int, str], edited: dict[int, str]) -> dict[int, str]:
    merged = {}
    for key in sorted(set(original) | set(translated) | set(edited)):
        merged[key] = edited.get(key) or translated.get(key) or original.get(key, "")
    return merged
```

```tsx
<Modal open={pluralEditorOpen} title="复数翻译编辑">
  {/* 为每个 plural index 渲染一个输入框 */}
</Modal>
```

**Step 4: Run test to verify it passes**

Run: `UV_CACHE_DIR=/tmp/uv-cache uv run --project apps/server --with pytest pytest apps/server/tests/test_gettext_translation_core.py apps/server/tests/test_gettext_translation_api.py apps/server/tests/test_tools_api.py -q`
Expected: PASS

Run: `cd apps/web && npm test`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/server/tests/test_gettext_translation_api.py apps/server/tests/test_gettext_translation_core.py apps/web/src/tools/gettext-translation/GettextTranslationPage.test.tsx README.md
git commit -m "test: complete gettext translation coverage"
```

## Implementation Notes

- 任何 Gettext 文本读写都不要绕开 `polib`
- `.pot` 导出产物一律为 `.po`
- 表格中的普通 entry 可以直接内联编辑
- plural entry 必须走详情弹窗或抽屉，避免把多复数位压扁成一个文本框
- 不要重构现有 CSV 工具，除非是工具注册或共享 API 类型的必要变更
- 真实回归时至少拿一次 [dms.pot](/Users/majianhang/Code/Playground/odoo-toolbox/docs/dms.pot) 跑通上传、翻译、导出链路
