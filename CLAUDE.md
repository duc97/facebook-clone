# Facebook Clone Backend

## Stack
- FastAPI + Strawberry GraphQL (type-safe, async)
- PostgreSQL + SQLAlchemy 2.0 (async) + Alembic (7 migrations)
- Redis (token blacklist, feed cache)
- JWT auth (access 15min, refresh 7 days), login via username
- Social: Follow model (unidirectional), NOT friend-request model
- pytest + httpx + testcontainers

## Architecture — Clean Architecture (4 Layers)
Presentation → Application → Domain ← Infrastructure
- Domain: frozen dataclass entities, Repository Protocols — ZERO external deps
  - Subdomains: auth, chat, follow, friend (legacy), media, notification, post, profile
- Application: Use Cases, DTOs (frozen dataclass)
- Infrastructure: SQLAlchemy models, Redis, JWT, S3
- Presentation: Strawberry types/mutations/queries, FastAPI routes
See: docs/architecture.md for full diagram

## REST API Endpoints (Target Spec)

| Action | Method | Path | Request | Response |
|--------|--------|------|---------|----------|
| Sign up | POST | `/api/v1/users` | `{user_name, email, first_name, last_name, birthday, password}` | `{msg}` |
| Login | POST | `/api/v1/sessions` | `{user_name, password}` | `{access_token, refresh_token}` |
| Edit profile | PUT | `/api/v1/users` | `{first_name, last_name, birthday, password}` | `{msg}` |
| See follow list | GET | `/api/v1/friends/{user_id}` | — | `{users}` |
| Follow | POST | `/api/v1/friends/{user_id}` | — | `{msg}` |
| Unfollow | DELETE | `/api/v1/friends/{user_id}` | — | `{msg}` |
| See user posts | GET | `/api/v1/friends/{user_id}/posts` | — | `{posts}` |
| See post | GET | `/api/v1/posts/{post_id}` | — | `{text, image, comments, likes}` |
| Create post | POST | `/api/v1/posts` | `{text, image}` | `{msg}` |
| Edit post | PUT | `/api/v1/posts/{post_id}` | `{text, image}` | `{msg}` |
| Delete post | DELETE | `/api/v1/posts/{post_id}` | — | `{msg}` |
| Comment post | POST | `/api/v1/posts/{post_id}/comments` | `{text}` | `{msg}` |
| Like post | POST | `/api/v1/posts/{post_id}/likes` | — | `{msg}` |
| Newsfeed | GET | `/api/v1/newsfeeds` | — | `{posts}` |

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
- Post fields: `text` (content), `image` (single URL) — NOT `content`/`media_urls`
- Comment field: `text` — NOT `content`
- Auth: login via `user_name`, NOT email
- User entity: `user_name`, `first_name`, `last_name`, `date_of_birth`, `display_name` (auto-computed)
- Social model: Follow (unidirectional) via `follows` table, NOT friend-request system

## Gotchas ⚠️
- asyncpg requires asyncio event loop — never mix sync SQLAlchemy calls
- Strawberry resolvers must be async — sync resolver breaks connection pooling
- Redis token blacklist uses key pattern `blacklist:{jti}` with TTL = remaining token lifetime
- testcontainers spin up real Postgres/Redis — integration tests are slow, run separately
- Dead code in presentation/graphql/queries/*.py — excluded from coverage intentionally
- Infrastructure repos excluded from unit coverage — tested in integration tests only
- alembic autogenerate misses ARRAY types — always review migration before applying
