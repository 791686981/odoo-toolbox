SHELL := /bin/bash

COMPOSE := docker compose
SERVER_DIR := apps/server
WEB_DIR := apps/web
UV_CACHE_DIR ?= /tmp/uv-cache
NPM_CACHE_DIR ?= /tmp/npm-cache
NPM_LOGS_DIR ?= /tmp/npm-logs

.DEFAULT_GOAL := help

.PHONY: help env init install install-server install-web \
	dev-api dev-web test test-server test-web build-web \
	docker-build docker-up docker-down docker-restart \
	docker-ps docker-logs docker-health docker-config clean

help: ## 显示可用命令
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_.-]+:.*## / {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "已创建 .env，请按需填写 OpenAI 配置。"; \
	else \
		echo ".env 已存在，跳过复制。"; \
	fi

init: env install ## 初始化项目：复制 .env 并安装前后端依赖

install:
	@$(MAKE) install-server
	@$(MAKE) install-web

install-server:
	@cd $(SERVER_DIR) && UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync

install-web:
	@cd $(WEB_DIR) && NPM_CONFIG_CACHE=$(NPM_CACHE_DIR) NPM_CONFIG_LOGS_DIR=$(NPM_LOGS_DIR) npm install

dev-api: ## 本地启动后端开发服务
	@cd $(SERVER_DIR) && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web: ## 本地启动前端开发服务
	@cd $(WEB_DIR) && NPM_CONFIG_CACHE=$(NPM_CACHE_DIR) NPM_CONFIG_LOGS_DIR=$(NPM_LOGS_DIR) npm run dev

test: test-server test-web ## 运行全部测试

test-server:
	@UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --project $(SERVER_DIR) --with pytest pytest -q

test-web:
	@cd $(WEB_DIR) && npm test

build-web:
	@cd $(WEB_DIR) && npm run build

docker-build: env ## 构建 Docker 镜像
	@$(COMPOSE) build api worker web

docker-up: env ## 用真实 OpenAI 配置启动全部容器
	@$(COMPOSE) up -d

docker-down: ## 停止并移除容器
	@$(COMPOSE) down

docker-restart:
	@$(MAKE) docker-down
	@$(MAKE) docker-up

docker-ps: ## 查看容器状态
	@$(COMPOSE) ps

docker-logs: ## 查看容器日志，可通过 SERVICE=api 指定服务
	@$(COMPOSE) logs -f $(SERVICE)

docker-health: ## 检查反代后的健康接口
	@curl -fsS http://127.0.0.1:8001/api/health && echo

docker-config:
	@$(COMPOSE) config

clean:
	@rm -rf $(WEB_DIR)/dist
	@rm -rf $(SERVER_DIR)/.pytest_cache
	@find $(SERVER_DIR) -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find $(SERVER_DIR) -type f -name "*.pyc" -delete
