# Performance & High Availability Plan

Single source of truth for the Facebook Clone backend performance audit.

## Phase 1: Quick Wins (1-3 days) — IMPLEMENTED

### B1 CRITICAL: Redis KEYS blocking in feed_cache.py

- **File**: `src/fb/infrastructure/cache/feed_cache.py` — `remove_post_from_feeds()`
- **Problem**: `KEYS "feed:ranked:*"` is O(n) and blocks the entire Redis instance
- **Fix**: Replaced with `SCAN` (non-blocking, cursor-based iteration)
- **Impact**: Prevents Redis stalls under load; SCAN yields incrementally

### B2 HIGH: Redis KEYS blocking in redis_cache.py

- **File**: `src/fb/infrastructure/cache/redis_cache.py` — `delete_pattern()`
- **Problem**: `KEYS` with glob pattern blocks Redis
- **Fix**: Replaced with `SCAN` + batched `DELETE`
- **Impact**: Same as B1 — prevents Redis blocking on cache invalidation

### A1 HIGH: 3 sequential queries in get_reactions

- **File**: `src/fb/presentation/rest/v1/posts.py` — `get_reactions()`
- **Problem**: `find_by_post` + `count_by_post` + `count_by_type` = 3 DB round-trips
- **Fix**: Derive total count from `sum(count_by_type.values())`, eliminating `count_by_post`
- **Impact**: 3 queries → 2 queries per reaction list request

### A2 HIGH: 2 sequential queries in friends endpoints

- **Files**: `src/fb/presentation/rest/v1/users.py`, `src/fb/presentation/graphql/schema.py`
- **Problem**: `get_friends()` + `get_friend_count()` = 2 DB round-trips
- **Fix**: Added `get_friends_with_count()` using window function `COUNT(*) OVER()`
- **Impact**: 2 queries → 1 query per friends list request

### A3 HIGH: Redundant COUNT(*) on every feed page

- **File**: `src/fb/application/post/get_feed.py` — `execute()` and `execute_ranked()`
- **Problem**: `get_feed_total_count()` runs expensive COUNT with IN-clause over all friend IDs on every request
- **Fix**: Estimate `has_next_page` from candidate pool size; removed COUNT query
- **Impact**: Eliminates an expensive sequential scan on every feed load

### F1 HIGH: Sequential fan-out writes (500 RTTs)

- **File**: `src/fb/infrastructure/cache/feed_warmer.py` — `fan_out_new_post()`
- **Problem**: Loop of up to 500 sequential `prepend_to_feed()` calls, each a separate Redis RTT
- **Fix**: Added `batch_prepend_to_feeds()` — single Redis pipeline for all ZADD+trim ops
- **Impact**: 500 RTTs → 1 pipelined round-trip (~100x faster fan-out)

### F2 MEDIUM: 3 RTTs per prepend_to_feed

- **File**: `src/fb/infrastructure/cache/feed_cache.py` — `prepend_to_feed()`
- **Problem**: ZADD + ZCARD + conditional ZREMRANGEBYRANK = 3 separate Redis calls
- **Fix**: Pipeline ZADD + unconditional ZREMRANGEBYRANK (safe no-op when under limit)
- **Impact**: 3 RTTs → 1 pipeline per individual prepend

### C1 HIGH: Hardcoded LocalFileStorage in avatar upload

- **File**: `src/fb/presentation/rest/v1/users.py` — `upload_user_avatar()`
- **Problem**: `LocalFileStorage(container.settings.upload_dir)` ignores container's `file_storage` (S3 in staging/prod)
- **Fix**: Changed to `container.file_storage` (respects STORAGE_BACKEND config)
- **Impact**: Avatars now upload to S3 in staging/production

---

## Phase 2: Caching & Query Optimization (1 week) — IMPLEMENTED

### 2.1 DataLoader for Strawberry GraphQL
- **Files**: `src/fb/presentation/graphql/loaders.py` (new), `context.py`, `schema.py`
- **Problem**: Each `post(id: X)` call in a GraphQL document executed a separate DB SELECT
- **Fix**: `GraphQLLoaders` dataclass with `DataLoader[str, Post|None]` and `DataLoader[str, Profile|None]`; request-scoped (one instance per request in `GraphQLContext`); batch methods `find_by_ids` and `find_by_user_ids` added to repos
- **Impact**: N individual SELECTs → 1 IN-clause query per GraphQL request tick

### 2.2 Alembic migration 007: pg_trgm GIN indexes for user search
- **File**: `migrations/versions/007_add_trgm_search_indexes.py`
- **Problem**: `user_search_repo.py` uses `ILIKE '%query%'` — leading wildcard forces full table scan
- **Fix**: `CREATE EXTENSION IF NOT EXISTS pg_trgm` + GIN trigram indexes on `users.display_name` and `users.email` using `CONCURRENTLY IF NOT EXISTS`
- **Impact**: Full table scan → GIN index scan for all substring search queries; backward-compatible

### 2.2 Pool event listeners (Prometheus)
- **File**: `src/fb/infrastructure/database/session.py`, `src/fb/infrastructure/metrics/prometheus.py`
- **Added**: `db_pool_checkout_wait_seconds` histogram + `db_pool_connections{state}` gauge
- **Wiring**: `_register_pool_listeners(engine)` attaches SQLAlchemy `checkout`/`checkin`/`connect` events; deferred import so unit tests without prometheus_client still work

### 2.3 Redis MGET batch + friend_count cache key
- **Files**: `src/fb/infrastructure/cache/redis_cache.py`, `keys.py`, `cache_service.py`
- **Added**: `RedisCache.mget(keys)` — single MGET round-trip for multiple keys
- **Added**: `CacheService.mget_posts(post_ids)` — batch cache read for feed assembly
- **Added**: `friend_count_key` + `TTL_FRIEND_COUNT=120s` + `get/set/invalidate_friend_count` on `CacheService`

### 2.3 GraphQL cache-aside for profile resolvers
- **File**: `src/fb/presentation/graphql/schema.py`
- **Problem**: `profile` and `my_profile` queries always hit the DB
- **Fix**: Cache-aside pattern using `container.cache.get_profile` / `set_profile`; helpers `_profile_output_to_dict` / `_profile_dict_to_type` for serialization
- **Impact**: Repeated profile reads served from Redis (TTL=300s) instead of DB

### 2.3 GraphQL mutation cache invalidation
- **Files**: `mutations/post.py`, `mutations/interaction.py`, `mutations/profile.py`
- **Fixed**: `update_post`, `delete_post` → `cache.invalidate_post(post_id)`
- **Fixed**: `create_comment`, `like_post`, `unlike_post` → `cache.invalidate_post(post_id)` (counters changed)
- **Fixed**: `update_profile`, `upload_avatar` → `cache.invalidate_profile(user_id)`

### 2.4 Connection pool tuning
- **File**: `src/fb/config.py`
- **Changes**: `db_pool_recycle` lowered from 3600→1800s (safer for K8s pod lifetimes); detailed comments on each setting with tuning guidance; added `cache_ttl_friend_count=120s` env-overridable setting
- **Current defaults**: pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=1800

---

## Phase 3: Kubernetes HA (2 weeks) — IMPLEMENTED

### 3.1 Namespace (`deploy/k8s/namespace.yaml`)
- Dedicated `facebook-clone` namespace with `app.kubernetes.io/` label conventions

### 3.2 ConfigMap (`deploy/k8s/configmap.yaml`)
- All non-secret env vars from `src/fb/config.py` (pool settings, cache TTLs, rate limits, image/video limits, CORS)
- Safe to commit; no credentials

### 3.3 Secret template (`deploy/k8s/secret.yaml`)
- Placeholders for `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`
- Comment directs operators to sealed-secrets or external-secrets-operator

### 3.4 Deployment (`deploy/k8s/deployment.yaml`)
- `replicas: 3`; rolling update `maxUnavailable: 1, maxSurge: 1`
- Resource requests: CPU 250m / memory 256Mi; limits: CPU 1000m / memory 512Mi
- Liveness probe: `GET /health` every 30s, `initialDelaySeconds: 30`
- Readiness probe: `GET /health/ready` every 10s, `initialDelaySeconds: 10`
- `terminationGracePeriodSeconds: 60` + `preStop: sleep 5` for load-balancer drain
- `podAntiAffinity` (preferred) to spread pods across nodes
- Prometheus scrape annotations on both Deployment and pod template

### 3.5 Service (`deploy/k8s/service.yaml`)
- ClusterIP, port 80 → targetPort 8000

### 3.6 HPA (`deploy/k8s/hpa.yaml`)
- `minReplicas: 3`, `maxReplicas: 10`
- CPU target 70%, memory target 80%
- WebSocket custom metric (`websocket_connections`, target 100/pod) present but commented out — requires prometheus-adapter
- Scale-down stabilization: 300s to prevent flapping

### 3.7 PodDisruptionBudget (`deploy/k8s/pdb.yaml`)
- `minAvailable: 2` — ensures at least 2 pods stay up during node maintenance or cluster upgrades

### 3.8 Ingress (`deploy/k8s/ingress.yaml`)
- nginx ingress class; TLS placeholder via cert-manager `letsencrypt-prod` ClusterIssuer
- Paths: `/api/` and `/graphql/` routed to the ClusterIP service
- nginx annotations: SSL redirect, 50 MB body limit, CORS, rate limiting, WebSocket upgrade

### 3.9 Kustomization (`deploy/k8s/kustomization.yaml`)
- Lists all 8 manifests above as resources for `kubectl apply -k deploy/k8s/`

---

## Phase 4: Observability & Chaos Hardening (ongoing) — IMPLEMENTED

### 4.1 Prometheus Metric Cardinality Review
- **File**: `src/fb/infrastructure/metrics/prometheus.py`
- **Added**: `METRICS_CARDINALITY_NOTES` comment block at the top of the file documenting every metric label set with a SAFE/FORBIDDEN audit.
- **Findings**: All existing labels are bounded. `http_requests_total[endpoint]` is normalised by `_normalize_path()` (UUIDs → `{id}`, numeric IDs → `{id}`). `cache_hits_total / cache_misses_total[cache_type]` uses a bounded enum (`feed`, `profile`, `post`, `friend_count`). `db_pool_connections[state]` uses 3 fixed values. No user/post/comment IDs are used as label values anywhere.
- **No metric changes required** — cardinality is already safe. Notes added as documentation and enforcement guide for future contributors.

### 4.2 Grafana Dashboard
- **File**: `deploy/grafana/facebook-clone-dashboard.json`
- **Panels** (Grafana 9+ schema, uid `facebook-clone-phase4`):
  1. **TODO: Redis Pipeline Latency** — placeholder text panel; `redis_pipeline_latency_seconds_bucket` not yet instrumented. Add to `feed_warmer.py`.
  2. **TODO: Feed Fan-out Timing** — placeholder text panel; `feed_fanout_duration_seconds` not yet instrumented. Add to `fan_out_new_post()`.
  3. **Feed Cache Miss Rate** — derived from `rate(cache_misses_total{cache_type="feed"}[5m])` / `(hits + misses)`. Thresholds: yellow >30%, red >50%.
  4. **DB Pool Checkout Wait (P50/P95/P99)** — `histogram_quantile` over `db_pool_checkout_wait_seconds_bucket`. Alert threshold at 100ms.
  5. **DB Pool Connections by State** — `db_pool_connections{state}` gauge with colour-coded series (checked_out=blue, idle=green, overflow=red).
  6. **HTTP Request Rate (RPS)** — `rate(http_requests_total[1m])` by normalised endpoint.
  7. **Active WebSocket Connections** — `websocket_connections_active` stat panel.
  8. **HTTP Error Rate / Feed Cache Hit Ratio / DB Query P99** — additional stat/gauge panels.

### 4.3 Alert Rules
- **File**: `deploy/prometheus/alerts.yaml`
- **Group**: `facebook-clone.phase4`
- **Rules**:
  - `FeedCacheMissRateHigh` — cache miss rate > 50% for 5m (severity: warning)
  - `DBPoolExhausted` — checkout wait P99 > 100ms for 5m (severity: critical)
  - `RedisDown` — misses spike (>100 in 2m) with zero hits (severity: critical)
  - `HighMemoryUsage` — container memory > 90% of limit for 5m (severity: warning)
  - `PodRestarting` — pod restart count > 0 in 10m (severity: warning, fires immediately)

### 4.4 Graceful Shutdown
- **File**: `src/fb/main.py`
- **Extended** the existing `lifespan` async context manager (did not replace it):
  1. **SIGTERM handler**: `loop.add_signal_handler(signal.SIGTERM, ...)` sets a shutdown event so Kubernetes TERM signals trigger orderly teardown.
  2. **WebSocket drain** (`_drain_websocket_connections`): sends close code 1001 to all active connections, waits up to 30 s for them to close, cancels stragglers.
  3. **Redis pipeline flush** (`_flush_redis_pipeline`): issues a PING to confirm Redis is reachable and any buffered pipeline commands have been processed.
  4. **Existing shutdown** preserved: `pubsub.stop()` → WebSocket drain → Redis flush → `redis.aclose()` → SIGTERM handler removed.

### Remaining (future)
- Chaos testing: Redis failover, DB connection storms, pod eviction (not yet scheduled)
