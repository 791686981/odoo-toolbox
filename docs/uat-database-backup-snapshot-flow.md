# UAT 数据库快照流程

## 阅读对象与用途

本文面向 UAT 执行人员、Odoo worktree 脚本维护者和 Toolbox 运维人员，用于完成 UAT 数据库快照的目录准备、zip 上传、节点 ID 交付和恢复配置生成。

## 备份树结构

UAT 快照统一沉淀在四层结构中：

```text
UAT
├── 项目管理
│   └── EPIC-04 WBS 拆解与执行任务基础
│       ├── 基线快照 - 2026-05-08
│       ├── ISSUE-001 复现现场
│       └── ISSUE-001 回归复测
├── 工时管理
└── 采购管理
```

- `UAT`、业务域、需求节点是 `folder`，不绑定 zip。
- 快照节点是 `snapshot`，必须绑定 Odoo 原生数据库备份 zip。
- 只有 `snapshot` 节点可以下载 zip，也只有 `snapshot` 节点可以生成恢复 `.env`。
- `domain` 必须属于标准 UAT 业务域；“模版”不是业务域。

## REST 与 MCP 分工

REST 负责传输和持久化大文件：

- `POST /api/database-backups/uat/snapshots`
  使用 `multipart/form-data` 上传 Odoo 原生 zip，并创建快照节点。
- `GET /api/database-backups/nodes/{node_id}/zip`
  下载快照 zip。
- `HEAD /api/database-backups/nodes/{node_id}/zip`
  获取 zip 大小、ETag 和 `X-File-Sha256`。

MCP 负责轻量编排和查询：

- `ensure_uat_tree`
  幂等创建 `UAT / 业务域 / 需求` 目录。
- `list_database_backup_tree`
  查询备份树，可只看 `UAT` 根。
- `get_database_backup_node`
  查询节点详情。
- `prepare_uat_snapshot_upload`
  返回 REST 上传地址和推荐表单字段，不创建节点。
- `build_odoo_restore_env`
  基于快照节点 ID 生成恢复 `.env` 片段。

MCP 不传输 zip，也不执行 Odoo 容器命令。

## 鉴权

Web 前端继续使用登录 Cookie。

脚本写入目录、更新元数据或上传快照时使用：

```text
Authorization: Bearer <TOOLBOX_DATABASE_BACKUP_WRITE_API_KEY>
```

脚本下载 zip 时使用：

```text
Authorization: Bearer <TOOLBOX_DOWNLOAD_API_KEY>
```

MCP 继续使用：

```text
Authorization: Bearer <TOOLBOX_MCP_API_KEY>
```

## 推荐 UAT 操作流程

1. 在 Odoo UAT worktree 中确认当前分支、commit 和待测需求。
2. 通过 MCP `ensure_uat_tree` 创建或确认业务域和需求目录。
3. 执行项目侧 `make uat-dump`，导出 Odoo 原生 zip，包含数据库和 filestore。
4. 执行项目侧 `make uat-upload`，调用 `POST /api/database-backups/uat/snapshots` 上传 zip。
5. 记录返回的 `node_id`、`sha256`、`git_branch`、`git_commit` 和 `restore_env`。
6. 在 UAT 测试计划中写入快照节点 ID，作为可复测交付物。

## 上传表单字段

`POST /api/database-backups/uat/snapshots` 使用 `multipart/form-data`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `domain` | 是 | 标准 UAT 业务域 |
| `requirement_title` | 是 | 需求目录标题 |
| `snapshot_name` | 是 | 快照节点名称 |
| `snapshot_type` | 是 | `baseline`、`issue_reproduction`、`regression` 或 `ad_hoc` |
| `file` | 是 | Odoo 原生数据库备份 zip |
| `parent_id` | 否 | 需求目录 ID；为空时按 domain 和 requirement 自动定位 |
| `notion_url` | 否 | Notion 页面 URL，仅作为元数据 |
| `base_node_id` | 否 | 基于哪个快照派生 |
| `git_branch` | 否 | UAT worktree 分支 |
| `git_commit` | 否 | UAT worktree commit |
| `odoo_version` | 否 | Odoo 版本 |
| `database_name` | 否 | 目标数据库名 |
| `note` | 否 | 快照备注 |
| `metadata` | 否 | JSON 对象字符串，服务端浅合并元数据 |

## 恢复配置

快照创建成功或调用 `build_odoo_restore_env` 后返回可直接写入 Odoo worktree `.env` 的片段：

```text
ODOO_RESTORE_NODE_ID=<node_id>
ODOO_RESTORE_IF_EXISTS=overwrite
ODOO_RESTORE_NEUTRALIZE=false
ODOO_RESTORE_TARGET_DB=<database_name>
```

`ODOO_RESTORE_TARGET_DB` 仅在快照节点保存了 `database_name` 时返回。
