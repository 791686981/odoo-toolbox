# Gettext 翻译工具设计

## 背景

当前项目已经具备一个可用的 `CSV 翻译` 工具，能够完成上传、AI 翻译、人工修订、导出和运行记录追踪。但 Odoo 模块翻译的常见输入并不只有 CSV，还包括标准 Gettext 文件：

- `.pot`：翻译模板，通常 `msgstr` 为空
- `.po`：已有翻译文件，可能包含已翻译项、`fuzzy` 标记、plural、context 和注释

仓库中的 [dms.pot](/Users/majianhang/Code/Playground/odoo-toolbox/docs/dms.pot) 已经是一个典型样本。为了让工具箱更贴近 Odoo 实际开发场景，需要新增一个独立的 Gettext 翻译工具，而不是把 `.po/.pot` 强行塞进现有 CSV 模型。

## 目标

- 新增一个独立的 Gettext 翻译工具，支持上传 `.pot` 或 `.po`
- `.pot` 可生成新的目标语言 `.po`
- `.po` 可继续补翻、人工修订并重新导出 `.po`
- 支持用户选择处理策略，而不是写死覆盖逻辑
- 解析与导出优先使用成熟库，避免手写文本解析破坏文件结构
- 继续复用现有平台能力：登录、文件上传、运行记录、文件中心、Celery 执行框架

## 非目标

- 首版不支持 `.mo` 编译
- 首版不支持多文件批处理
- 首版不支持翻译记忆库、术语库自动维护
- 首版不做源码扫描或字符串提取
- 首版不把 `.po/.pot` 和 CSV 合并成一个“通用翻译工具”

## 方案选择

### 方案 A：独立 Gettext 工具，底层使用 `polib`

这是推荐方案。

优点：

- 能正确处理 Gettext 语义：header、comments、flags、occurrences、`msgctxt`、plural、obsolete
- 导出时不需要自己拼接文本，结构保真更高
- 工具边界清晰，不会污染现有 CSV 数据模型
- 后续如果要扩展 `fuzzy`、plural 编辑体验，演进路径更顺

缺点：

- 需要新增一套工具私有模型和结果页，而不是直接照搬 CSV 行模型

### 方案 B：先抽象通用翻译引擎，再同时服务 CSV 与 Gettext

优点：

- 长期看架构更统一

缺点：

- 当前仓库仍在平台化过程中，前置抽象成本高
- 首版交付速度会明显变慢

### 方案 C：把 `.po/.pot` 转成类表格中间格式，尽量复用 CSV 工具

优点：

- UI 复用度高，首版表面改动少

缺点：

- 容易扭曲 Gettext 结构
- plural、`msgctxt`、flags、header 的映射会很别扭
- 导出保真风险最高

## 结论

采用方案 A：新增独立工具 `gettext-translation`，解析与导出统一使用 `polib`。

## 工具定位

### 工具 ID

`gettext-translation`

### 路由

`/tools/gettext-translation`

### 用户场景

- 上传 Odoo 模块的 `.pot`，生成指定目标语言的 `.po`
- 上传已有 `.po`，只补翻空白项，或补翻 `fuzzy`，或全量重翻
- 在结果工作台逐条人工修订后导出 `.po`

## 首版功能范围

### 输入

- 支持 `.po`
- 支持 `.pot`

### 处理模式

针对 `.po` 提供可选策略：

- 只翻空白 `msgstr`
- 翻空白 `msgstr` 和 `fuzzy`
- 全量覆盖

针对 `.pot`：

- 将所有可翻译 entry 视为待处理项
- 最终导出为新的 `.po`

### 结果工作台

- 展示可翻译 entry
- 支持逐条人工修订
- 支持查看上下文信息
- 支持导出 `.po`

## 技术选型

### 解析与导出

使用 `polib` 作为核心库。

选择理由：

- 是 Python 生态中处理 `.po/.pot` 的成熟库
- 支持读取、修改和写回 header、metadata、flags、comments、plural、obsolete 等结构
- 比手写正则和字符串拼接更稳

### 平台复用

继续复用现有平台能力：

- `UploadedFile`
- `ToolRun`
- 文件中心与下载接口
- Celery 异步执行模式
- 前端壳布局、运行记录、工具注册

## 数据模型设计

平台公共模型不新增特殊字段，继续复用现有 `UploadedFile` 和 `ToolRun`。

工具私有模型新增如下：

### `GettextTranslationRun`

保存一次 Gettext 翻译任务的整体状态。

建议字段：

- `id`
- `tool_id`
- `status`
- `progress`
- `source_language`
- `target_language`
- `context_text`
- `input_file_type`
- `translation_mode`
- `chunk_size`
- `concurrency`
- `total_entries`
- `processed_entries`
- `error_message`
- `uploaded_file_id`
- `exported_file_id`
- `created_by`
- `created_at`
- `updated_at`

### `GettextTranslationEntry`

保存每个待工作 entry 的业务状态。

建议字段：

- `id`
- `run_id`
- `entry_index`
- `msgctxt`
- `msgid`
- `msgid_plural`
- `msgstr`
- `msgstr_plural`
- `translated_value`
- `translated_plural_values`
- `edited_value`
- `edited_plural_values`
- `occurrences`
- `flags`
- `comment`
- `tcomment`
- `previous_msgid`
- `status`
- `is_plural`
- `is_fuzzy`
- `created_at`
- `updated_at`

说明：

- 数据库存的是“工作态”，不是完整文件快照
- 复杂字段可用 JSON 保存，例如 plural、occurrences、flags

### `GettextTranslationChunk`

用于沿用现有分块执行模式。

建议字段：

- `id`
- `run_id`
- `chunk_index`
- `entry_ids`
- `entry_count`
- `status`
- `error_message`
- `created_at`
- `updated_at`

## 后端设计

### 新工具目录

建议新增：

```text
apps/server/app/tools/gettext_translation/
  __init__.py
  manifest.py
  router.py
  parser.py
  exporter.py
  task_runner.py
  prompt_builder.py
  schemas.py
```

### 解析策略

解析阶段通过 `polib` 读取文件，并做以下处理：

- 识别文件类型为 `.po` 或 `.pot`
- 识别 header entry
- 跳过 obsolete entry
- 保留 comments、flags、occurrences、`msgctxt`、plural
- 为每个可翻译 entry 生成稳定的工作记录

### 待翻译项筛选规则

#### `.pot`

- 所有非 obsolete、非 header、存在 `msgid` 的 entry 均可进入待翻译集合

#### `.po`

根据用户选择的模式筛选：

- `blank`：只处理空白 `msgstr`
- `blank_and_fuzzy`：处理空白 `msgstr` 和 `fuzzy` entry
- `overwrite_all`：全部可翻译 entry 都进入待处理集合

### 翻译执行

执行模型沿用现有 chunk 机制：

1. 创建 run、entry、chunk
2. 启动 Celery 任务
3. 按 chunk 拉取 entry
4. 为每个 chunk 组织 prompt
5. 将 AI 返回结果写入 entry 的工作字段
6. 更新进度

### Prompt 设计

AI 翻译输入中应包含：

- 目标语言
- 用户填写的术语或背景说明
- `msgid`
- `msgctxt`
- comments
- occurrences
- plural 信息
- 当前已有译文（针对 `.po`）

输出结构建议继续使用结构化响应，不返回自由文本。

### 导出策略

导出时重新读取原始上传文件，并基于 `polib` 对象回填结果：

- 普通 entry：优先写入人工修订值，其次 AI 结果，最后保留原值
- plural entry：按 plural 索引回填
- `.pot` 导出时生成新的 `.po`
- `.po` 导出时保留原有结构，只更新翻译内容

### 导出保真原则

- 不手写拼接 `.po` 文本
- 原始 header、metadata、comments、flags、occurrences、`msgctxt`、plural 结构尽量原样保留
- 仅修改译文和必要的语言元信息

## 前端设计

### 新工具目录

建议新增：

```text
apps/web/src/tools/gettext-translation/
  index.ts
  GettextTranslationPage.tsx
```

### 页面结构

首版页面延续现有 CSV 工具的三段式体验：

1. 上传与任务设置
2. 术语/背景说明
3. 结果工作台

### 上传与任务设置

字段建议：

- 文件上传：仅允许 `.po,.pot`
- 源语言
- 目标语言
- 分块大小
- 并发数
- 处理模式

处理模式在上传 `.pot` 时可隐藏或禁用，在上传 `.po` 时显示。

### 术语/背景说明

首版不强制生成 AI 背景说明，直接提供可编辑文本区域，供用户输入：

- 术语偏好
- 风格要求
- Odoo 专有名词约定

这样可以减少一条非必要依赖链，优先把 `.po/.pot` 主流程做稳。

### 结果工作台

建议字段：

- 序号
- `msgctxt`
- `msgid`
- 当前译文
- AI 译文
- 人工修订
- 状态

对 plural entry：

- 表格中显示摘要
- 点击进入弹窗或抽屉进行多复数位编辑

这是首版需要刻意做的差异化处理，避免把 plural 结构粗暴压扁成一个文本框。

## 文件与运行记录集成

- 新工具 manifest 注册到后端工具注册中心
- 前端工具页注册到 `toolPageRegistrations`
- 创建任务时同步写入 `ToolRun`
- 导出后创建 `ToolArtifact`
- 运行记录页可跳转回 Gettext 工具详情

## 错误处理

### 上传阶段

- 扩展名非法时直接拒绝
- `polib` 解析失败时返回明确错误

### 任务创建阶段

- 目标语言为空时拒绝创建
- `.po` 的处理模式缺失时拒绝创建

### 执行阶段

- 单 chunk 失败即整任务失败
- 保留错误信息到 run 和 chunk

### 导出阶段

- plural 回填不完整时拒绝导出
- 原始文件丢失或无法解析时拒绝导出

## 测试策略

### 后端单元测试

- `.pot` 解析
- `.po` 解析
- `fuzzy` 筛选
- plural entry 识别
- `.pot -> .po` 导出
- `.po -> .po` 导出
- 人工修订优先级

### 后端 API 测试

- 上传 `.pot` 创建任务并导出
- 上传 `.po` 按不同模式创建任务
- 修改 entry 后导出

### 前端测试

- 新工具注册在侧边栏中可见
- 上传 `.po/.pot` 时表单行为正确
- `.po` 时显示处理模式
- `.pot` 时隐藏处理模式
- 结果页支持普通 entry 编辑

### 集成样本

建议直接使用 [dms.pot](/Users/majianhang/Code/Playground/odoo-toolbox/docs/dms.pot) 作为首个真实样本测试文件。

## 分阶段实施建议

### Phase 1

- 完成后端 `polib` 解析与导出
- 建立工具注册与最小任务执行
- 支持 `.pot -> .po`

### Phase 2

- 加入 `.po` 增量翻译模式
- 支持 `fuzzy`
- 支持人工修订

### Phase 3

- 增强 plural 编辑体验
- 增补 AI 校对或专门术语功能

## 决策总结

- 新工具独立实现，不强行复用 CSV 数据模型
- 底层解析与导出统一使用 `polib`
- 平台层继续复用现有登录、文件、运行和 Celery 基础设施
- 首版同时支持 `.po` 与 `.pot`
- `.po` 的处理策略由用户选择
- 前端工作台支持人工修订
