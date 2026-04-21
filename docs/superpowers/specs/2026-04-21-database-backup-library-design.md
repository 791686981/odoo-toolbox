# 数据库备份库设计文档

日期：2026-04-21  
项目：Odoo Toolbox  
主题：数据库 zip 备份版本树与规范页

## 1. 背景

团队在做 Odoo 开发和升级测试时，经常会导出数据库 zip 用于联调、验证和回归。当前工具箱已经具备通用文件上传能力，但缺少一个专门管理数据库备份版本关系的地方，导致以下问题：

- 主线数据库持续更新，但无法直观看到某个测试库是从哪个备份派生出来的
- 数据库 zip 与普通上传文件混在一起，缺少面向版本树的操作语义
- 团队缺少统一的数据库命名、使用和升级规范入口

本设计在 Odoo Toolbox 中新增一个独立的“数据库备份库”模块，用于管理数据库备份节点、主线根节点、分支关系和静态规范页。

## 2. 目标

### 2.1 目标

- 提供数据库备份版本树，支持根节点和分支节点
- 每个节点都绑定一个真实存在的 zip 备份文件
- 支持多个根节点，但前端始终突出一个人工指定的主线根节点
- 提供稳定的 zip 获取接口，供前端下载和后续自动化调用
- 提供一页静态规范文档，沉淀数据库命名、使用和升级规则

### 2.2 非目标

- 第一版不做数据库恢复、还原或新库创建
- 第一版不做节点删除
- 第一版不做父子关系重排
- 第一版不做 zip 替换
- 第一版不做规范页在线编辑
- 第一版不做对象存储、外链分享或权限细分

## 3. 总体方案

采用“独立备份节点模型 + 复用现有文件存储能力”的方案：

- 后端新增 `DatabaseBackupNode` 实体，专门表达数据库备份版本树
- zip 文件继续复用现有上传文件存储机制，节点通过 `zip_file_id` 关联到底层文件记录
- 对外接口以“备份节点”为中心，不直接暴露底层文件路径或强依赖底层 `file_id`
- 前端新增独立平台入口“数据库备份库”，默认展示版本树，并在同模块内提供静态规范页

这样做的原因：

- 保持“普通文件中心”和“数据库版本树”职责分离
- 未来可继续扩展恢复说明、标签、筛选、升级目标版本等能力
- zip 的存储实现未来可以从本地磁盘替换为对象存储，而不破坏业务接口

## 4. 领域模型

### 4.1 实体：`DatabaseBackupNode`

每条记录表示一个数据库备份版本节点。

建议字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `string(36)` | 主键 |
| `name` | `string(255)` | 节点名，可编辑 |
| `database_name` | `string(255)` | 数据库名 |
| `odoo_version` | `string(64)` | Odoo 版本，例如 `18.0` |
| `parent_id` | `string(36) \| null` | 父节点，空表示根节点 |
| `source_type` | `string(32)` | 节点来源类型，第一版取值 `root` / `branch` |
| `zip_file_id` | `string(36)` | 关联 `uploaded_files.id`，必填 |
| `is_main_root` | `boolean` | 是否主线根节点 |
| `created_by` | `string(100)` | 创建人 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |
| `note` | `text` | 备注，可编辑 |

### 4.2 约束规则

- 创建节点时必须上传 zip 文件，不允许空节点
- 只有根节点允许 `is_main_root = true`
- 同一时间只允许一个主线根节点
- `parent_id` 创建后不可修改
- `zip_file_id` 创建后不可修改
- `name` 和 `note` 允许修改
- 第一版不提供删除能力，避免误删破坏版本树

### 4.3 与现有模型关系

- `DatabaseBackupNode.zip_file_id -> UploadedFile.id`
- zip 文件的二进制内容继续落到现有上传目录
- 下载时通过备份节点接口间接定位到底层文件，不暴露真实磁盘路径

## 5. API 设计

第一版新增数据库备份模块 API，统一挂在 `/api/database-backups` 下。

### 5.1 查询整棵树

`GET /api/database-backups/tree`

用途：

- 返回全部根节点和子节点的树形结构
- 主线根节点排在首位，其他根节点按创建时间倒序排序

响应示意：

```json
{
  "main_root_id": "node_main",
  "items": [
    {
      "id": "node_main",
      "name": "prod-main-2026-04-21",
      "database_name": "prod_main",
      "odoo_version": "18.0",
      "source_type": "root",
      "is_main_root": true,
      "created_at": "2026-04-21T03:00:00Z",
      "children": [
        {
          "id": "node_branch_1",
          "name": "upgrade-18-202604",
          "database_name": "upgrade_18_test",
          "odoo_version": "18.0",
          "source_type": "branch",
          "is_main_root": false,
          "created_at": "2026-04-21T06:00:00Z",
          "children": []
        }
      ]
    }
  ]
}
```

### 5.2 创建节点

`POST /api/database-backups/nodes`

第一版采用 `multipart/form-data`，将节点元数据与 zip 文件一次提交，保证“节点创建成功”与“zip 已存储”保持原子性。

表单字段：

- `name`
- `database_name`
- `odoo_version`
- `source_type`
- `parent_id`（可空）
- `is_main_root`（仅根节点允许为 `true`）
- `note`
- `file`（zip 文件，必填）

行为规则：

- 若 `parent_id` 有值，则创建子节点
- 若 `parent_id` 为空，则创建根节点
- 若 `is_main_root = true`，必须同时满足“当前节点是根节点”
- 文件扩展名至少校验 `.zip`
- 节点与底层文件记录一起创建；任一失败则整体回滚

### 5.3 查询节点详情

`GET /api/database-backups/nodes/{id}`

响应包含节点字段、zip 元信息和稳定下载地址。

响应示意：

```json
{
  "id": "node_main",
  "name": "prod-main-2026-04-21",
  "database_name": "prod_main",
  "odoo_version": "18.0",
  "parent_id": null,
  "source_type": "root",
  "is_main_root": true,
  "note": "4 月 21 日主线备份，用于升级测试分支派生。",
  "created_at": "2026-04-21T03:00:00Z",
  "updated_at": "2026-04-21T03:00:00Z",
  "zip": {
    "file_id": "file_xxx",
    "filename": "prod-main-2026-04-21.zip",
    "size": 123456789,
    "mime_type": "application/zip",
    "sha256": "abc123",
    "download_url": "/api/database-backups/nodes/node_main/zip"
  }
}
```

### 5.4 修改节点元数据

`PATCH /api/database-backups/nodes/{id}`

允许修改：

- `name`
- `note`

禁止修改：

- `parent_id`
- `zip_file_id`
- `database_name`
- `odoo_version`
- `source_type`
- `is_main_root`

说明：

第一版将数据库名、Odoo 版本和来源类型也视为建档信息，不允许修改，确保节点记录具备档案性质。如果后续业务确实需要修正，可以在第二版引入更细粒度的“可修订字段”策略。

### 5.5 设置主线根节点

`POST /api/database-backups/nodes/{id}/mark-main-root`

行为：

- 仅根节点可被设置为主线根节点
- 设置成功后，其他根节点的 `is_main_root` 自动改为 `false`

### 5.6 获取 zip 文件

`GET /api/database-backups/nodes/{id}/zip`

行为：

- 直接返回 zip 二进制流
- 对外语义是“获取某个备份节点的 zip”
- 后端内部再通过 `zip_file_id` 定位到底层文件记录

设计原则：

- 不暴露服务器真实路径
- 不要求外部系统知道底层 `file_id`
- 保持未来替换存储实现时接口稳定

### 5.7 探测 zip 元信息

`HEAD /api/database-backups/nodes/{id}/zip`

用途：

- 不返回文件内容，仅返回响应头
- 便于自动化脚本先确认文件是否存在、大小是否变化，再决定是否下载

建议头信息：

- `Content-Length`
- `Content-Type`
- `ETag`
- `X-File-Sha256`
- `Last-Modified`

### 5.8 规范页

第一版规范页为前端静态内容，不新增专门后端接口。

原因：

- 内容固定，跟代码发布即可
- 降低第一版实现复杂度
- 避免为只读文档增加无意义的数据库和 API 维护成本

## 6. 前端方案

### 6.1 模块入口

在平台侧边栏中新增“数据库备份库”入口，归类为平台能力，和“运行记录”“文件中心”“系统设置”同级。

### 6.2 模块内部视图

模块内提供两个视图：

- `版本树`
- `命名与升级规范`

默认进入 `版本树`。

### 6.3 版本树页面

页面采用“左树右详情”结构：

- 左侧显示根节点和子节点树
- 主线根节点固定高亮并排在首位
- 其他根节点继续展示，但弱化优先级
- 右侧显示当前节点详情、zip 信息和操作按钮

右侧详情区展示：

- 节点名
- 数据库名
- Odoo 版本
- 来源类型
- 创建时间
- 备注
- zip 文件名、大小、sha256
- 下载按钮

主要操作：

- 新建根节点
- 新增子节点
- 修改节点名和备注
- 设置主线根节点
- 下载 zip

### 6.4 规范页

规范页为静态展示页面，建议至少包含以下章节：

1. 数据库命名规范
2. 主线与分支使用规则
3. 升级测试、回写与废弃规则

建议使用清晰的卡片分段或章节排版，不做在线编辑。

## 7. 文件策略

### 7.1 存储策略

- 继续复用现有上传目录和 `UploadedFile` 记录
- 节点创建时调用模块内部服务，把 zip 写入存储并生成 `UploadedFile`
- `DatabaseBackupNode` 只持有关联关系，不直接持久化真实路径

### 7.2 对外访问策略

- 对外统一通过 `/api/database-backups/nodes/{id}/zip` 获取 zip
- 不鼓励外部依赖 `/api/files/{file_id}/download`
- `file_id` 可以作为内部实现细节存在于详情响应中，但不作为业务主入口

这样可以让未来的恢复任务、对象存储迁移或归档策略切换都保持兼容。

## 8. 错误处理

第一版需要明确以下错误场景：

- 上传文件不是 zip：返回 400
- 创建子节点时父节点不存在：返回 404
- 尝试将非根节点设为主线根节点：返回 400
- 查询不存在的节点：返回 404
- 节点关联 zip 丢失：详情和下载接口返回 404，并提示归档文件缺失
- 尝试修改不可变字段：返回 400

前端应在新建节点时给出明确错误提示，避免用户误以为节点已创建但文件未归档。

## 9. 测试策略

### 9.1 后端测试

至少覆盖以下场景：

- 创建根节点成功
- 创建子节点成功
- 非 zip 文件创建失败
- 父节点不存在时创建失败
- 同一时间仅允许一个主线根节点
- 非根节点不可设置为主线根节点
- `PATCH` 仅允许修改 `name` 和 `note`
- `GET tree` 返回树结构正确且主线根节点排第一
- `GET /zip` 和 `HEAD /zip` 可正常返回

### 9.2 前端测试

至少覆盖以下场景：

- 页面能渲染版本树和当前节点详情
- 主线根节点展示优先级正确
- 新建节点表单要求 zip 必填
- 仅允许编辑节点名和备注
- 规范页能正确展示静态内容

## 10. 迭代边界

第一版完成后，可按优先级继续扩展：

1. 节点标签与筛选
2. 恢复说明字段和推荐操作命令
3. 归档校验与健康状态
4. 恢复任务接口，例如 `POST /api/database-backups/nodes/{id}/restore-jobs`
5. 对象存储和外部下载签名地址

## 11. 验收标准

当以下条件全部成立时，可认为第一版设计目标达成：

- 用户可以创建根节点和子节点，且创建时必须上传 zip
- 工具箱能以版本树方式展示数据库备份关系
- 系统中任意时刻只有一个主线根节点
- 用户可以查看节点详情并通过节点接口下载 zip
- 用户无法修改父子关系和替换 zip
- 用户可以在工具箱内查看静态规范页
