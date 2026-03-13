# Architecture Overview

Facebook Clone Backend — Python 3.12 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL · Redis · Strawberry GraphQL

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Clean Architecture Layers](#2-clean-architecture-layers)
3. [Component Interaction Flow](#3-component-interaction-flow)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
5. [Tech Stack Decisions](#5-tech-stack-decisions)
6. [Request Lifecycle](#6-request-lifecycle)
7. [Dependency Injection](#7-dependency-injection)

---

## 1. System Overview

```
                        ┌───────────────────────────────────────────────────┐
                        │                 Internet / Clients                │
                        │   (Web Browser, Mobile App, API Consumers)        │
                        └────────────────────┬──────────────────────────────┘
                                             │ HTTPS / WSS
                                             ▼
                        ┌────────────────────────────────────────────────────┐
                        │          Ingress / Load Balancer                   │
                        │   (NGINX Ingress + cert-manager TLS)               │
                        │   Routes: /api/v1/** /graphql /** /api/v1/ws/**   │
                        └──────┬──────────────────────────┬──────────────────┘
                               │                          │
                    Blue Slot  │              Green Slot  │
                               ▼                          ▼
               ┌───────────────────────┐  ┌───────────────────────┐
               │   App Pod (blue)      │  │   App Pod (green)     │
               │  FastAPI + Strawberry │  │  FastAPI + Strawberry │
               │  Uvicorn ASGI         │  │  Uvicorn ASGI         │
               │  HPA: 2 → 20 pods     │  │  HPA: 2 → 20 pods     │
               └──────────┬────────────┘  └────────────┬──────────┘
                          │                            │
          ┌───────────────┼────────────────────────────┼───────────────┐
          │               │                            │               │
          ▼               ▼                            ▼               ▼
┌──────────────┐  ┌──────────────┐           ┌──────────────┐  ┌───────────────┐
│  PostgreSQL  │  │    Redis     │           │  S3 / MinIO  │  │  Observability│
│  (Primary +  │  │  Cluster     │           │  (Object     │  │  Prometheus   │
│  Replica)    │  │  Cache +     │           │   Storage)   │  │  Grafana      │
│  Port 5432   │  │  PubSub +    │           │  Port 9000   │  │  Loki         │
│              │  │  RateLimit + │           │              │  │  Jaeger       │
│  pool_size=10│  │  Blacklist   │           │  WebP/thumb  │  └───────────────┘
│  overflow=20 │  │  Port 6379   │           │  video meta  │
└──────────────┘  └──────────────┘           └───────────────┘

Kubernetes Resources:
  Deployments  : facebook-clone-blue / facebook-clone-green
  HPA          : minReplicas=2, maxReplicas=20 (CPU 70% / Memory 80%)
  PDB          : minAvailable=1 (zero-downtime rolling)
  NetworkPolicy: default-deny-all + explicit allow rules
  ConfigMap    : app config (non-secret)
  Secret       : DB_URL, REDIS_URL, JWT_SECRET, AWS_* credentials
```

---

## 2. Clean Architecture Layers

Dependency rule: outer layers depend on inner layers; inner layers know nothing about outer layers.

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    PRESENTATION LAYER                            │
  │                                                                  │
  │   FastAPI REST          Strawberry GraphQL    WebSocket          │
  │   /api/v1/*             /graphql              /api/v1/ws/*       │
  │                                                                  │
  │   Routers, Request/Response schemas (Pydantic)                   │
  │   ConnectionManager (multi-device WebSocket dict)                │
  │   Depends() wiring to Application layer DTOs                     │
  └──────────────────┬───────────────────────────────────────────────┘
                     │  calls
                     ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                    APPLICATION LAYER                             │
  │                                                                  │
  │   Use Cases (one class per action):                              │
  │     CreatePostUseCase    GetFeedUseCase      SendMessageUseCase  │
  │     RegisterUserUseCase  LoginUseCase        LikePostUseCase     │
  │     UploadMediaUseCase   AddFriendUseCase    SearchUseCase       │
  │                                                                  │
  │   DTOs (frozen dataclass, no ORM imports):                       │
  │     CreatePostDTO   FeedItemDTO   UserProfileDTO                 │
  │                                                                  │
  │   Service Interfaces (Protocol):                                 │
  │     NotificationServiceProtocol   MediaServiceProtocol          │
  │     CacheServiceProtocol          EmailServiceProtocol          │
  └──────────────────┬───────────────────────────────────────────────┘
                     │  calls (via Protocol / Repository interfaces)
                     ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                      DOMAIN LAYER                                │
  │                                                                  │
  │   Entities (frozen dataclass):                                   │
  │     User  Profile  Post  Comment  Like  Friendship  Message      │
  │     Notification  Media  Reaction  Share                         │
  │                                                                  │
  │   Value Objects (frozen dataclass):                              │
  │     Email  UserId  PostId  MediaUrl  ReactionType                │
  │                                                                  │
  │   Repository Protocols (typing.Protocol):                        │
  │     UserRepositoryProtocol  PostRepositoryProtocol               │
  │     FriendRepositoryProtocol  MessageRepositoryProtocol          │
  │                                                                  │
  │   Domain Exceptions:                                             │
  │     UserNotFound  PostNotFound  FriendRequestAlreadySent         │
  │     AlreadyFriends  PermissionDenied  MediaProcessingFailed      │
  │                                                                  │
  │   Domain Services (pure business logic, no I/O):                │
  │     FeedRankingService  PermissionChecker                        │
  └──────────────────┬───────────────────────────────────────────────┘
                     │  implemented by
                     ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                  INFRASTRUCTURE LAYER                            │
  │                                                                  │
  │   SQLAlchemy Repositories:                                       │
  │     SQLUserRepository   SQLPostRepository   SQLFriendRepository  │
  │     SQLMessageRepository  SQLNotificationRepository              │
  │                                                                  │
  │   Cache / PubSub:                                                │
  │     RedisCache (profile TTL=300s, post TTL=120s)                 │
  │     RedisPubSub (cross-process WebSocket fan-out)                │
  │     FeedCache (ZSET TTL=60s, cap 500 friends)                    │
  │     TokenBlacklist (logout / revoke)                             │
  │     RateLimiter (sliding window, guest/user/premium tiers)       │
  │                                                                  │
  │   External Services:                                             │
  │     S3MediaStorage (aioboto3)  LocalMediaStorage (fallback)      │
  │     JWTService (python-jose)   PasswordHasher (bcrypt)           │
  │     ImageProcessor (Pillow → WebP 1920×1080, thumb 320×320)     │
  │     VideoProcessor (ffmpeg → metadata + thumbnail)               │
  └──────────────────────────────────────────────────────────────────┘

Dependency arrows: Presentation → Application → Domain ← Infrastructure
                                  Application ← Infrastructure
```

Each layer communicates only through well-defined interfaces (Python `Protocol`). SQLAlchemy `Table`/`Model` objects never escape the infrastructure layer; the application layer only sees domain entities and DTOs.

---

## 3. Component Interaction Flow

### "Create Post" end-to-end request

```
Client
  │
  │  POST /api/v1/posts
  │  Authorization: Bearer <jwt>
  │  Body: { "content": "Hello!", "media_ids": ["uuid1"] }
  │
  ▼
┌────────────────────────────────────────────────────────────────┐
│ MIDDLEWARE CHAIN (FastAPI)                                     │
│  1. RequestIDMiddleware    → attach X-Request-ID header        │
│  2. SecurityHeadersMiddleware → CSP, HSTS, X-Frame-Options    │
│  3. RateLimitMiddleware    → Redis sliding window check        │
│     └─ 60 req/min (user), 30 (guest), 120 (premium)           │
│  4. JWTAuthMiddleware      → decode token, check blacklist     │
│     └─ sets request.state.user_id                             │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ PRESENTATION LAYER                                             │
│  PostRouter.create_post()                                      │
│  • Pydantic validates CreatePostRequest                        │
│  • Extracts user_id from request.state                         │
│  • Calls container.create_post_use_case()                      │
└──────────────────────────┬─────────────────────────────────────┘
                           │  CreatePostDTO(author_id, content, media_ids)
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ APPLICATION LAYER — CreatePostUseCase.execute(dto)             │
│  1. Validate author exists (UserRepo.get_by_id)                │
│  2. Validate media_ids belong to author (MediaRepo.get_many)   │
│  3. Build Post domain entity                                   │
│  4. Call PostRepository.save(post)                             │
│  5. Invalidate author's feed cache (async, fire-and-forget)    │
│  6. Trigger fan-out task (async, fire-and-forget)              │
│  7. Return PostDTO                                             │
└──────┬─────────────────────────────────┬────────────────────────┘
       │ save                            │ fan-out / cache tasks
       ▼                                 ▼
┌──────────────────┐       ┌──────────────────────────────────────┐
│ INFRASTRUCTURE   │       │ ASYNC BACKGROUND TASKS               │
│ SQLPostRepository│       │                                      │
│  • INSERT posts  │       │ FanOutTask (asyncio.create_task):    │
│  • INSERT media  │       │  • Fetch up to 500 friends           │
│    junction      │       │  • For each friend:                  │
│                  │       │    ZADD feed:{friend_id} score=ts    │
│ DB RESPONSE      │       │      post_id                         │
│  • Post row      │       │  • EXPIRE feed:{friend_id} 60s       │
│    written       │       │                                      │
└──────┬───────────┘       │ NotificationTask (asyncio.create_task│
       │                   │  • Insert notification rows for      │
       │                   │    close friends / tagged users      │
       │                   │  • PUBLISH notification:{user_id}    │
       │                   │    → RedisPubSub → WebSocket push    │
       │                   └──────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────────────┐
│ RESPONSE                                                       │
│  HTTP 201 Created                                              │
│  { "success": true, "data": { "id": "uuid", ... } }            │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow Diagrams

### 4.1 Auth Flow

```
REGISTER
  Client ──POST /auth/register──► Router
    ► RegisterUserUseCase
        ► Validate email uniqueness (UserRepo)
        ► Hash password (bcrypt)
        ► Insert user + profile rows
        ► Return UserDTO
    ◄ 201 { access_token, refresh_token }

LOGIN
  Client ──POST /auth/login──► Router
    ► LoginUseCase
        ► Fetch user by email
        ► bcrypt.verify(password, hashed)
        ► Generate access_token (15 min) + refresh_token (7 days)
        ► Store refresh_token hash in Redis (TTL=7d)
    ◄ 200 { access_token, refresh_token }

REFRESH
  Client ──POST /auth/refresh──► Router
    ► RefreshTokenUseCase
        ► Verify refresh_token signature
        ► Check not in blacklist (Redis)
        ► Rotate: blacklist old, issue new pair
    ◄ 200 { access_token, refresh_token }

LOGOUT
  Client ──POST /auth/logout──► Router
    ► LogoutUseCase
        ► Add access_token JTI to Redis blacklist (TTL = remaining token lifetime)
        ► Delete refresh_token from Redis
    ◄ 204 No Content
```

### 4.2 Feed Generation Flow (Cache-First ZSET + Fan-Out on Write)

```
GET /feed?cursor=...&limit=20
  │
  ▼
GetFeedUseCase
  │
  ├─► Redis ZREVRANGEBYSCORE feed:{user_id} ──► HIT (< 60s)
  │     └─► Return post_ids from ZSET
  │           └─► Batch-fetch posts from Redis JSON cache
  │                 ├─► HIT: return from cache (TTL=120s)
  │                 └─► MISS: fetch from PostgreSQL, store in cache
  │
  └─► Redis MISS / expired
        └─► Fallback: PostgreSQL query
              SELECT posts.* FROM posts
              JOIN friendships ON posts.author_id = friendships.friend_id
              WHERE friendships.user_id = :uid
              ORDER BY posts.created_at DESC LIMIT 20
              └─► Rebuild ZSET in Redis (ZADD + EXPIRE 60s)

Fan-Out on Write (when new post created):
  CreatePostUseCase
    └─► asyncio.create_task(fan_out)
          └─► Fetch sender's friend_ids (up to 500)
                └─► For each friend_id:
                      ZADD feed:{friend_id} <created_at_ts> <post_id>
                      ZREMRANGEBYRANK feed:{friend_id} 0 -501  (cap at 500)
                      EXPIRE feed:{friend_id} 60

Fan-Out Invalidation (post deleted or updated):
  └─► ZREM feed:{friend_id} <post_id>  for all friends
  └─► DEL post:{post_id}  (JSON cache)
```

### 4.3 Media Upload Flow

```
Client ──POST /media/upload (multipart)──►
  ├─► UploadMediaUseCase
  │     ├─► Validate file type + size
  │     ├─► Save raw bytes → temp local path
  │     ├─► INSERT media row (status=pending, original_url=temp)
  │     └─► asyncio.create_task(process_media_pipeline)
  │               │
  │               ▼  (background, fire-and-forget)
  │         MediaPipeline
  │           ├─► UPDATE media status=processing
  │           ├─► IMAGE path:
  │           │     Pillow.open() → resize 1920×1080 → save WebP
  │           │     Pillow.open() → resize 320×320  → save thumbnail
  │           │     aioboto3.upload_file() → S3 original
  │           │     aioboto3.upload_file() → S3 thumbnail
  │           ├─► VIDEO path:
  │           │     ffprobe → extract width/height/duration metadata
  │           │     ffmpeg  → extract frame 0 → thumbnail
  │           │     aioboto3.upload_file() → S3 original
  │           │     aioboto3.upload_file() → S3 thumbnail
  │           └─► UPDATE media status=ready,
  │                             original_url=s3://…,
  │                             processed_url=s3://…,
  │                             thumbnail_url=s3://…
  │
  ◄── 202 { "media_id": "uuid", "status": "pending" }

Client polls GET /media/{id} until status=ready
```

### 4.4 WebSocket Message Flow

```
Sender                    App Pod A              Redis PubSub           App Pod B              Receiver
  │                           │                       │                     │                     │
  ├─WS /api/v1/ws/messages───►│                       │                     │                     │
  │  (already authenticated)  │ Register conn in      │                     │                     │
  │                           │ ConnectionManager     │                     │                     │
  │                           │ dict[user_id, {ws}]   │                     │                     │
  │                           │                       │                     │                     │
  ├─ { type:"message",        │                       │                     │                     │
  │    to: receiver_id,       │                       │                     │                     │
  │    content: "Hi" }       ►│                       │                     │                     │
  │                           │ INSERT messages row   │                     │                     │
  │                           │ (sender, receiver,    │                     │                     │
  │                           │  content, is_seen=F)  │                     │                     │
  │                           │                       │                     │                     │
  │                           │──PUBLISH chat:{rcvr}─►│                     │                     │
  │                           │  payload: msg JSON    │                     │                     │
  │                           │                       │──broadcast to Pod B►│                     │
  │                           │                       │                     │ Lookup user in      │
  │                           │                       │                     │ ConnectionManager   │
  │                           │                       │                     │──WS send──────────►│
  │                           │                       │                     │                     │ receives message
  │◄── ACK ───────────────────│                       │                     │                     │
```

### 4.5 Notification Flow

```
Action: User A likes User B's post
  │
  ▼
LikePostUseCase
  ├─► INSERT likes row (post_id, user_id)
  ├─► UPDATE posts SET like_count = like_count + 1
  └─► asyncio.create_task(notify_task)
            │
            ▼  (fire-and-forget)
      NotificationTask
        ├─► INSERT notifications row
        │     (user_id=B, actor_id=A, type=like,
        │      entity_id=post_id, entity_type=post)
        ├─► INCR notif_unread:{user_id_B}  (TTL=30s)
        └─► PUBLISH notification:{user_id_B}
                  { type: "like", actor: "A", post_id: "..." }
                          │
                          ▼  (RedisPubSub subscriber in each pod)
                  NotificationSubscriber
                    └─► ConnectionManager.send(user_id_B, payload)
                              └─► All WebSocket connections for B
                                   (multi-device support)
```

---

## 5. Tech Stack Decisions

### FastAPI vs Django / Flask

| Concern | Decision | Rationale |
|---|---|---|
| Performance | FastAPI | ASGI-native, async from the ground up; handles 10× more concurrent connections than sync Django under I/O-heavy workloads |
| Type safety | FastAPI | First-class Pydantic integration; request/response schemas are Python types, not string annotations |
| Auto docs | FastAPI | OpenAPI + Swagger UI generated automatically from type hints |
| Maturity | Trade-off | Django has a larger ecosystem; we mitigate this by using well-maintained standalone libraries |
| Admin panel | Trade-off | No built-in admin; acceptable for an API-only backend |

### SQLAlchemy 2.0 Async vs Other ORMs

| Concern | Decision | Rationale |
|---|---|---|
| Async support | SQLAlchemy 2.0 | Native `AsyncSession` with `asyncpg` driver; first-class async without monkey-patching |
| Query control | SQLAlchemy | Full SQL expressiveness when needed; ORM for simple CRUD, Core for complex queries |
| Migration | Alembic | Same ecosystem, auto-generate migrations from model changes |
| vs Tortoise-ORM | SQLAlchemy | SQLAlchemy has wider community, better debugging tools, proven at scale |
| vs Django ORM | SQLAlchemy | Django ORM requires Django's full stack; SQLAlchemy is standalone |

### Strawberry GraphQL vs Ariadne / Graphene

| Concern | Decision | Rationale |
|---|---|---|
| Code style | Strawberry | Schema-first with Python type annotations; no separate SDL files to keep in sync |
| Async | Strawberry | Native `async` resolvers; Graphene 2 has partial async support |
| Type safety | Strawberry | Full mypy/pyright integration; resolver types match schema types |
| vs Ariadne | Strawberry | Ariadne is SDL-first which adds boilerplate; Strawberry's decorator pattern is cleaner |

### PostgreSQL vs MySQL / MongoDB

| Concern | Decision | Rationale |
|---|---|---|
| JSONB / Arrays | PostgreSQL | `media_urls ARRAY` and JSONB for flexible fields; MySQL lacks native array type |
| ACID | PostgreSQL | Full ACID for financial-grade consistency on friend requests, likes |
| vs MongoDB | PostgreSQL | Relational data (users/friends/posts) has clear schemas; MongoDB flexibility not needed |
| Full-text search | PostgreSQL | `tsvector` / `tsquery` used for basic search; Elasticsearch optional scale-out |

### Redis (multi-role)

| Role | Implementation | Why Redis |
|---|---|---|
| Cache | JSON strings with TTL | Sub-millisecond reads; eliminates hot-path DB queries |
| Feed ZSET | Sorted sets scored by timestamp | O(log N) insert/range-query; ideal for time-ordered feeds |
| Token blacklist | SET with TTL | Atomic, instant lookup; DB blacklist would require index scan |
| Rate limiting | Sliding window with EXPIRE | `INCR` + `EXPIRE` is atomic; no locks needed |
| PubSub | Redis Pub/Sub channels | Lightweight cross-process message bus; avoids a full message broker for this scale |
| **Trade-off** | Eventual persistence | Redis AOF/RDB provides durability; cache data is always reconstructable from DB |

### Alembic for Migrations

- Auto-generates migrations from SQLAlchemy model changes (`alembic revision --autogenerate`)
- Supports online (zero-downtime) and offline migration modes
- Version history tracked in `alembic_version` table
- Migration files are plain Python — complex data migrations are straightforward

### Clean Architecture vs MVC / Layered

- **MVC** couples business logic to the framework; swapping FastAPI for gRPC would require rewriting controllers and models
- **Layered** architecture still allows upper layers to depend on lower layers' concrete types
- **Clean Architecture** inverts dependencies via Protocols: the domain layer has zero imports from SQLAlchemy, Redis, or FastAPI; each layer is independently unit-testable with simple mocks

### aioboto3 for S3

- Official `boto3` is synchronous; `aioboto3` wraps it with `asyncio`-compatible context managers
- Avoids blocking the event loop during multi-MB file uploads
- Works identically against AWS S3 and MinIO (local dev / staging)

### Pillow + ffmpeg for Media

| Tool | Purpose | Rationale |
|---|---|---|
| Pillow | Image resize, WebP conversion | Pure Python, well-maintained, handles EXIF, ICC profiles |
| ffmpeg | Video thumbnail, metadata | Industry standard; supports every codec; metadata via `ffprobe` JSON output |
| **Trade-off** | ffmpeg is a system binary | Handled in Docker image (`RUN apt-get install ffmpeg`); version pinned in base image |

---

## 6. Request Lifecycle

Every HTTP request to `/api/v1/**` passes through the following steps in order:

```
 1. TCP connection accepted by Uvicorn ASGI server
 2. RequestIDMiddleware
      • Reads X-Request-ID header or generates UUID4
      • Injects into request.state.request_id
      • Adds header to response for tracing
 3. SecurityHeadersMiddleware
      • Sets: Strict-Transport-Security, X-Content-Type-Options,
              X-Frame-Options: DENY, Content-Security-Policy
 4. CORSMiddleware
      • Validates Origin against allowed origins list
      • Handles preflight OPTIONS requests
 5. RateLimitMiddleware
      • Identifies client: authenticated user_id or IP (guest)
      • Redis INCR sliding-window key (60s window)
      • Tiers: guest=30/min, user=60/min, premium=120/min
      • Returns 429 + Retry-After header if exceeded
 6. JWTAuthMiddleware (optional — public endpoints skip)
      • Decode Bearer token (python-jose, HS256 / RS256)
      • Check JTI against Redis blacklist
      • Set request.state.user_id, request.state.user_role
      • Return 401 if missing/invalid/blacklisted
 7. FastAPI Router dispatch
      • Path + method matching
      • Pydantic request body validation (422 on schema errors)
      • Dependency injection via Depends()
 8. Use Case execution (Application layer)
      • Business rule enforcement
      • Domain entity construction
      • Repository calls (async, awaited)
 9. Repository / Infrastructure (async)
      • SQLAlchemy AsyncSession query
      • Cache check (Redis GET/ZRANGE)
      • External service calls (S3, etc.)
10. Domain validation
      • Domain exceptions raised here propagate up as HTTP errors
      • DomainException → mapped to 4xx in exception handlers
11. Response serialization
      • Domain entity / DTO → Pydantic response model → JSON
12. PostResponseMiddleware
      • Attach request_id to response headers
      • Emit structured log line (request_id, method, path, status, duration_ms)
      • Emit Prometheus histogram metric (http_request_duration_seconds)
13. Uvicorn sends HTTP response to client

WebSocket requests (/api/v1/ws/**)
  • Steps 1–6 identical (JWT validated on WS handshake)
  • Step 7: ConnectionManager.connect(user_id, websocket)
  • Async receive loop: decode JSON → dispatch to handler
  • On disconnect: ConnectionManager.disconnect(user_id, websocket)
```

---

## 7. Dependency Injection

### The Container Pattern

A single `Container` object is instantiated once at application startup (`app/container.py`) and stored on `app.state.container`. FastAPI's `Depends()` pulls specific use cases from the container.

```
startup sequence:
  lifespan() context manager
    │
    ├─► create AsyncEngine (SQLAlchemy)
    │     pool_size=10, max_overflow=20,
    │     pool_recycle=3600, pool_timeout=30,
    │     connect_args={"server_settings": {"jit": "off"}}
    │
    ├─► create async_session_factory (sessionmaker)
    │
    ├─► create Redis client (aioredis)
    │
    ├─► create S3 client (aioboto3 session)
    │
    └─► build Container(engine, redis, s3)

Container contents:
  Infrastructure:
    user_repo         = SQLUserRepository(session_factory)
    post_repo         = SQLPostRepository(session_factory)
    friend_repo       = SQLFriendRepository(session_factory)
    message_repo      = SQLMessageRepository(session_factory)
    notification_repo = SQLNotificationRepository(session_factory)
    media_repo        = SQLMediaRepository(session_factory)
    cache             = RedisCache(redis_client)
    feed_cache        = FeedCache(redis_client)
    pubsub            = RedisPubSub(redis_client)
    rate_limiter      = RateLimiter(redis_client)
    token_blacklist   = TokenBlacklist(redis_client)
    jwt_service       = JWTService(secret_key, algorithm)
    password_hasher   = BcryptPasswordHasher()
    media_storage     = S3MediaStorage(s3_client, bucket)
    image_processor   = PillowImageProcessor()
    video_processor   = FfmpegVideoProcessor()
    ws_manager        = ConnectionManager()

  Application Use Cases (constructed from infra deps):
    register_use_case       = RegisterUserUseCase(user_repo, password_hasher, jwt_service)
    login_use_case          = LoginUseCase(user_repo, password_hasher, jwt_service, token_blacklist)
    create_post_use_case    = CreatePostUseCase(post_repo, media_repo, cache, feed_cache, pubsub)
    get_feed_use_case       = GetFeedUseCase(post_repo, friend_repo, feed_cache, cache)
    send_message_use_case   = SendMessageUseCase(message_repo, ws_manager, pubsub)
    upload_media_use_case   = UploadMediaUseCase(media_repo, media_storage, image_processor, video_processor)
    … (one use case class per user action)
```

### FastAPI Wiring

```python
# In router files — thin, no business logic
async def get_container(request: Request) -> Container:
    return request.app.state.container

@router.post("/posts", response_model=PostResponse, status_code=201)
async def create_post(
    body: CreatePostRequest,
    current_user: CurrentUser = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    dto = CreatePostDTO(author_id=current_user.id, content=body.content)
    post = await container.create_post_use_case.execute(dto)
    return PostResponse.from_domain(post)
```

### Testing

Because every use case receives its dependencies via constructor injection, tests replace infrastructure with in-memory fakes:

```python
def make_create_post_use_case():
    return CreatePostUseCase(
        post_repo=InMemoryPostRepository(),
        media_repo=InMemoryMediaRepository(),
        cache=NullCache(),
        feed_cache=NullFeedCache(),
        pubsub=NullPubSub(),
    )
```

No database or Redis connection required to unit-test business logic.

---

*Last updated: 2026-03-13*
