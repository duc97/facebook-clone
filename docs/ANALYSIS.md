# Facebook Clone Backend — Technical Analysis

> **Scope:** Single-region monolith. Python 3.12 · FastAPI · SQLAlchemy 2.0 async ·
> PostgreSQL 16 · Redis 7 · Kubernetes (HPA 2→20) · 346 tests passing.
> Analysis date: March 2026.

---

## 1. Executive Summary

This backend is a well-engineered, production-ready foundation for a social network at
early-to-mid startup scale. The engineering team made several correct, opinionated
decisions: Clean Architecture enforced at the import level, async-first I/O throughout,
a multi-purpose Redis layer, and GitOps-ready Kubernetes manifests with blue/green
deployment and full Prometheus + Grafana + Loki + Jaeger observability. At roughly
1,000 concurrent users and 2–20 pods the system should operate comfortably with
headroom to spare.

The main architectural concerns are classic monolith-at-scale problems: a single write
PostgreSQL instance (hard SPOF), a single Redis node (dual SPOF for cache and pub/sub),
in-process WebSocket state that requires sticky sessions, and a fire-and-forget
notification pattern that silently discards work on pod restart. None of these are
show-stoppers today, but they will require deliberate action before the 100K-user
threshold.

The most structurally sound decision is Clean Architecture with frozen dataclasses in
the domain layer. This gives the codebase an unusually high test ceiling: domain logic
is fully unit-testable without any infrastructure dependency. The 346-test suite already
demonstrates this discipline. The weaknesses are concentrated in the infrastructure and
operational layers — areas that scale independently of core business logic and can be
addressed without rewriting the domain.

---

## 2. Architecture Strengths

### 2.1 Clean Architecture with Strict Layer Isolation

**What it is:** Four concentric layers — Domain → Application → Infrastructure →
Presentation — with a strict inward dependency rule: outer layers may depend on inner
layers, never the reverse. The Domain layer has zero external dependencies (no SQLAlchemy,
no Redis, no FastAPI imports).

**Why it matters:** This is the single most valuable structural decision in the codebase.
It means every use case can be unit-tested by injecting a pure in-memory mock, without
spinning up a database or cache. The 346-test suite is a direct consequence of this.
Adding a new storage backend (e.g., replacing PostgreSQL with CockroachDB) requires
changes only in `infrastructure/repositories/` — the domain and application layers are
untouched.

**Concrete example:** `CreatePostUseCase` (`application/post/create_post.py`) depends
only on `PostRepository` (a domain Protocol) and `UnitOfWork` (a domain interface).
The SQLAlchemy implementation lives in `infrastructure/repositories/post_repo.py`.
Tests can inject `FakePostRepository` without a database connection.

---

### 2.2 Async-First I/O Stack

**What it is:** The full I/O path is async: FastAPI (async route handlers) →
SQLAlchemy 2.0 with `asyncpg` driver → Redis with `redis.asyncio` → S3 with
async boto3. No blocking calls on the event loop.

**Why it matters:** Python's asyncio allows a single event-loop thread to handle
thousands of concurrent I/O-bound connections by cooperative multitasking. A
synchronous SQLAlchemy call would block the entire event loop for its duration.
With `asyncpg`, the event loop is free to accept new requests while a DB query
runs. Under 100 concurrent WebSocket connections per pod this matters significantly.

**Concrete example:** `SqlAlchemyMessageRepository.get_conversation_messages()`
uses `await self._session.execute(stmt)` throughout. The asyncpg driver sends the
query to PostgreSQL and immediately yields back to the event loop; the response is
processed when the DB replies.

---

### 2.3 Multi-Layer Cache Strategy

**What it is:** Redis is used for three distinct cache shapes:
- **String JSON** (`profile:{id}`, `post:{id}`) — simple key-value with TTL
- **Sorted Set (ZSET)** (`feed:ranked:{user_id}`) — scored feed entries, trimmed at 200
- **List** (`feed:{user_id}`) — legacy backward-compatible feed ID list

TTLs are tuned by access pattern: profiles (300s, low write rate), posts (120s, like/
comment counts change more often), friends list (600s, very stable), notification unread
count (30s, real-time feel). All cache reads use silent failure — a Redis exception
returns `None` and triggers a DB fallback.

**Why it matters:** The ZSET-based feed cache (`feed:ranked:{user_id}`) allows O(log N)
insertion of new posts via `ZADD` (fan-out on write), and O(1) retrieval of top-N posts
via `ZREVRANGE`. The 200-entry cap prevents unbounded memory growth per user. Silent
failure ensures the cache is never a hard dependency — the system degrades gracefully if
Redis is unavailable.

**Concrete example:** `RedisFeedCache.prepend_to_feed()` calls `ZADD` with the current
Unix timestamp as the score, then trims with `ZREMRANGEBYRANK` if the set exceeds
`MAX_FEED_SIZE = 200`. The entire fan-out path is non-blocking.

---

### 2.4 DevOps and Operational Maturity

**What it is:** Multi-stage Docker builds (builder/runtime separation), blue/green
Kubernetes deployment (`deployment-blue.yaml` + `deployment-green.yaml`), HPA
(minReplicas=2, maxReplicas=20, CPU 70%, memory 80%, WebSocket connections 100/pod),
PodDisruptionBudget, NetworkPolicy default-deny ingress, Prometheus metrics scraping,
Grafana dashboards, Loki log aggregation, Jaeger distributed tracing.

**Why it matters:** Most side projects stop at "it runs in Docker." This project has
production-grade operational artifacts. Blue/green with no `maxUnavailable` means zero-
downtime deploys. The custom HPA metric (`websocket_connections_active`) correctly
accounts for WebSocket load, which CPU alone does not capture. Non-root container user
(`runAsUser: 1001`) and `seccompProfile: RuntimeDefault` reduce attack surface.

**Concrete example:** The HPA manifest triggers a scale-up of 4 pods per 60-second
window (or 100% pods, whichever is larger) and has a 5-minute scale-down stabilization
window — this prevents thrashing under bursty load patterns.

---

### 2.5 Fire-and-Forget Notification Delivery

**What it is:** Notification creation (`NotificationService._create()`) saves the
notification to the database, commits the transaction, then publishes to Redis pub/sub.
The `await self._pubsub.publish(...)` call is not awaited inside a background task; if
Redis is unavailable the exception is swallowed and the DB record still exists. The
WebSocket push is therefore best-effort on top of a durable DB write.

**Why it matters:** Separating persistence from real-time delivery is architecturally
correct. The notification is never lost (it's in PostgreSQL). The WebSocket push is an
optimization for online users. This prevents a Redis failure from blocking post creation
or friend requests.

**Concrete example:** `LikePostUseCase` creates the like, commits, then calls
`notification_service.notify_like(...)` — if the notify call raises, the like is already
committed. The user will see the notification on next poll even if the WebSocket push
fails.

---

### 2.6 Domain Immutability via Frozen Dataclasses

**What it is:** All domain entities are `@dataclass(frozen=True, slots=True)`. Mutations
return new instances via `dataclasses.replace()`. For example, `Post.increment_like_count()`
returns `replace(self, like_count=self.like_count + 1)`.

**Why it matters:** Immutable entities are inherently thread-safe and concurrency-safe.
A frozen dataclass passed into a coroutine cannot be mutated by another coroutine mid-
flight. This is especially important in an asyncio context where cooperative scheduling
can interleave coroutine execution. It also makes unit tests deterministic: an entity's
state at assertion time is guaranteed to be the state at creation time plus explicit
transformations.

**Concrete example:** `Post` entity has 11 fields and 6 mutation methods, all returning
new instances. Python raises `FrozenInstanceError` at runtime if code accidentally tries
to assign `post.like_count = 5` — the compiler (via `frozen=True`) catches this class of
bug.

---

### 2.7 Dual REST + GraphQL API

**What it is:** The presentation layer exposes both a REST API (FastAPI routes under
`/api/v1/`) and a Strawberry GraphQL endpoint (`/graphql`). Both APIs share the same
application use cases and infrastructure.

**Why it matters:** REST is predictable and CDN-cacheable for mobile clients; GraphQL
allows flexible query composition and reduces over-fetching for web clients. The dual
API approach avoids building two separate backends. Strawberry (Python) provides
compile-time type safety via Python type annotations.

---

## 3. Weaknesses & Technical Debt

### 3.1 Monolith Module Coupling Risk

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Debt estimate** | 3–6 months to decompose if left unmanaged |

**What it is:** The application is a single deployable unit. All domain modules (auth,
chat, friend, post, notification, profile, media) live in the same process and are
imported together at startup. A bug in the media processing pipeline can destabilize
chat; a memory leak in notifications affects post throughput.

**Impact:** At <50K users and a team of <10 engineers, a monolith is the correct choice
— Conway's Law rewards it. Beyond that threshold, the deployment unit becomes a release
bottleneck and the blast radius of any individual change grows.

**Recommended fix:** Maintain Clean Architecture discipline now (zero cross-domain
direct calls; use domain events or shared DTOs). This makes future module extraction
mechanical rather than architectural surgery. The current design is extract-ready.

---

### 3.2 Single PostgreSQL Write Node

| Attribute | Detail |
|-----------|--------|
| **Severity** | HIGH |
| **Debt estimate** | 1–2 sprints to add read replicas; 1–3 months for multi-AZ |

**What it is:** A single PostgreSQL instance handles all reads and writes. There is no
read replica. The connection pool is `pool_size=10, max_overflow=20` per pod — with 20
pods that is 600 total connections to a single DB, which is within PostgreSQL's default
`max_connections=100` only if the DB is tuned upward or PgBouncer is used.

**Impact:** PostgreSQL is both a SPOF and a read bottleneck. Feed queries (posts by
author_id IN [...]) and profile reads are read-heavy and could be offloaded. Under 20
pods at `pool_size=10`, this generates up to 200 connections — already above PostgreSQL's
default limit of 100.

**Recommended fix:** Add PgBouncer as a connection pooler immediately (transaction-mode
pooling reduces connection count by 10×). Add a read replica (RDS Multi-AZ or Patroni)
for feed, profile, and search queries within 1 sprint.

---

### 3.3 Single Redis Node

| Attribute | Detail |
|-----------|--------|
| **Severity** | HIGH |
| **Debt estimate** | 1–2 sprints |

**What it is:** A single Redis instance serves 4 distinct workloads: cache, pub/sub
(WebSocket routing), token blacklist (auth), and rate limiting. If the Redis node goes
down, all four break simultaneously.

**Impact:** Rate limiting fails open (explicitly coded — see `rate_limiter.py:114`).
The token blacklist becomes unavailable — logged-out tokens could be replayed until
expiry. The WebSocket pub/sub listener crashes (RedisPubSub catches `CancelledError`
only; a connection drop causes `logger.exception("RedisPubSub listener crashed")`
with no automatic restart). Feed cache misses force PostgreSQL fallback at 100% of
requests.

**Recommended fix:** Redis Sentinel (3 nodes) for HA in Phase 1. Redis Cluster in
Phase 2. Separate the token blacklist onto a different Redis DB index (already supported
by redis URL query param) to isolate auth from cache downtime.

---

### 3.4 Fan-Out Write Cap at 500 Friends

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM (now) / HIGH (at scale) |
| **Debt estimate** | 2–4 weeks |

**What it is:** `feed_fan_out_max_friends: int = 500` in `config.py` caps the number of
friends whose feeds are updated when a user posts. Users with >500 friends get degraded
feed freshness.

**Impact:** This is a deliberate trade-off that solves the "celebrity problem" at small
scale by simply not solving it. At 10K users with power users having 1,000+ friends,
this silently skips feed delivery to ~50% of their friends. Those users see stale feeds
until the 60s TTL expires and a DB read rebuilds it.

**Recommended fix:** Implement a hybrid push/pull model. For users with <500 friends,
push (current behavior). For users above a threshold, or for users with >10K followers,
use pull-on-read (fan-in at read time, no cache). This is how Twitter Firehose / Facebook
News Feed handled celebrities.

---

### 3.5 WebSocket ConnectionManager Is In-Memory

| Attribute | Detail |
|-----------|--------|
| **Severity** | HIGH (for horizontal scale) |
| **Debt estimate** | 2–3 weeks |

**What it is:** `ConnectionManager._connections` is a plain Python `dict[str, set[WebSocket]]`
in process memory. Each pod has its own independent copy. Redis pub/sub bridges cross-pod
delivery (`RedisPubSub`), but the mapping of user → WebSocket object exists only in the
pod that accepted the connection.

**Impact:** A Kubernetes load balancer without sticky sessions will route WebSocket
upgrade and subsequent HTTP requests to different pods. The WebSocket connection is lost
on reconnect if the client lands on a different pod. The Redis pub/sub correctly routes
the message to the right pod, but the `send_to_user` call on the wrong pod is a no-op
(user not found in that pod's `_connections`).

**Recommended fix:** Either configure sticky sessions (`sessionAffinity: ClientIP` in
the Kubernetes Service, or NGINX `ip_hash`) or externalize WebSocket connection state
to Redis (e.g., track `user_id → pod_id` in Redis; pods only push to users connected
locally and subscribe to their own pod channel).

---

### 3.6 Fire-and-Forget with No Message Queue Durability

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Debt estimate** | 2–3 weeks (add Celery + Redis queue) |

**What it is:** `asyncio.create_task()` is used in several places for background work
(feed fan-out, notification push). If the pod restarts mid-task — during a rolling
deploy, OOM kill, or spot instance reclaim — in-flight tasks are lost.

**Impact:** Feed fan-out for new posts may be partially delivered. Some users get the
new post in their feed; others don't, until their 60s TTL expires. This is cosmetically
acceptable today but will cause inconsistency complaints at scale.

**Recommended fix:** Replace `asyncio.create_task()` with Celery tasks backed by Redis
(or RabbitMQ) for any work that must not be lost. Fan-out is a prime candidate: enqueue
one task per batch of friends, making it both durable and rate-controllable.

---

### 3.7 Offset Pagination on High-Cardinality Tables

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Debt estimate** | 1 sprint |

**What it is:** `get_conversations()` in `message_repo.py` uses `LIMIT :limit OFFSET :offset`.
The `get_feed_post_ids()` in `feed_repo.py` also uses `.offset(offset)`.

**Impact:** `OFFSET N` forces PostgreSQL to read and discard N rows. At offset 10,000 on
a messages table with 1M rows, PostgreSQL performs a sequential scan of 10,000 rows on
every page navigation. Performance degrades as O(N) with page depth.

**Note:** The `get_conversation_messages()` method already uses cursor-based pagination
(`decode_cursor` / `encode_cursor`). The conversations list view and some feed paths have
not been migrated.

**Recommended fix:** Apply the same cursor pattern (already present in the codebase) to
all paginated queries. `get_conversations()` can use `created_at DESC, id DESC` as a
stable cursor — identical to the message cursor pattern.

---

### 3.8 `media_urls` as PostgreSQL ARRAY on Posts

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW (now) / MEDIUM (at scale) |
| **Debt estimate** | 1 sprint + data migration |

**What it is:** `Post` stores media as `media_urls: tuple[str, ...]` mapped to a
PostgreSQL `ARRAY` column. URLs are strings with no FK constraint, no metadata
(MIME type, size, dimensions, upload status), and no ability to query "all posts
containing a specific media file."

**Impact:** Deduplication is impossible. If the same image is shared in 10 posts,
it's stored as 10 independent URL strings. Media deletion is unsafe — there is no
reference count. Adding metadata (e.g., thumbnail URL, duration for video) requires
either a JSON blob in the array or a schema change.

**Recommended fix:** Normalize to a `post_media` join table: `(id, post_id, media_id,
position, created_at)` referencing a `media` table `(id, url, mime_type, size_bytes,
width, height, duration_seconds, uploaded_by, created_at)`.

---

### 3.9 No Idempotency Keys on Mutating Operations

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Debt estimate** | 1–2 sprints |

**What it is:** POST/PUT/DELETE operations have no idempotency key header. A client that
retries a `POST /api/v1/posts` after a network timeout will create duplicate posts.

**Recommended fix:** Accept an `Idempotency-Key: <uuid>` header, store the key + response
in Redis with a 24h TTL, and return the cached response on replay. FastAPI middleware
can handle this transparently for all mutating routes.

---

### 3.10 No Audit Log / Event Sourcing

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Debt estimate** | 2–4 weeks |

**What it is:** There is no audit trail for sensitive operations: account deletion,
admin actions, friend removals, post deletions. The `is_published=False` soft-delete
on posts is the only historical marker.

**Recommended fix:** Append a structured audit event (who, what, when, from_state,
to_state) to a `domain_events` table on any state-changing use case. This also enables
notification replay and eventual consistency patterns.

---

## 4. Performance Bottlenecks at Scale

### 4.1 At 10,000 Concurrent Users (Current Capacity)

**Database:**
- Pool math: 20 pods × (pool_size=10 + max_overflow=20) = 600 possible connections.
  PostgreSQL's `max_connections` defaults to 100 and is typically tuned to 200–400 for
  a 4-core instance. **This is likely already misconfigured for production without PgBouncer.**
- Feed query `author_id IN (...)` with 500 friends generates an IN-clause with up to 501
  UUIDs. PostgreSQL will use `ix_posts_published_author_created` for small friend lists but
  may fall back to a bitmap index scan or sequential scan for large ones.

**Redis:**
- Single node Redis handles ~100K ops/second. At 10K users with 60/min rate limit buckets,
  peak Redis ops ≈ 10K INCR/s + feed ZSET ops. Well within limits.

**WebSocket:**
- 100 connections/pod × 20 pods = 2,000 total WebSocket connections. The HPA metric
  `websocket_connections_active: 100` triggers scale-up before saturation.

**Assessment:** Manageable with PgBouncer added. No fundamental redesign needed.

---

### 4.2 At 100,000 Concurrent Users (Near-Term Challenge)

**Database:**
- A single write primary cannot sustain 100K concurrent users with feed generation,
  post creation, and notification writes. Expect >90% CPU saturation on a db.m5.2xlarge
  with mixed OLTP workload.
- Feed `IN` queries with 501 UUIDs × 5K requests/second = 2.5M UUID comparisons/second
  against the posts table. PostgreSQL index scans become sequential under this volume.
- The `messages` table grows by ~10M rows/day at 100K users. Offset pagination on
  `get_conversations()` will degrade to multi-second queries for active users.

**Redis:**
- Feed fan-out: a post by a user with 500 friends triggers 500 `ZADD` operations.
  At 1,000 posts/second × 500 = 500K Redis ops/second — approaching single-node limits.
- Pub/sub message rate: 100K users × average 2 events/minute = 3,333 pub/sub messages/
  second. Single Redis pub/sub handles ~100K messages/second — safe for now but headroom
  is finite.

**WebSocket:**
- 100K persistent connections require 50+ pods (100 connections/pod × HPA max 20 = only
  2,000). **HPA maxReplicas=20 is insufficient at 100K users.** Requires either raising
  the cap to 1,000 connections/pod (memory tuning) or a dedicated WebSocket service.

**Media:**
- S3 GET costs for direct serving: 100K users × 50 page views/day × 5 images/page =
  25M S3 GETs/day ≈ $1,000/month in GET costs alone, plus data transfer. CDN is
  mandatory at this scale.

**Assessment:** Requires read replicas, PgBouncer, cursor pagination, Redis Sentinel,
CDN, and HPA limit increase before reaching 100K.

---

### 4.3 At 1,000,000 Concurrent Users (Medium-Term Challenge)

**Database:**
- A single PostgreSQL instance, even with 4 read replicas, cannot handle 1M users.
  The `messages` table alone grows at ~1B rows/month. PostgreSQL B-tree indexes on
  UUIDs degrade past ~500M rows without partitioning.
- The `author_id IN (...)` feed query pattern does not scale to 500 friends × 1M users
  × thousands of queries/second. This requires a dedicated feed service with precomputed
  timelines.
- Write throughput: at 1M users × 10 write ops/minute = 166K writes/second. A single
  PostgreSQL primary maxes out at ~10K-20K writes/second for complex transactions.

**Redis:**
- Feed fan-out write amplification: 1M users × average 500 friends × 1 post/hour =
  69M Redis ZADD operations/second during peak. This is 700× beyond a single Redis node.
- Pub/sub at 1M users is not feasible on a single Redis node. Redis Cluster with
  dedicated pub/sub shards is required.

**WebSocket:**
- 1M persistent connections require ~10,000 pods at 100 connections/pod, or purpose-
  built WebSocket infrastructure (e.g., Ably, Pusher, or a custom Golang/Erlang service).

**Assessment:** 1M users requires microservices decomposition, database sharding,
Kafka-based event streaming, and a purpose-built feed service. See Section 8.

---

## 5. Security Analysis

### 5.1 What's Done Well

| Control | Implementation | Notes |
|---------|---------------|-------|
| Short JWT access token | 15-minute expiry (`jwt_access_token_expire_minutes: int = 15`) | Industry best practice |
| Token blacklist on logout | Redis key `blacklist:{token}` with matching TTL | Prevents replay of revoked tokens |
| Sliding-window rate limiting | Redis INCR per 60s window, per IP/user | Correctly differentiated guest (30/min) vs user (60/min) |
| Security headers middleware | HSTS, X-Frame-Options DENY, CSP default-src 'self', X-XSS-Protection | All six headers present |
| Non-root container | `runAsUser: 1001`, `runAsNonRoot: true`, `seccompProfile: RuntimeDefault` | Follows least-privilege principle |
| NetworkPolicy default-deny | `default-deny-ingress` policy; allow-list only ingress-nginx and monitoring | Correct zero-trust posture |
| Domain isolation | Domain layer has no external dependencies | SQL injection impossible at the domain layer |
| Container scanning | Trivy in CI pipeline | Catches known CVEs in base images |

---

### 5.2 Vulnerabilities and Concerns

#### CRITICAL

**No refresh token rotation**
- **Severity:** CRITICAL
- **Detail:** `jwt_refresh_token_expire_days: int = 7`. Refresh tokens are long-lived
  and, per the codebase review, are not rotated on use. If a refresh token is stolen
  (XSS, log exposure, device compromise), the attacker has 7-day persistent access.
  The token blacklist only covers access tokens at logout — a stolen refresh token
  issued before logout is not invalidated.
- **Fix:** Rotate refresh tokens on every use (issue a new token, blacklist the old one).
  Use the Redis blacklist pattern already in place.

#### HIGH

**Rate limiter fails open on Redis unavailability**
- **Severity:** HIGH
- **Detail:** `rate_limiter.py:114`: `logger.warning("Rate limiter Redis unavailable — allowing request")`. During a Redis outage, all rate limiting is bypassed. A DDoS or
  credential stuffing attack during a Redis failure window has no defense.
- **Fix:** Implement a local in-memory fallback counter (per pod) using a bounded LRU
  cache. This degrades gracefully to per-pod limits rather than no limits.

**WebSocket token in URL**
- **Severity:** HIGH
- **Detail:** WebSocket connections pass the JWT in the query parameter
  (`?token=<jwt>`). Query parameters are logged by nginx access logs, Kubernetes
  Ingress logs, and application-level request loggers. A JWT in a log file is a
  persistent credential exposure.
- **Fix:** Accept the token as a `Sec-WebSocket-Protocol` subprotocol header, or as the
  first message after connection establishment (before any data is sent).

#### MEDIUM

**GraphQL introspection enabled in production**
- **Severity:** MEDIUM
- **Detail:** Strawberry GraphQL enables introspection by default. Introspection exposes
  the full API schema to unauthenticated callers — all type names, field names, argument
  types, and relationships. This is useful during development but constitutes an
  information disclosure vulnerability in production.
- **Fix:** Disable introspection via `GraphQL(schema, introspection=False)` in
  production. Gate it behind an admin role if dev tooling needs it.

**JWT secret default value**
- **Severity:** MEDIUM
- **Detail:** `jwt_secret_key: str = "change-me-in-production"` in `config.py`. If this
  default is used in any non-local deployment (e.g., a staging environment with a
  misconfigured `.env`), all JWTs are signed with a known public key. A Kubernetes
  `secret.yaml` should enforce the secret is present and non-default at pod startup.
- **Fix:** Add a startup assertion: `assert settings.jwt_secret_key != "change-me-in-production"`.

**Raw SQL in `message_repo.py` without parameterization audit**
- **Severity:** MEDIUM
- **Detail:** `get_conversations()` uses `text("""...""")` with named bind parameters
  (`:uid`, `:limit`, `:offset`). SQLAlchemy's `text()` with named parameters correctly
  parameterizes these values — SQL injection is not present here. However, raw SQL in
  a typed ORM codebase is a maintenance risk: future developers may copy this pattern
  and forget parameterization.
- **Fix:** Add a code review note / linting rule (`bandit B608`) to flag raw SQL
  patterns and require security review.

**No CSRF protection**
- **Severity:** MEDIUM (mitigated)
- **Detail:** Pure JWT-based APIs on non-browser clients are not vulnerable to CSRF.
  However, if the API is consumed by a browser with cookies (e.g., via GraphQL Playground
  with auth cookies), CSRF is relevant.
- **Mitigation:** JWT in Authorization header (not cookie) is the current pattern — this
  mitigates CSRF for the documented API surface.

#### LOW

**`media_urls` ARRAY not validated for SSRF**
- **Severity:** LOW
- **Detail:** `media_urls` are stored and returned as-is. If any code path fetches
  these URLs server-side (e.g., generating thumbnails from URLs rather than direct
  uploads), an attacker could supply `http://169.254.169.254/` (AWS metadata endpoint).
- **Fix:** Validate that all media URLs reference the configured S3 bucket domain only.
  Never fetch user-supplied URLs server-side.

**No MFA support**
- **Severity:** LOW
- **Detail:** Authentication is password + JWT only. For a social platform handling
  personal data, TOTP-based MFA is a reasonable expectation.

---

## 6. Comparison with Real Facebook Architecture

### 6.1 Facebook's Actual Architecture (Publicly Known)

Facebook at 2B+ DAU operates a system fundamentally different in every scaling dimension:

- **Social graph:** TAO (The Associations and Objects) — a distributed, geographically
  replicated graph store optimized for social graph traversal. Not SQL.
- **Photo storage:** Haystack (purpose-built immutable blob store) + f4 (warm storage
  for less-accessed media). S3-equivalent custom infrastructure.
- **News Feed:** EdgeRank evolved into a machine-learning ranking system. Feed generation
  is a hybrid push/pull with separate fan-out workers. Not a simple chronological ZSET.
- **Caching:** mcrouter + Memcached (not Redis). Hundreds of Memcached nodes with
  consistent hashing. Redis is used selectively, not as the primary cache.
- **Messaging:** Iris (near-real-time) → MQTT for mobile, long-polling for web.
  Dedicated messaging infrastructure, not WebSocket on the same API pod.
- **Inter-service:** Thrift RPC for service-to-service calls. Not REST internally.
- **Database:** ZippyDB (key-value), MySQL with custom sharding (Vitess), TAO, Cassandra
  (for time-series). PostgreSQL is not used at Facebook's scale.
- **Analytics:** Scuba for real-time log analytics. Hive/Spark for batch.
- **Scale:** 100B+ reads/day on TAO alone. Billions of photos uploaded/day.

---

### 6.2 Comparison Table

| Feature | This Implementation | Facebook Production | Gap |
|---------|--------------------|--------------------|-----|
| Data model (social graph) | PostgreSQL tables with FK joins | TAO distributed graph store | Fundamental — SQL can't scale the social graph beyond ~10M edges without sharding |
| Feed algorithm | Chronological ZSET, fan-out on write, 500-friend cap | ML-ranked, hybrid push/pull, no celebrity cap | ML ranking is a 6-month+ investment; hybrid push/pull is achievable at 500K users |
| Real-time messaging | WebSocket + Redis pub/sub | MQTT (mobile), long-polling (web), dedicated Iris service | Architecture is correct; durability and scale differ |
| Media storage | S3/MinIO + Pillow + ffmpeg | Haystack + f4 + CDN at edge (global PoPs) | CDN is the next step; Haystack-equivalent at 10B+ objects only |
| Caching layer | Redis (single node, 4 purposes) | mcrouter + hundreds of Memcached nodes, purpose-separated | Single node → Sentinel/Cluster is Phase 1; purpose separation is Phase 2 |
| Database | PostgreSQL (single write node) | MySQL (Vitess sharding) + TAO + ZippyDB + Cassandra | Polyglot persistence required at 100M+ users |
| Scale | 2–20 pods, ~1K concurrent | 100K+ servers, 2B+ DAU | 6 orders of magnitude |
| Deployment | Blue/green, K8s HPA | Custom canary, region-by-region rollout | Facebook deploys 2× per day to 5B users with custom infra |
| Observability | Prometheus + Grafana + Loki + Jaeger | Scuba, ODS, custom distributed tracing | Functionally equivalent for this scale; Scuba's real-time querying differs |
| Auth | JWT 15min + 7-day refresh | OAuth 2.0 + custom auth tokens + hardware keys for employees | JWT is correct for this scale; no fundamental gap |

---

### 6.3 What This Project Got Right

1. **Clean Architecture maps well to Facebook's service boundaries.** Facebook's User,
   Feed, Messaging, and Notification services exist as discrete teams. This monolith
   organized by domain (auth, post, chat, notification) makes future decomposition
   natural.

2. **Fan-out on write for feed is Facebook's original architecture.** Facebook used
   push-model fan-out with a friends cap before introducing hybrid pull for celebrities.
   This project correctly implements the v1 approach.

3. **Redis pub/sub for cross-process WebSocket is the standard pattern.** Discord,
   Slack (early), and many production systems use this exact architecture for real-time
   message routing before investing in a dedicated message broker.

4. **15-minute JWT + 7-day refresh token matches industry norms.** Facebook's access
   token expiry windows follow similar patterns, with device-bound long-lived tokens.

5. **Prometheus + Jaeger observability is production-grade.** The annotation-based
   scraping (`prometheus.io/scrape: "true"`) and distributed tracing are patterns used
   by major cloud-native deployments. Facebook's internal tooling (ODS, Scuba) solves
   the same problems with different implementations.

---

### 6.4 What Would Need to Change at Facebook Scale

1. **Replace PostgreSQL social graph with a graph database or TAO-equivalent.** SQL
   joins across friend tables at 500M users require either Vitess-style sharding or a
   dedicated graph store.

2. **Dedicated messaging infrastructure.** WebSocket on API pods cannot handle 1B+
   active Messenger sessions. A dedicated, stateful messaging service with Kafka
   persistence is required.

3. **ML-based feed ranking.** Chronological feeds have high engagement for small social
   graphs; ML ranking (EdgeRank successor) is necessary to surface relevant content for
   users with 1,000+ friends.

4. **Global CDN with edge compute.** Media latency from a single S3 region is
   unacceptable for international users. Facebook operates 100+ global PoPs.

5. **Polyglot persistence.** No single database handles all of Facebook's data shapes
   efficiently. Time-series (Cassandra), graph (TAO), blob (Haystack), search
   (ElasticSearch-equivalent), and OLAP (Hive) are all required.

---

## 7. Roadmap: Scale to 1 Million Users

### Phase 1 (Month 1–2): Quick Wins — Effort: Medium, Impact: High

| Action | Effort | Impact | Why Now |
|--------|--------|--------|---------|
| Add PgBouncer (transaction-mode) | 1 week | HIGH | Prevents connection exhaustion with 20+ pods immediately |
| PostgreSQL read replica (RDS Multi-AZ) | 1 week | HIGH | Offload feed, profile, search reads; eliminate SPOF |
| Redis Sentinel (3 nodes) | 1 week | HIGH | Eliminate Redis SPOF; automatic failover in <30s |
| CDN for S3 media (CloudFront) | 3 days | HIGH | 80% of bandwidth cost reduction; latency improvement for all users |
| Cursor pagination on `get_conversations()` | 3 days | MEDIUM | Prevent O(N) degradation on messages table at 1M rows |
| Celery + Redis task queue for fan-out | 2 weeks | MEDIUM | Durability for feed fan-out; survive pod restarts |
| HPA maxReplicas: 20 → 50 | 1 hour | MEDIUM | Current cap is insufficient at 100K WebSocket connections |
| Refresh token rotation | 1 week | CRITICAL (security) | Close the stolen-refresh-token attack vector |

---

### Phase 2 (Month 3–4): Core Scaling — Effort: High, Impact: High

| Action | Effort | Impact | Notes |
|--------|--------|--------|-------|
| Route reads to replica (SQLAlchemy async session factory) | 2 weeks | HIGH | Profile, feed, search → replica; writes → primary |
| Messages table: partition by `created_at` (monthly) | 2 weeks | HIGH | PostgreSQL declarative partitioning; transparent to ORM |
| WebSocket sticky sessions (NGINX `ip_hash`) | 1 week | HIGH | Fixes multi-pod WebSocket routing without Redis state |
| Elasticsearch for user search | 3 weeks | MEDIUM | `users` table LIKE queries do not scale; ES provides relevance ranking |
| Per-endpoint rate limiting (not just per-IP) | 1 week | MEDIUM | `/api/v1/auth/login` needs stricter limits than `/api/v1/feed` |
| Disable GraphQL introspection in production | 1 day | MEDIUM (security) | Information disclosure; see Section 5 |
| WebSocket JWT in header (not URL query param) | 3 days | HIGH (security) | Prevent token exposure in logs |

---

### Phase 3 (Month 5–6): Advanced — Effort: High, Impact: Medium/High

| Action | Effort | Impact | Notes |
|--------|--------|--------|-------|
| Hybrid push/pull feed for power users | 4 weeks | HIGH | Solve celebrity problem; uncap fan-out |
| Event sourcing for notifications | 3 weeks | MEDIUM | Audit trail + notification replay + eventual consistency |
| Redis Cluster (3 primary + 3 replica) | 2 weeks | HIGH | Horizontal memory scaling; sharded pub/sub |
| Idempotency key middleware | 2 weeks | MEDIUM | Prevent duplicate post creation on retry |
| Feature flags system (LaunchDarkly or Unleash) | 1 week | MEDIUM | Incremental rollouts without code deploys |
| Service mesh (Istio) for mTLS + traffic management | 4 weeks | MEDIUM | Prerequisite for microservices extraction |

---

## 8. Roadmap: Scale to 100 Million Users

At 100M users, the monolith architecture becomes a structural bottleneck. This scale
requires fundamental redesign across every layer.

### 8.1 Microservices Decomposition

**Extract order and rationale:**

1. **Media Service** (Month 1–2) — upload, processing, CDN. Stateless; clear domain
   boundary; high compute (Pillow, ffmpeg) should not share resources with API pods.
   Uses S3 directly. Team size: 2 engineers.

2. **Notification Service** (Month 3–4) — pub/sub → Kafka consumer, WebSocket push.
   Currently the most event-driven module. Extract along the `NotificationService`
   interface already in `application/notification/`. Team size: 2–3 engineers.

3. **Chat/Messaging Service** (Month 5–8) — dedicated WebSocket infrastructure, Kafka-
   backed message persistence. Chat is stateful (WebSocket) and high-volume (1B+ messages/
   day at scale). Requires its own database (Cassandra or DynamoDB for time-series message
   storage). Team size: 4–5 engineers.

4. **Feed Service** (Month 9–12) — precomputed timeline, hybrid push/pull, ML ranking
   pipeline. This is the most complex extraction. Requires Kafka for post events,
   dedicated Redis Cluster for feed ZSETs, and an ML feature store. Team size: 5–8
   engineers.

5. **User/Auth Service** (Month 6–8, parallel with Chat) — identity, JWT issuance,
   friend graph. The friend graph at 100M users likely needs TAO-equivalent or a graph
   database (Neo4j, Amazon Neptune). Team size: 3–4 engineers.

**Communication:** REST for synchronous calls (service A → B direct query). Kafka for
async events (post created → feed service, notification service). This enables
backpressure and replay.

---

### 8.2 Database Per Service

| Service | Primary DB | Rationale |
|---------|-----------|-----------|
| User/Auth | PostgreSQL (Citus or Vitess sharding) | Relational, ACID, shardable by user_id |
| Feed | Redis Cluster (ZSETs) + Kafka (durable log) | Write-heavy fan-out; ZSET is native |
| Chat/Messages | Apache Cassandra or DynamoDB | Time-series, append-only, billions of rows |
| Notifications | PostgreSQL + Kafka | Relational with event log |
| Media | S3 + PostgreSQL metadata | Blobs in object store; metadata in SQL |
| Search | Elasticsearch | Full-text + vector search for users/posts |

---

### 8.3 Feed Service Redesign

- **Push model** (users with <1,000 friends): fan-out on write via Kafka consumer group.
  Each post event → Celery worker → batch `ZADD` to all friend feeds.
- **Pull model** (users with >1,000 followers, "celebrities"): feed assembled at read
  time by querying top-N posts from followed users and merging. No fan-out.
- **ML ranking layer**: features (recency, interaction rate, relationship score) → online
  model inference (ONNX or TensorFlow Serving) → re-rank before serving.
- **Estimated engineering team:** 5–8 engineers, 6–9 months to full production quality.

---

### 8.4 Media CDN at Scale

- Deploy CloudFront/Cloudflare with S3 origin.
- Edge functions for WebP/AVIF transcoding on first request.
- Adaptive bitrate (HLS/DASH) for video using ffmpeg in a dedicated transcoding queue.
- Estimated CDN cost at 100M users: $15K–$40K/month (CloudFront, ~500TB/month transfer).
- Alternative: Cloudflare R2 (zero egress cost) + Cloudflare Workers for transcoding.

---

### 8.5 Engineering Team and Timeline

| Phase | Team Size | Timeline | Key Milestones |
|-------|-----------|----------|----------------|
| 1M users (Section 7) | 5–8 engineers | 6 months | Read replicas, Redis HA, CDN, cursor pagination |
| Media service extraction | 2 engineers | 2 months | Dedicated media service with CDN |
| Notification + Chat services | 6–8 engineers | 6 months | Kafka, Cassandra, WebSocket service |
| Feed service + ML | 8–12 engineers | 9–12 months | Hybrid push/pull, ML ranking |
| User sharding + graph | 4–6 engineers | 6–9 months | Vitess or Citus sharding |
| **Total to 100M users** | **~30 engineers** | **~24 months** | Full microservices, polyglot DB |

---

## 9. Cost Estimation

### 9.1 Current Architecture on AWS (~1,000 Concurrent Users)

| Resource | Instance | Monthly Cost (USD) |
|----------|----------|--------------------|
| EKS cluster — 3× m5.xlarge workers (4 vCPU, 16 GB) | On-demand | ~$450 |
| EKS control plane | Managed | ~$73 |
| RDS PostgreSQL — db.m5.large (2 vCPU, 8 GB), Multi-AZ | On-demand | ~$280 |
| ElastiCache Redis — cache.m5.large (2 vCPU, 6.38 GB) | On-demand | ~$120 |
| S3 storage — 100 GB media + 10K GET/day | Standard | ~$10 |
| CloudFront CDN — 1 TB/month transfer | | ~$85 |
| ALB (Application Load Balancer) | | ~$30 |
| Route53 hosted zone | | ~$1 |
| ECR container registry | 50 GB | ~$5 |
| CloudWatch / data transfer | | ~$25 |
| **Total estimate** | | **~$1,079/month** |

*Note: Spot instances for worker nodes reduce compute by ~60% → ~$750/month total.*

---

### 9.2 At 1 Million Users on AWS

Assumptions: 50K concurrent users, 5K req/s peak, 10 TB/month media transfer, 500 GB
media storage, 20 pods average (HPA).

| Resource | Specification | Monthly Cost (USD) |
|----------|---------------|--------------------|
| EKS — 20× m5.2xlarge workers (8 vCPU, 32 GB) | Mixed on-demand + spot | ~$4,200 |
| EKS control plane | Managed | ~$73 |
| RDS PostgreSQL — db.r5.2xlarge (8 vCPU, 64 GB) Multi-AZ + 2 read replicas | On-demand | ~$3,800 |
| PgBouncer (EC2 t3.medium × 2) | On-demand | ~$70 |
| ElastiCache Redis — 3-node cluster (cache.r6g.xlarge × 3) | On-demand | ~$900 |
| S3 — 500 GB storage + 50M GETs/month | | ~$180 |
| CloudFront — 10 TB/month transfer + 500M requests | | ~$900 |
| Celery workers — 5× m5.large | On-demand | ~$360 |
| Elasticsearch — 3× r5.large.search | On-demand | ~$600 |
| ALB + WAF + Shield Standard | | ~$150 |
| NAT Gateway | | ~$100 |
| Data transfer (inter-AZ, egress) | | ~$400 |
| CloudWatch / X-Ray / logging | | ~$200 |
| **Total estimate** | | **~$11,933/month** |

*Cost breakdown: Compute 35%, Database 32%, CDN 8%, Cache 8%, Search 5%, Other 12%.*
*1-year Reserved Instances for DB and cache reduce total by ~30% → ~$8,350/month.*

---

### 9.3 GCP Alternative at 1 Million Users

| Resource | Specification | Monthly Cost (USD) |
|----------|---------------|--------------------|
| GKE Autopilot — equivalent to 20× n2-standard-8 | Per-pod billing | ~$3,800 |
| Cloud SQL PostgreSQL — db-n1-highmem-8 + HA + 2 replicas | | ~$3,200 |
| Memorystore Redis — STANDARD_HA, 3 nodes × 6 GB | | ~$720 |
| Cloud Storage — 500 GB + 50M Class A ops | | ~$160 |
| Cloud CDN — 10 TB/month | | ~$750 |
| Cloud Armor (WAF) | | ~$200 |
| Pub/Sub + Dataflow (if migrating from Redis pub/sub) | | ~$300 |
| **Total estimate (GCP)** | | **~$9,130/month** |

*GCP is ~24% cheaper at this scale, primarily due to GKE Autopilot pricing and
committed-use discounts (CUDs) on Cloud SQL being more aggressive than AWS RIs.*

---

### 9.4 Cost Optimization Strategies

1. **Spot/Preemptible instances for Celery workers and non-critical pods:** 60–70% cost
   reduction on compute. The deployment already has `tolerations` for spot nodes
   (`node.kubernetes.io/spot`). Enabling spot for worker nodes at 1M users saves
   ~$1,500/month.

2. **S3 Intelligent-Tiering for media:** Media older than 90 days moves to Infrequent
   Access automatically. At 500 GB with 20% active, saves ~$20/month at 1M users —
   significant at 100M users ($500+/month).

3. **WebP/AVIF compression for images:** WebP saves 25–35% vs JPEG at equivalent
   quality. At 10 TB/month CDN transfer, saves ~$200/month in transfer costs.

4. **Reserved Instances / Committed Use Discounts:** 1-year RIs on RDS and ElastiCache
   save 35–40%. 3-year RIs save 55–60%. At $4,700/month on DB+cache, 1-year RI saves
   ~$1,650/month.

5. **PgBouncer transaction-mode pooling:** Reduces required DB instance size by 1 tier
   (fewer connections = lower `max_connections` requirement = smaller instance). Saves
   ~$300/month on the largest DB instance tier.

---

## 10. Final Recommendations

Priority-ordered action items for the engineering team:

| # | Priority | Action | Effort | Impact | Timeline |
|---|----------|--------|--------|--------|----------|
| 1 | CRITICAL | Implement refresh token rotation (blacklist old token on refresh) | 1 week | Security: prevents 7-day token reuse after theft | Sprint 1 |
| 2 | CRITICAL | Add PgBouncer in transaction mode between pods and PostgreSQL | 1 week | Operational: prevents connection exhaustion at 10+ pods | Sprint 1 |
| 3 | HIGH | Add PostgreSQL read replica; route feed/profile reads to replica | 2 weeks | Operational: eliminates DB SPOF; doubles read capacity | Sprint 1–2 |
| 4 | HIGH | Deploy Redis Sentinel (3 nodes); configure automatic failover | 1 week | Operational: eliminates Redis SPOF for cache, pubsub, blacklist, ratelimit | Sprint 2 |
| 5 | HIGH | Move WebSocket JWT from URL query param to first-message auth | 3 days | Security: prevents token exposure in server/proxy logs | Sprint 2 |
| 6 | HIGH | Configure sticky sessions (NGINX `ip_hash` or `sessionAffinity: ClientIP`) | 2 days | Operational: fixes WebSocket routing across pods | Sprint 2 |
| 7 | HIGH | Add CloudFront CDN in front of S3 media bucket | 3 days | Cost + Performance: 80% bandwidth cost reduction; global latency improvement | Sprint 2 |
| 8 | MEDIUM | Replace fire-and-forget `asyncio.create_task()` with Celery + Redis queue | 2 weeks | Reliability: feed fan-out survives pod restarts; auditable task execution | Sprint 3 |
| 9 | MEDIUM | Apply cursor pagination to `get_conversations()` and remaining offset queries | 3 days | Performance: prevents O(N) degradation on messages table at scale | Sprint 3 |
| 10 | MEDIUM | Disable GraphQL introspection in production; add startup assertion for JWT secret | 1 day | Security: prevents schema information disclosure; prevents default secret in prod | Sprint 3 |

---

*Analysis prepared for internal engineering review. All cost estimates are approximate and
based on AWS us-east-1 on-demand pricing as of Q1 2026. Actual costs depend on reserved
instance commitments, data transfer patterns, and workload characteristics.*
