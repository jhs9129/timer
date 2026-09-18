.PHONY: setup db-up db-down dev-api dev-web check check-api check-web test test-api test-web migrate vapid-keys

API := apps/api
WEB := apps/web
COMPOSE := docker compose -f infra/docker-compose.yml

setup:
	cd $(API) && uv sync
	cd $(WEB) && npm ci

db-up:
	$(COMPOSE) up -d --wait

db-down:
	$(COMPOSE) down

dev-api:
	cd $(API) && uv run uvicorn app.main:app --reload --port 8000

dev-web:
	cd $(WEB) && npm run dev

migrate:
	cd $(API) && uv run alembic upgrade head

vapid-keys:
	cd $(API) && uv run python scripts/gen_vapid.py

check: check-api check-web

check-api:
	cd $(API) && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -q

check-web:
	cd $(WEB) && npm run lint && npm run typecheck && npm test -- --reporter=dot

test: test-api test-web

test-api:
	cd $(API) && uv run pytest -q

test-web:
	cd $(WEB) && npm test -- --reporter=dot
