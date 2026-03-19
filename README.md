# Odoo Toolbox

面向小团队内部使用的 Odoo 开发辅助工具箱，首版聚焦 Odoo 导出 CSV 的翻译流程。

## 当前能力

- 左侧可扩展工具导航，右侧为工具工作区
- CSV 上传后自动生成可编辑背景说明
- 按任务设置分块翻译，并通过后台任务执行
- 前端实时查看结果、逐条人工修订、完成后导出 CSV
- 通过环境变量配置 OpenAI Base URL、API Key 与翻译模型

## 目录结构

```text
apps/
  server/   FastAPI + Celery + SQLAlchemy
  web/      React + Vite + Ant Design
infra/
  docker/   Nginx 配置
storage/
  uploads/  上传文件
  outputs/  导出文件
```

## 本地开发

### 后端

```bash
cd /Users/majianhang/Code/Playground/odoo-toolbox/apps/server
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd /Users/majianhang/Code/Playground/odoo-toolbox/apps/web
npm install
npm run dev
```

## Docker 运行

1. 复制 `.env.example` 为 `.env`
2. 填写 `TOOLBOX_OPENAI_API_KEY`
3. 启动：

```bash
cd /Users/majianhang/Code/Playground/odoo-toolbox
docker compose up --build
```

默认访问地址：

- Web: [http://localhost:8001](http://localhost:8001)
- API: [http://localhost:8001/api/health](http://localhost:8001/api/health)

默认登录账号来自环境变量：

- 用户名：`TOOLBOX_ADMIN_USERNAME`
- 密码：`TOOLBOX_ADMIN_PASSWORD`

## Makefile 快捷命令

推荐直接在项目根目录使用：

```bash
cd /Users/majianhang/Code/Playground/odoo-toolbox
make help
```

常用命令：

- `make init`
  初始化 `.env` 并安装前后端依赖
- `make dev-api`
  本地启动 FastAPI 开发服务
- `make dev-web`
  本地启动 Vite 开发服务
- `make test`
  运行前后端测试
- `make docker-build`
  构建 `api / worker / web` 镜像
- `make docker-up`
  使用 `.env` 中的真实 OpenAI 配置启动容器
- `make docker-health`
  检查 `http://127.0.0.1:8001/api/health`
- `make docker-down`
  停止并清理容器
