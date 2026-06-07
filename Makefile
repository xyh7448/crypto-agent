.PHONY: help install dev build up down test lint migrate

help:
	@echo "Crypto Quant Agent OS"
	@echo ""
	@echo "Commands:"
	@echo "  install    Install dependencies"
	@echo "  dev        Run development server"
	@echo "  build      Build Docker image"
	@echo "  up         Start all services with Docker"
	@echo "  down       Stop all services"
	@echo "  test       Run tests"
	@echo "  lint       Run linting"
	@echo "  migrate    Run database migrations"
	@echo "  mcp        Run MCP server (stdio)"

install:
	uv pip install -e .
	uv pip install -e ".[dev]"

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

test:
	python -m pytest tests/ -v --asyncio-mode=auto

lint:
	ruff check app/ tests/
	ruff format --check app/ tests/

migrate:
	alembic upgrade head

mcp:
	python -m app.mcp.server

shell:
	python -c "import asyncio; from app.core.database import engine; asyncio.run(engine.connect())"
