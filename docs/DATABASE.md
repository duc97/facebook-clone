# Database Design

Facebook Clone Backend — PostgreSQL 16 · SQLAlchemy 2.0 · Alembic migrations 001–006

---

## Table of Contents

1. [Entity Relationship Diagram](#1-entity-relationship-diagram)
2. [Schema Design Decisions](#2-schema-design-decisions)
3. [Index Strategy](#3-index-strategy)
4. [Query Patterns](#4-query-patterns)
5. [Migration Guide](#5-migration-guide)
6. [Performance Considerations](#6-performance-considerations)

---

## 1. Entity Relationship Diagram

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                               USERS (auth)                                        │
│  PK  id              UUID        NOT NULL                                         │
│      email           VARCHAR     NOT NULL  UNIQUE                                 │
│      hashed_password VARCHAR     NOT NULL                                         │
│      display_name    VARCHAR     NOT NULL                                         │
│      is_active       BOOLEAN     DEFAULT TRUE                                     │
│      created_at      TIMESTAMPTZ NOT NULL                                         │
│      updated_at      TIMESTAMPTZ NOT NULL                                         │
└────────────────────────────────────┬──────────────────────────────────────────────┘
  │ 1                                │ 1                      │ 1
  │                                  │                        │
  │ 1:1                              │ 1:N                    │ 1:N (actor)
  ▼                                  ▼                        │
┌───────────────────────┐   ┌──────────────────────┐         │
│ PROFILES              │   │ POSTS                │         │
│ PK  id       UUID     │   │ PK  id       UUID    │         │
│ FK  user_id  UUID ────┤   │ FK  author_id UUID───┤         │
│     bio      TEXT     │   │     content   TEXT   │         │
│     avatar_url        │   │     media_urls TEXT[]│         │
│     cover_photo_url   │   │     like_count  INT  │         │
│     location  VARCHAR │   │     comment_count INT│         │
│     website   VARCHAR │   │     is_published BOOL│         │
│     date_of_birth DATE│   │     created_at        │         │
│     created_at        │   │     updated_at        │         │
│     updated_at        │   └──────────────────────┘         │
└───────────────────────┘     │ 1:N      │ 1:N    │ 1:N      │
                              │          │        │           │
                 ┌────────────┘  ┌───────┘        │           │
                 │ 1:N           │ 1:N (via FK)    │           │
                 ▼              ▼                 ▼           ▼
        ┌───────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐
        │ COMMENTS      │ │ LIKES        │ │ REACTIONS    │ │ SHARES        │
        │ PK id  UUID   │ │ PK id  UUID  │ │ PK id  UUID  │ │ PK id  UUID   │
        │ FK post_id ───┤ │ FK post_id ──┤ │ FK post_id ──┤ │ FK post_id ───┤
        │ FK author_id  │ │ FK user_id ──┤ │ FK user_id ──┤ │ FK user_id    │
        │    content    │ │    created_at│ │  reaction_type│ │    content    │
        │    created_at │ │ UQ(post,user)│ │    created_at│ │    created_at │
        │    updated_at │ └──────────────┘ │ UQ(post,user)│ └───────────────┘
        └───────────────┘                 └──────────────┘

┌───────────────────────────────────────────────────────────────────────────────────┐
│  FRIEND REQUEST STATE MACHINE          BIDIRECTIONAL FRIENDSHIP                   │
│                                                                                   │
│  ┌──────────────────────────────┐      ┌──────────────────────────┐               │
│  │ FRIEND_REQUESTS              │      │ FRIENDSHIPS              │               │
│  │ PK  id          UUID         │      │ PK id          UUID      │               │
│  │ FK  sender_id   UUID → users │      │ FK user_id     UUID      │               │
│  │ FK  receiver_id UUID → users │      │ FK friend_id   UUID      │               │
│  │     status  pending/         │      │    created_at            │               │
│  │             accepted/        │      │ UQ(user_id, friend_id)   │               │
│  │             rejected         │      └──────────────────────────┘               │
│  │     created_at               │      NOTE: One request → two rows               │
│  │     updated_at               │      (A→B) and (B→A) for                        │
│  │ UQ(sender_id, receiver_id)   │      bidirectional lookup                       │
│  └──────────────────────────────┘                                                 │
└───────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────────┐
│  MESSAGES (1:1 chat)                   NOTIFICATIONS (polymorphic)                │
│                                                                                   │
│  ┌──────────────────────────┐          ┌──────────────────────────┐               │
│  │ MESSAGES                 │          │ NOTIFICATIONS            │               │
│  │ PK  id          UUID     │          │ PK  id         UUID      │               │
│  │ FK  sender_id   UUID     │          │ FK  user_id    UUID      │               │
│  │ FK  receiver_id UUID     │          │ FK  actor_id   UUID      │               │
│  │     content     TEXT     │          │     notification_type    │               │
│  │     is_seen     BOOLEAN  │          │     entity_id   UUID     │               │
│  │     created_at           │          │     entity_type VARCHAR  │               │
│  └──────────────────────────┘          │     message     TEXT     │               │
│                                        │     is_read     BOOLEAN  │               │
│                                        │     created_at           │               │
│                                        └──────────────────────────┘               │
└───────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────────┐
│  MEDIA (polymorphic entity, status machine)                                       │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐              │
│  │ MEDIA                                                           │              │
│  │ PK  id              UUID                                        │              │
│  │ FK  owner_id        UUID → users                                │              │
│  │     entity_id       UUID  (nullable — set after post creation)  │              │
│  │     entity_type     VARCHAR  ('post' | 'profile' | 'message')   │              │
│  │     original_url    VARCHAR  (temp path → S3 URL after process) │              │
│  │     thumbnail_url   VARCHAR                                     │              │
│  │     processed_url   VARCHAR  (WebP / transcoded video)          │              │
│  │     media_type      VARCHAR  ('image' | 'video' | 'audio')      │              │
│  │     content_type    VARCHAR  (MIME type)                        │              │
│  │     file_size       BIGINT                                      │              │
│  │     width / height  INTEGER                                     │              │
│  │     duration_seconds FLOAT                                      │              │
│  │     status          VARCHAR  pending→processing→ready→failed    │              │
│  │     created_at      TIMESTAMPTZ                                 │              │
│  └─────────────────────────────────────────────────────────────────┘              │
└───────────────────────────────────────────────────────────────────────────────────┘

Cardinalities summary:
  users      1:1    profiles
  users      1:N    posts          (author_id)
  users      1:N    comments       (author_id)
  users      1:N    likes          (user_id)
  users      1:N    reactions      (user_id)
  users      1:N    shares         (user_id)
  users      1:N    messages       (sender_id or receiver_id)
  users      1:N    notifications  (user_id)
  users      1:N    media          (owner_id)
  users      M:N    users          (via friendships — two rows per pair)
  users      M:N    users          (via friend_requests — one row per request)
  posts      1:N    comments
  posts      1:N    likes
  posts      1:N    reactions
  posts      1:N    shares
  posts      M:N    media          (via media.entity_id + entity_type='post')
```

---

## 2. Schema Design Decisions

### Users + Profiles — Separation of Concerns

**Why split into two tables?**

`users` holds authentication-critical data: `email`, `hashed_password`, `is_active`. This table is queried on every login and every JWT validation. Keeping it narrow (7 columns) maximises cache efficiency and minimises row size for index-only scans on `email`.

`profiles` holds display data: `bio`, `avatar_url`, `cover_photo_url`, `location`, `website`, `date_of_birth`. This data is only needed when rendering a user's profile page and can be cached independently with a longer TTL (300 s in Redis).

The 1:1 relationship is enforced by the `UNIQUE` constraint on `profiles.user_id`. Deleting a user cascades to the profile. Profile creation is idempotent — the application creates both rows in the same transaction during registration.

**Trade-off**: Requires a JOIN when you need both auth + display data. Mitigated by caching the combined `UserProfileDTO` in Redis.

---

### Friend System — Separate Tables for State Machine and Bidirectionality

**`friend_requests`** models the state machine:

```
Alice sends request to Bob
  → INSERT friend_requests (sender=Alice, receiver=Bob, status=pending)

Bob accepts
  → UPDATE friend_requests SET status=accepted
  → INSERT friendships (user_id=Alice, friend_id=Bob)
  → INSERT friendships (user_id=Bob,   friend_id=Alice)

Bob rejects
  → UPDATE friend_requests SET status=rejected
```

Keeping `friend_requests` separate from `friendships` allows:
- Querying pending incoming/outgoing requests efficiently
- Preventing duplicate requests (`UNIQUE(sender_id, receiver_id)`)
- Audit trail of the relationship history

**`friendships`** stores two symmetric rows per friendship `(A→B)` and `(B→A)`. This is a deliberate denormalisation for query simplicity:

```sql
-- "All friends of user X" — single table scan, no OR
SELECT friend_id FROM friendships WHERE user_id = :x
```

Without the symmetric row, every query would need `WHERE user_id = :x OR friend_id = :x`, which prevents index-only scans. The `UNIQUE(user_id, friend_id)` constraint prevents duplicates.

---

### Posts + Comments + Likes + Reactions + Shares

**Denormalised counters** (`like_count`, `comment_count` on `posts`):

These are maintained by application-level increments (`UPDATE posts SET like_count = like_count + 1`) rather than recomputed by `COUNT(*)`. This is a classic read-optimised denormalisation — feed queries read `like_count` without a subquery join.

**Risk**: Counter drift if a transaction partially fails. Mitigated by running count updates in the same DB transaction as the insert, and by a nightly reconciliation job.

**`media_urls TEXT[]`** on posts stores S3 URL strings after media processing completes. The `media` table holds the full metadata. Posts reference the final processed URLs directly for fast rendering without a join.

**`reactions`** vs **`likes`**: Both tables exist because `likes` is a boolean (you liked or you didn't), while `reactions` stores a `reaction_type` enum (like, love, haha, sad, angry). The `UNIQUE(post_id, user_id)` constraint on both ensures one record per user per post. In practice, you may choose to consolidate — having both is a legacy decision retained for backward compatibility.

---

### Messages — Simple 1:1 Chat Model

The `messages` table implements direct messages without conversation grouping. Each row has `sender_id`, `receiver_id`, `content`, and `is_seen`.

**Why no conversation table?** A conversation between A and B is identified by the pair `(min(A,B), max(A,B))` — no separate row needed. Conversation lists are derived by a `DISTINCT ON` query (see §4).

**`is_seen`** is a boolean, not a timestamp, intentionally. Read receipts in this implementation are per-message but the UI shows "seen" once per conversation. Upgrading to a timestamp is a non-breaking schema change.

The index `ix_messages_receiver_seen (receiver_id, is_seen)` accelerates unread message counts per user.

---

### Notifications — Polymorphic Entity Pattern

`entity_id` + `entity_type` allow a single notifications table to reference any entity:

| notification_type | entity_type | entity_id points to |
|---|---|---|
| like | post | posts.id |
| comment | post | posts.id |
| friend_request | user | users.id |
| share | post | posts.id |
| mention | comment | comments.id |

This avoids a separate notifications table per entity type. The application resolves the entity in a second lookup (cached). The `ix_notifications_user_read_created` index covers the most common access pattern: "Show user X's unread notifications, newest first."

---

### Media — Status Machine + Entity Polymorphism

The `status` field follows a strict state machine:

```
pending → processing → ready
                    ↘ failed
```

- `pending`: Row created, original bytes uploaded to temp storage
- `processing`: Background pipeline started (Pillow / ffmpeg)
- `ready`: S3 URLs written back, safe to reference from posts
- `failed`: Pipeline errored; row retained for debugging

**Why a separate table instead of embedding in posts?** Media can be associated with profiles (avatars, cover photos), posts, and messages. The `entity_id` / `entity_type` polymorphism supports all cases. Media is uploaded before post creation — the `entity_id` is NULL until the post is saved, then backfilled.

The `ix_media_entity (entity_type, entity_id)` composite index is the primary access path: "All media for post X".

---

## 3. Index Strategy

| Index Name | Table | Columns | Query It Serves | Notes |
|---|---|---|---|---|
| `ix_users_email` | users | `email` | Login by email, JWT validation, uniqueness check | High selectivity (unique) |
| `ix_friend_requests_receiver_status` | friend_requests | `(receiver_id, status)` | "Pending requests for user X" | Partial — most rows are status≠pending over time |
| `ix_friendships_user_id` | friendships | `user_id` | Friend list lookup (fan-out, feed, suggestions) | High cardinality on user_id |
| `ix_friendships_friend_id` | friendships | `friend_id` | Reverse lookup: "Who is friends with X?" | Supports deletion cascade |
| `ix_friendships_user_friend` | friendships | `(user_id, friend_id)` | "Is A friends with B?" existence check | Covering index for UQ check |
| `ix_posts_author_created` | posts | `(author_id, created_at)` | Profile page: posts by user, newest first | Composite avoids sort |
| `ix_posts_created_at` | posts | `created_at` | Global trending / admin queries | Low selectivity — used rarely |
| `ix_posts_published_author_created` | posts | `(is_published, author_id, created_at)` | Feed query: published posts by friend, newest first | Filters out drafts cheaply |
| `ix_posts_published_created` | posts | `(is_published, created_at)` | Public explore / search feed | Partial index equivalent |
| `ix_comment_post_created` | comments | `(post_id, created_at)` | Comments on post X, paginated | Time-ordered within post |
| `ix_message_conversation` | messages | `(sender_id, receiver_id, created_at)` | Message history between A and B | Covers both query directions with OR; see note |
| `ix_messages_receiver_seen` | messages | `(receiver_id, is_seen)` | Unread message count for user X | Low cardinality on is_seen — effective as partial |
| `ix_notification_user_created` | notifications | `(user_id, created_at)` | Notification list for user X | Base index |
| `ix_notifications_user_read_created` | notifications | `(user_id, is_read, created_at)` | Unread notifications for user X, newest first | Supersedes base index for most queries |
| `ix_media_entity` | media | `(entity_type, entity_id)` | All media for a post / profile | Primary media lookup path |
| `ix_media_owner` | media | `owner_id` | "All uploads by user X" (profile media grid) | Moderate selectivity |
| `ix_reactions_post_id` | reactions | `post_id` | Reactions count / type breakdown per post | Covers aggregate queries |
| `ix_shares_post_id` | shares | `post_id` | Share count + list per post | Low expected volume |

**Note on `ix_message_conversation`**: The conversation history query uses `(sender_id=A AND receiver_id=B) OR (sender_id=B AND receiver_id=A)`. PostgreSQL may use a bitmap OR of two index scans. A union rewrite or a generated `conversation_id` column (sorted pair hash) would give a cleaner index; this is a known optimisation candidate.

---

## 4. Query Patterns

### 4.1 Feed Query (Friends' Posts, Newest First)

Used as the PostgreSQL fallback when the Redis ZSET cache is cold or expired.

```sql
-- Feed for user :current_user_id, page cursor :before_ts, limit 20
SELECT
    p.id,
    p.author_id,
    p.content,
    p.media_urls,
    p.like_count,
    p.comment_count,
    p.created_at,
    u.display_name   AS author_name,
    pr.avatar_url    AS author_avatar
FROM posts p
JOIN friendships f
    ON p.author_id = f.friend_id
    AND f.user_id  = :current_user_id
JOIN users u
    ON u.id = p.author_id
JOIN profiles pr
    ON pr.user_id = p.author_id
WHERE p.is_published = TRUE
  AND p.created_at  < :before_ts          -- cursor pagination
ORDER BY p.created_at DESC
LIMIT 20;

-- Index path:
--   ix_posts_published_author_created on posts (is_published, author_id, created_at)
--   ix_friendships_user_id on friendships (user_id)
--   Nested-loop join: friendships → posts index scan per friend
```

**Explain target**: Nested loop with index scans; avoid sequential scan on posts. For users with 500 friends this is ~500 index seeks, each returning a small number of rows. Redis ZSET eliminates this query in the common case.

---

### 4.2 Conversation List (DISTINCT ON CTE to Avoid N+1)

Returns the most recent message per conversation for a user's inbox.

```sql
-- All conversations for user :uid, showing latest message per partner
WITH ranked AS (
    SELECT
        m.*,
        CASE
            WHEN m.sender_id   = :uid THEN m.receiver_id
            WHEN m.receiver_id = :uid THEN m.sender_id
        END AS partner_id,
        ROW_NUMBER() OVER (
            PARTITION BY LEAST(m.sender_id, m.receiver_id),
                         GREATEST(m.sender_id, m.receiver_id)
            ORDER BY m.created_at DESC
        ) AS rn
    FROM messages m
    WHERE m.sender_id = :uid
       OR m.receiver_id = :uid
)
SELECT
    r.partner_id,
    r.content        AS last_message,
    r.created_at     AS last_message_at,
    r.is_seen,
    u.display_name,
    pr.avatar_url
FROM ranked r
JOIN users   u  ON u.id  = r.partner_id
JOIN profiles pr ON pr.user_id = r.partner_id
WHERE r.rn = 1
ORDER BY r.last_message_at DESC
LIMIT 20;

-- Index path: ix_message_conversation on messages (sender_id, receiver_id, created_at)
-- The OR condition may trigger a BitmapOr of two index scans.
-- Alternative: maintain a separate conversations table updated on each message.
```

---

### 4.3 Unread Notification Count

Used on every page load to show the notification bell badge. Cached in Redis (TTL=30s, key `notif_unread:{user_id}`).

```sql
-- Called only on Redis cache miss
SELECT COUNT(*)
FROM notifications
WHERE user_id = :uid
  AND is_read = FALSE;

-- Index path: ix_notifications_user_read_created (user_id, is_read, created_at)
-- is_read=FALSE rows are few relative to total — effective partial scan
```

---

### 4.4 Media by Entity

Fetches all media rows for a given post (or profile, message, etc.).

```sql
SELECT
    id,
    thumbnail_url,
    processed_url,
    media_type,
    width,
    height,
    duration_seconds,
    status
FROM media
WHERE entity_type = :entity_type     -- e.g. 'post'
  AND entity_id   = :entity_id
  AND status      = 'ready'
ORDER BY created_at ASC;

-- Index path: ix_media_entity (entity_type, entity_id)
-- entity_id is UUID — high selectivity; typical post has 1–4 media rows
```

---

### 4.5 Friend Suggestions (Mutual Friends)

Returns users who are friends-of-friends but not already friends with the current user.

```sql
-- Friends of friends, ordered by mutual count, not already friends
SELECT
    candidate_id,
    COUNT(*) AS mutual_count,
    u.display_name,
    pr.avatar_url
FROM (
    -- Friends of my friends
    SELECT f2.friend_id AS candidate_id
    FROM friendships f1
    JOIN friendships f2
        ON f2.user_id = f1.friend_id
    WHERE f1.user_id   = :uid
      AND f2.friend_id <> :uid
) candidates
JOIN users   u  ON u.id  = candidates.candidate_id
JOIN profiles pr ON pr.user_id = candidates.candidate_id
WHERE NOT EXISTS (
    SELECT 1 FROM friendships
    WHERE user_id = :uid AND friend_id = candidates.candidate_id
)
GROUP BY candidate_id, u.display_name, pr.avatar_url
ORDER BY mutual_count DESC
LIMIT 10;

-- Index path:
--   ix_friendships_user_id on friendships (user_id) — both f1 and f2 scans
--   ix_friendships_user_friend on friendships (user_id, friend_id) — NOT EXISTS check
-- This query is expensive at scale; cache result in Redis (key: suggestions:{uid}, TTL=600s)
```

---

## 5. Migration Guide

### 5.1 Fresh Install (From Scratch)

```bash
# 1. Ensure PostgreSQL is running and the target database exists
createdb facebook_clone

# 2. Configure the database URL in your environment
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/facebook_clone"

# 3. Run all migrations from the project root
alembic upgrade head

# 4. Verify the current revision
alembic current
# Expected: <rev_006_hash> (head)

# 5. Confirm tables were created
psql $DATABASE_URL -c "\dt"
# Expected: 12 tables (users, profiles, friend_requests, friendships,
#            posts, comments, likes, reactions, shares, messages,
#            notifications, media)
```

Alembic reads `alembic.ini` for the script location and `env.py` for the database URL. The async engine in `env.py` uses `run_sync` to apply migrations synchronously (Alembic does not support async natively).

---

### 5.2 Rolling Upgrade (Zero-Downtime in Kubernetes)

Zero-downtime migrations require that the new schema be **backward compatible** with the old running application code during the rollout window.

**Rules for zero-downtime migrations:**

| Operation | Safe? | Strategy |
|---|---|---|
| Add nullable column | ✅ Yes | Apply migration before deploy |
| Add column with default | ✅ Yes | Apply migration before deploy |
| Add index `CONCURRENTLY` | ✅ Yes | Apply migration before deploy |
| Add new table | ✅ Yes | Apply migration before deploy |
| Remove column | ⚠️ No | Remove from code first, then deploy, then remove column |
| Rename column | ❌ No | Add new column, dual-write, backfill, then remove old |
| Change column type | ❌ No | Add new column, backfill, switch reads, remove old |
| Remove table | ⚠️ No | Stop writing, deploy, then drop table |

**Procedure:**

```bash
# Step 1: Apply the migration against the live database BEFORE deploying new pods
# Run from your CI/CD pipeline or a migration job pod
alembic upgrade head

# Step 2: Verify migration applied cleanly
alembic current
# Should show new head revision

# Step 3: Trigger rolling deploy
kubectl set image deployment/facebook-clone-blue \
  app=ghcr.io/org/facebook-clone:v2.0.0
# Kubernetes respects PDB minAvailable=1 — old pods stay up until new pods are Ready

# Step 4: Monitor rollout
kubectl rollout status deployment/facebook-clone-blue
```

**Index creation** in migrations uses `CONCURRENTLY` to avoid table locks:

```python
# In migration file — DO NOT use op.create_index() for large tables in production
op.execute(
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_posts_created_at "
    "ON posts (created_at)"
)
```

Alembic's `--sql` flag generates the raw SQL for DBAs to review before applying.

---

### 5.3 Rollback Procedure

```bash
# Roll back one migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision_id>

# View migration history
alembic history --verbose

# Roll back to the very beginning (empty schema)
alembic downgrade base
```

**Important caveats:**
- Dropping columns or tables in `downgrade()` will permanently destroy data. Always take a snapshot before rolling back in production.
- Indexes created with `CONCURRENTLY` cannot be dropped inside a transaction. Use `op.execute("DROP INDEX CONCURRENTLY ...")`.
- If a migration added data (seed rows), the `downgrade()` must DELETE those rows to restore the prior state.

---

### 5.4 Adding New Migrations

**Naming convention:** `{NNN}_{short_snake_case_description}.py`

```
migrations/versions/
  001_initial_schema.py
  002_add_reactions_shares.py
  003_add_media_table.py
  004_add_notification_improvements.py
  005_add_missing_indexes.py
  006_performance_indexes.py
  007_your_new_migration.py   ← increment the prefix
```

**Generating a migration from model changes:**

```bash
alembic revision --autogenerate -m "add_search_vector_to_posts"
# Review the generated file — autogenerate is not perfect
# Always check: added columns have server_default or nullable=True
# Always check: index creation uses CONCURRENTLY for large tables
```

**DOs and DON'Ts:**

```
DO:
  ✅ Always provide both upgrade() and downgrade()
  ✅ Use IF NOT EXISTS / IF EXISTS guards
  ✅ Test migrations on a database snapshot before applying to production
  ✅ Use CONCURRENTLY for index creation on tables with > 100k rows
  ✅ Run alembic check in CI to detect model/migration drift

DON'T:
  ❌ Squash or edit existing migration files after they reach production
  ❌ Use server_default=func.now() without testing timezone handling
  ❌ Add NOT NULL columns without a default (table rewrite locks the table)
  ❌ Skip the downgrade() implementation ("not needed" — it always is)
  ❌ Run migrations inside the application startup path in production
```

---

## 6. Performance Considerations

### 6.1 Connection Pooling Configuration

```python
# src/infrastructure/database.py
create_async_engine(
    DATABASE_URL,
    pool_size=10,       # Persistent connections kept open
    max_overflow=20,    # Additional connections allowed under peak load
    pool_recycle=3600,  # Recycle connections after 1 hour (prevents stale TCP)
    pool_timeout=30,    # Raise after 30s if no connection available
    pool_pre_ping=True, # Test connection health before use (handles pg restarts)
    connect_args={
        "server_settings": {"jit": "off"}
    }
)
```

**Sizing rationale:**
- `pool_size=10` × up to 20 pods = 200 concurrent connections to PostgreSQL. PostgreSQL default `max_connections=100` should be raised to at least 250 in `postgresql.conf` (`max_connections=300`).
- `max_overflow=20` handles request spikes. Connections above `pool_size` are closed immediately after use.
- `pool_recycle=3600`: Long-lived TCP connections can go stale after network equipment idle timeouts (commonly 30 min). Recycling at 1 hour is conservative and safe.

**PgBouncer** is recommended in front of PostgreSQL in production to multiplex application connections through transaction-level pooling, reducing PostgreSQL's actual connection count.

---

### 6.2 Why JIT is Disabled

PostgreSQL's Just-In-Time compilation (`jit=on` by default in PG 12+) compiles query plans to machine code for long-running analytical queries. For OLTP workloads (short, frequent queries like those in this application), JIT adds compilation overhead without benefit:

- Typical query runtime: 0.5–5 ms
- JIT compilation cost: 5–50 ms for first execution
- Net effect: JIT makes fast queries slower

```python
connect_args={"server_settings": {"jit": "off"}}
```

This is set at the connection level, not `postgresql.conf`, so it applies only to application connections and does not affect maintenance operations or analytics queries run by a DBA.

---

### 6.3 VACUUM and Autovacuum Recommendations

PostgreSQL uses Multi-Version Concurrency Control (MVCC). Dead tuples accumulate from updates and deletes. `VACUUM` reclaims this space.

**High-churn tables** that need tuned autovacuum:

| Table | High-churn operation | Recommended setting |
|---|---|---|
| `posts` | `like_count` / `comment_count` increments on every like/comment | `autovacuum_vacuum_scale_factor=0.01` |
| `notifications` | Bulk inserts + mark-as-read updates | `autovacuum_vacuum_scale_factor=0.01` |
| `messages` | `is_seen` updates + constant inserts | `autovacuum_vacuum_scale_factor=0.01` |
| `likes` | High insert/delete rate | `autovacuum_vacuum_scale_factor=0.02` |

Apply via `ALTER TABLE`:

```sql
ALTER TABLE posts SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_analyze_scale_factor = 0.005
);
```

**Weekly manual VACUUM ANALYZE** is recommended for the feed-critical tables during off-peak hours:

```sql
VACUUM ANALYZE posts;
VACUUM ANALYZE friendships;
VACUUM ANALYZE notifications;
```

**Bloat monitoring**: Query `pg_stat_user_tables` for `n_dead_tup` and alert when dead tuples exceed 20% of live tuples.

---

### 6.4 Query EXPLAIN Examples

#### Feed Query — Expected Plan

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT p.id, p.content, p.created_at
FROM posts p
JOIN friendships f ON p.author_id = f.friend_id AND f.user_id = '…uuid…'
WHERE p.is_published = TRUE
ORDER BY p.created_at DESC
LIMIT 20;
```

**Expected output (healthy):**

```
Limit  (cost=… rows=20)
  ->  Sort  (cost=… sort key: p.created_at DESC)
        ->  Nested Loop
              ->  Index Scan using ix_friendships_user_id on friendships f
                    Index Cond: (user_id = '…uuid…')
              ->  Index Scan using ix_posts_published_author_created on posts p
                    Index Cond: (is_published = TRUE AND author_id = f.friend_id)
Buffers: shared hit=NNN read=0  ← all in buffer cache, no disk reads
```

**Warning signs:**

| Plan node | Problem | Fix |
|---|---|---|
| `Seq Scan on posts` | Missing index or planner choosing full scan | Run `ANALYZE posts`; check index exists |
| `Hash Join` instead of `Nested Loop` | Planner estimates many friend rows | Likely correct for users with 500 friends; acceptable |
| `Sort` with `Buffers: read=NNN` | Sort spilling to disk | Increase `work_mem` for this session: `SET work_mem = '64MB'` |
| High `Rows Removed by Filter` | Index not filtering effectively | Consider partial index `WHERE is_published = TRUE` |

#### Unread Notification Count — Expected Plan

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) FROM notifications
WHERE user_id = '…uuid…' AND is_read = FALSE;
```

**Expected:**

```
Aggregate
  ->  Index Scan using ix_notifications_user_read_created on notifications
        Index Cond: (user_id = '…uuid…' AND is_read = FALSE)
Buffers: shared hit=2  ← 2 index pages, no table heap access
```

This is an **index-only scan** if `count(*)` can be satisfied from the index. Verify with `EXPLAIN` that `Heap Fetches=0`. If not, run `VACUUM notifications` to update the visibility map.

---

### 6.5 Slow Query Monitoring

Enable slow query logging in `postgresql.conf`:

```ini
log_min_duration_statement = 100   # log queries taking > 100ms
log_statement = 'none'
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

In Kubernetes, ship PostgreSQL logs to Loki via Promtail. Set up a Grafana alert for queries exceeding 500 ms. Use `pg_stat_statements` extension for aggregate query performance tracking:

```sql
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
```

---

*Last updated: 2026-03-13*
