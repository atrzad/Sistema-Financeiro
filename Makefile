# Atalhos de desenvolvimento. Requer: docker, uv, pnpm.
COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: help up up-app down logs migrate api worker web test test-backend test-web lint fmt

help: ## Lista os comandos
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

up: ## Sobe Postgres, Redis e MinIO
	$(COMPOSE) --profile infra up -d --wait

up-app: ## Sobe tudo em containers (infra + API + worker)
	$(COMPOSE) --profile app up -d --build --wait

down: ## Derruba os containers
	$(COMPOSE) --profile app down

logs: ## Logs dos containers
	$(COMPOSE) --profile app logs -f

migrate: ## Aplica migrações (como app_owner)
	cd backend && uv run alembic upgrade head

api: ## API em modo dev (http://localhost:8000/docs)
	cd backend && uv run fastapi dev app/main.py

worker: ## Worker Celery consumindo todas as filas
	cd backend && uv run celery -A app.workers.celery_app worker -l info -Q celery,validation,ocr,reports,maintenance

web: ## Frontend em modo dev (http://localhost:5173)
	pnpm --filter web dev

test: test-backend test-web ## Todos os testes

test-backend:
	cd backend && uv run pytest -q

test-web:
	pnpm -r test

lint: ## Lint + tipos (backend e web)
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
	pnpm format:check && pnpm -r lint && pnpm -r typecheck

fmt: ## Formata o código
	cd backend && uv run ruff check --fix . && uv run ruff format .
	pnpm format
