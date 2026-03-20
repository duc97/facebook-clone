# Facebook Clone Backend

## Stack
- FastAPI + Strawberry GraphQL (type-safe, async)
- PostgreSQL + SQLAlchemy 2.0 (async) + Alembic
- Redis (token blacklist, feed cache)
- JWT auth (access 15min, refresh 7 days)
- pytest + httpx + testcontainers

## Architecture — Clean Architecture (4 Layers)
Presentation → Application → Domain ← Infrastructure
- Domain: frozen dataclass entities, Repository Protocols — ZERO external deps
- Application: Use Cases, DTOs (frozen dataclass)
- Infrastructure: SQLAlchemy models, Redis, JWT, S3
- Presentation: Strawberry types/mutations/queries, FastAPI routes
See: docs/architecture.md for full diagram

## Commands
- install: `pip install -e ".[dev]"`
- services: `docker compose up -d`
- migrate: `alembic upgrade head`
- dev server: `uvicorn fb.main:create_app --factory --reload`
- test all: `pytest tests/ -v`
- test unit: `pytest tests/unit/ -v`
- test e2e: `pytest tests/e2e/ -v`
- coverage: `pytest --cov=src/fb --cov-report=term-missing`
- lint: `ruff check src/ && mypy src/`

## Model Routing
- Planning / architecture / deep reasoning → switch to Opus first: `/model opus`
- Implementation / coding / refactor → Sonnet (default)
- Subagent background tasks (file search, docs reading) → Haiku (automatic)

Standard workflow:
1. `/model opus` → `/plan "feature"` → save spec to docs/
2. `/compact`
3. `/model sonnet` → implement

## Conventions
- Immutable entities (frozen dataclass) — NEVER use mutable dataclass in Domain
- Layer imports: Presentation→Application→Domain only, never skip layers
- Repository pattern: always define Protocol in Domain, implement in Infrastructure
- Comments in English
- Conventional commits: feat/fix/refactor/test/chore

## Gotchas ⚠️
- asyncpg requires asyncio event loop — never mix sync SQLAlchemy calls
- Strawberry resolvers must be async — sync resolver breaks connection pooling
- Redis token blacklist uses key pattern `blacklist:{jti}` with TTL = remaining token lifetime
- testcontainers spin up real Postgres/Redis — integration tests are slow, run separately
- Dead code in presentation/graphql/queries/*.py — excluded from coverage intentionally
- Infrastructure repos excluded from unit coverage — tested in integration tests only
- alembic autogenerate misses ARRAY types — always review migration before applying