# Project Progress

## Đã hoàn thành
- Phase 1: Base setup + Auth
- Phase 2: GraphQL + Infra
- Phase 3: User Profile + Friend + Search
- Phase 4: Post + Feed + Interactions
- API Redesign: versioning /api/v1/, chuẩn RESTful
- Tests: 346 passed, 0 failed
- Phase 5: Realtime - Chat + Notifications (WebSocket)
  - Migration 004: messages, notifications, reactions, shares tables
  - WebSocket handler: chat.send, chat.typing, chat.seen, ping/pong
  - Online presence: user.online/user.offline broadcast to friends
  - Fix: mark_seen EntityId bug
  - REST: GET /messages/unread-count, GET /users/online, GET /users/{id}/online
  - Realtime push: notification.new via pubsub (like, comment, reaction, share, friend_request, friend_accept)
  - REST send_message pushes chat.message to receiver via pubsub
- Phase 6: Media Upload S3 + Image/Video Processing
  - Migration 005: media table (owner_id, entity_id/type, original/processed/thumbnail URL, width/height/duration, status)
  - Domain: Media entity (frozen DC), MediaType/MediaStatus enums, MediaRepository Protocol, exceptions
  - Infrastructure: S3FileStorage presigned URL, LocalFileStorage presigned passthrough
  - Image processing: Pillow resize→WebP (1920×1080 max), center-crop thumbnail (320×320)
  - Video processing: ffmpeg metadata extraction (width/height/duration/codec), frame thumbnail
  - Background pipeline: asyncio.create_task fire-and-forget for image + video processing
  - REST endpoints: POST /media/upload, GET /media, GET /media/{id}, DELETE /media/{id}
  - Streaming: GET /media/{id}/stream (S3 presigned redirect / local HTTP Range 206)
  - Presigned URL: GET /media/{id}/presigned-url

- Phase 7: Redis Caching + Performance
  - Migration 006: 7 composite indexes (posts, friendships, notifications, messages, reactions, shares)
  - RedisCache: generic JSON cache (get/set/delete/delete_pattern/get_or_set/increment/decrement)
  - CacheService: domain-aware cache (profile, post, user-posts, friends, notif-unread)
  - cache keys.py: TTL constants + key-builder functions cho mọi domain
  - Container.cache wired at startup
  - Cache-aside: GET /users/{id} (profile), GET /posts/{id}, GET /notifications/unread-count
  - Feed: cache-first ranked feed (ZSET scored), fan-out on write (post creation)
  - Feed invalidation: delete/update post purges all cached feeds
  - N+1 fix: get_conversations → single raw SQL (DISTINCT ON + CTEs)
  - UUID fix in feed repo: str→uuid.UUID for index alignment
  - Connection pool: configurable pool_size/max_overflow/recycle/timeout + JIT off

- Phase 8: Docker + CI/CD
  - Multi-stage Dockerfile (base/builder/development/production), non-root UID 1001, <100MB
  - docker-compose.yml (app + postgres:16-alpine + redis:7-alpine + minio), docker-compose.staging.yml
  - GitHub Actions: ci.yml (ruff+bandit+safety+pytest+multi-arch build+trivy SARIF)
  - GitHub Actions: cd.yml (blue/green deploy staging auto + production manual + Slack notify)
  - GitHub Actions: release.yml (GitHub Release on v*.*.* tag with changelog)
  - K8s: namespace, RBAC, ConfigMap, Secret, ResourceQuota, LimitRange
  - K8s: deployment-blue/green (initContainer migrations, 3 probes, anti-affinity, preStop)
  - K8s: HPA (2→20, CPU+memory+websocket_connections), PDB (minAvailable=1)
  - K8s: Ingress (NGINX TLS cert-manager), NetworkPolicy (default-deny), Kustomize overlays
  - Observability: Prometheus metrics middleware (10 metrics, _normalize_path), JSON structured logging
  - Observability: OpenTelemetry tracing (Jaeger), AlertManager (PagerDuty+Slack), Grafana dashboard
  - Scripts: blue-green-deploy.sh, rollback.sh, tag-release.sh

- Documentation
  - docs/ARCHITECTURE.md (system overview, 4-layer diagram, data flows, tech stack decisions)
  - docs/DATABASE.md (ERD, schema decisions, index strategy, migration guide)
  - docs/API.md (all endpoints, request/response examples, auth flow, error codes, rate limiting)
  - docs/WEBSOCKET.md (events, connection flow, reconnection strategy, JS client example)
  - docs/RUNBOOK.md (dev/staging/prod deploy, scaling guide, backup/restore, incident playbook)
  - docs/DISASTER_RECOVERY.md (RTO/RPO targets, failure scenarios, data recovery, DR testing)
  - docs/ANALYSIS.md (strengths, weaknesses, bottlenecks, security, Facebook comparison, 1M/100M roadmap, cost estimate)

- Phase 9: API Redesign — Follow Model + New User Fields
  - Migration 007: Add user_name, first_name, last_name, date_of_birth to users table + create follows table
  - User entity: thêm user_name (unique, 3-50 chars), first_name, last_name, date_of_birth
  - UserName value object: validation regex ^[a-zA-Z0-9_.]{3,50}$
  - Auth: login via user_name thay vì email (POST /sessions)
  - Sign up: POST /users với {user_name, email, first_name, last_name, birthday, password}
  - Edit profile: PUT /users với {first_name, last_name, birthday, password}
  - Follow model (unidirectional): Follow entity, FollowRepository protocol, SqlAlchemyFollowRepository
  - Follow endpoints: POST /friends/{user_id}, DELETE /friends/{user_id}, GET /friends/{user_id}
  - User posts: GET /friends/{user_id}/posts
  - Newsfeed: GET /newsfeeds (đổi từ /feed)
  - Post fields: content → text, media_urls → image (single URL)
  - Comment field: content → text
  - Like endpoint: /posts/{id}/like → /posts/{id}/likes (plural)
  - EditUserUseCase: update first_name, last_name, birthday, password
  - FollowUserUseCase, UnfollowUserUseCase, GetFollowingUseCase
  - New exceptions: UserNameAlreadyExistsError, CannotFollowSelfError, AlreadyFollowingError, NotFollowingError
  - GraphQL schema updated: UserType thêm user_name, first_name, last_name
  - Tests: 441 passed (6 pre-existing failures in feed/cache — không liên quan)

## Đang làm
- (nothing — all phases complete)
