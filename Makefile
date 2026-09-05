.PHONY: help up down logs db-up migrate backend frontend test

help:
	@echo "make up       - build and start all Compose services"
	@echo "make db-up    - start PostgreSQL only"
	@echo "make migrate  - run Alembic migrations in backend container"
	@echo "make logs     - follow backend logs"
	@echo "make down     - stop Compose services"

up:
	docker compose up -d --build

down:
	docker compose down

db-up:
	docker compose up -d postgres

migrate:
	docker compose run --rm backend alembic upgrade head

logs:
	docker compose logs -f backend

backend:
	cd backend && python3 -m uvicorn app.main:app --host "$${BACKEND_HOST:-0.0.0.0}" --port "$${BACKEND_PORT:-8000}" --reload

frontend:
	cd frontend && npm run dev -- --host "$${FRONTEND_HOST:-0.0.0.0}" --port "$${FRONTEND_PORT:-5173}"

test:
	cd backend && python3 -m pytest
