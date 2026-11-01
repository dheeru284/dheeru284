# Bharat Narrative Intelligence Platform: developer commands.
# Prerequisites: uv, Node 20+, and Postgres (pgvector) + Redis (docker compose up -d).

BACKEND := backend
FRONTEND := frontend

.PHONY: help infra-up infra-down ollama-up ollama-pull backend-install migrate \
        dev-api dev-worker frontend-install dev-web lint-backend test-backend \
        test-frontend build-frontend test check

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

infra-up: ## Start Postgres+pgvector and Redis (docker compose)
	docker compose up -d postgres redis

infra-down: ## Stop local infrastructure
	docker compose down

ollama-up: ## Start Ollama in docker
	docker compose --profile ollama up -d ollama

ollama-pull: ## Pull the default chat and embedding models into Ollama
	ollama pull llama3.1:8b && ollama pull nomic-embed-text

backend-install: ## Install backend dependencies (uv)
	cd $(BACKEND) && uv sync

migrate: ## Apply database migrations
	cd $(BACKEND) && uv run alembic upgrade head

dev-api: ## Run the FastAPI server on :8000 (reload)
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --port 8000

dev-worker: ## Run a Celery worker
	cd $(BACKEND) && uv run celery -A app.workers.celery_app worker --loglevel=INFO

frontend-install: ## Install frontend dependencies
	cd $(FRONTEND) && npm ci

dev-web: ## Run the Next.js dev server on :3000
	cd $(FRONTEND) && npm run dev

lint-backend: ## Ruff lint + format check
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .

test-backend: lint-backend ## Lint and run backend tests (needs Postgres + Redis)
	cd $(BACKEND) && uv run pytest

test-frontend: ## Lint, typecheck and unit-test the frontend
	cd $(FRONTEND) && npm run lint && npm run typecheck && npm test

build-frontend: ## Production build of the frontend
	cd $(FRONTEND) && npm run build

test: test-backend test-frontend ## All tests

check: test build-frontend ## Everything CI runs
