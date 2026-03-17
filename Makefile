.PHONY: install dev test test-unit test-integration test-e2e lint format typecheck migrate migration docker-build docker-build-dev docker-up docker-up-build docker-down docker-logs docker-migrate docker-shell docker-staging docker-size podman-build podman-build-dev podman-up podman-up-build podman-down podman-logs podman-migrate podman-shell podman-size coverage

install:
	pip install -e ".[dev]"

dev:
	uvicorn fb.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

test-e2e:
	pytest -m e2e

lint:
	ruff check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy src/

migrate:
	alembic upgrade head

migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# ── Docker ────────────────────────────────────────────────────────────
docker-build:
	docker build --target production -t facebook-clone:latest .

docker-build-dev:
	docker build --target development -t facebook-clone:dev .

docker-up:
	docker compose up -d

docker-up-build:
	docker compose up -d --build

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f app

docker-migrate:
	docker compose run --rm migrate

docker-shell:
	docker compose exec app bash

docker-staging:
	docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# ── Image size check ──────────────────────────────────────────────────
docker-size:
	docker images facebook-clone:latest --format "Image size: {{.Size}}"

# ── Podman (rootless, daemonless alternative to Docker) ───────────────
# Requires: podman, podman-compose
# Same compose file works for both runtimes — podman-compose reads docker-compose.yml

podman-build:
	podman build --target production -t facebook-clone:latest .

podman-build-dev:
	podman build --target development -t facebook-clone:dev .

podman-up:
	podman-compose up -d

podman-up-build:
	podman-compose up -d --build

podman-down:
	podman-compose down -v

podman-logs:
	podman-compose logs -f app

podman-migrate:
	podman-compose run --rm migrate

podman-shell:
	podman-compose exec app bash

# Check final production image size (should be ~50-65 MB with Distroless)
podman-size:
	podman images facebook-clone:latest --format "Image size: {{.Size}}"

coverage:
	pytest --cov=src/fb --cov-report=term-missing --cov-report=html
