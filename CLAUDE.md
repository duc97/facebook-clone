# Facebook Clone Backend

## Stack
- Framework: FastAPI (Python 3.10+)
- API: Strawberry GraphQL (type-safe, async)
- Database: PostgreSQL + SQLAlchemy 2.0 (async) + Alembic
- Cache: Redis (token blacklist, feed cache)
- Auth: JWT (access 15min, refresh 7 days)
- Testing: pytest + httpx

## Architecture — Clean Architecture (4 Layers)

```
Presentation ──▶ Application ──▶ Domain ◀── Infrastructure
                                   ▲            │
                                   └────────────┘
                                 (implements protocols)
```

- **Domain**: Entities (frozen dataclass), Value Objects, Repository Protocols, Exceptions — ZERO external deps
- **Application**: Use Cases, DTOs (frozen dataclass), Service interfaces
- **Infrastructure**: SQLAlchemy models, Repo implementations, Redis, JWT, File Storage
- **Presentation**: Strawberry GraphQL types/mutations/queries, FastAPI routes, Middleware

## Running

```bash
# Install
pip install -e ".[dev]"

# Start services
docker compose up -d

# Run migrations
alembic upgrade head

# Start dev server
uvicorn fb.main:create_app --factory --reload
# → http://localhost:8000/graphql (Strawberry playground)
# → http://localhost:8000/health
```

## Testing

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# E2E tests only
pytest tests/e2e/ -v

# With coverage
pytest --cov=src/fb --cov-report=term-missing
```

## Conventions
- Clean Architecture — strict layer dependency rules
- Immutable entities (frozen dataclass)
- Comment in English
- Conventional commits
- Docker-ready
