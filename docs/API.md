# Facebook Clone — REST API Reference

> **Version:** 1.0
> **Last updated:** 2026-03-13
> **Base URL:** `http://localhost:8000`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Rate Limiting](#3-rate-limiting)
4. [Error Handling](#4-error-handling)
5. [Versioning Strategy](#5-versioning-strategy)
6. [Endpoints by Module](#6-endpoints-by-module)
   - [Auth](#61-auth)
   - [Users](#62-users)
   - [Friends](#63-friends)
   - [Posts](#64-posts)
   - [Feed](#65-feed)
   - [Messages](#66-messages)
   - [Notifications](#67-notifications)
   - [Media](#68-media)
   - [Search](#69-search)
   - [Health & Metrics](#610-health--metrics)
7. [Caching Behavior](#7-caching-behavior)

---

## 1. Overview

### Base URL and Versioning

| Property        | Value                          |
|-----------------|-------------------------------|
| Base URL        | `http://localhost:8000`       |
| API Prefix      | `/api/v1/`                    |
| Content-Type    | `application/json`            |
| Auth Scheme     | Bearer JWT (Authorization header) |
| GraphQL         | `POST /graphql`               |

All REST endpoints are prefixed with `/api/v1/`. Breaking changes are introduced under a new version prefix (e.g., `/api/v2/`).

### Response Envelope

Every response — success or error — is wrapped in a consistent envelope:

```json
{
  "success": true,
  "data": { },
  "error": null,
  "meta": {
    "total": 100,
    "page": 1,
    "limit": 20,
    "has_next": true
  },
  "version": "1.0"
}
```

| Field     | Type            | Description                                              |
|-----------|-----------------|----------------------------------------------------------|
| `success` | `boolean`       | `true` on success, `false` on error                     |
| `data`    | `any \| null`   | Response payload; `null` when an error occurs           |
| `error`   | `object \| null`| Error details; `null` on success                        |
| `meta`    | `object \| null`| Pagination metadata; present on list endpoints          |
| `version` | `string`        | API version string (`"1.0"`)                            |

### Pagination

All list endpoints accept `page` and `limit` query parameters:

| Parameter | Default | Max  | Description              |
|-----------|---------|------|--------------------------|
| `page`    | `1`     | —    | 1-based page number      |
| `limit`   | `20`    | `100`| Items per page           |

**Pagination response inside `meta`:**

```json
{
  "meta": {
    "total": 243,
    "page": 2,
    "limit": 20,
    "has_next": true
  }
}
```

---

## 2. Authentication

### Auth Flow

```
┌──────────┐                          ┌──────────────┐
│  Client  │                          │  API Server  │
└────┬─────┘                          └──────┬───────┘
     │                                       │
     │  POST /api/v1/auth/register           │
     │  { email, password, username }        │
     │──────────────────────────────────────▶│
     │                                       │  Hash password (bcrypt)
     │                                       │  Create user record
     │                                       │  Issue access + refresh tokens
     │  200 { access_token, refresh_token }  │
     │◀──────────────────────────────────────│
     │                                       │
     │  GET /api/v1/auth/me                  │
     │  Authorization: Bearer <access_token> │
     │──────────────────────────────────────▶│
     │                                       │  Verify JWT signature
     │                                       │  Check token expiry
     │  200 { user }                         │
     │◀──────────────────────────────────────│
     │                                       │
     │  POST /api/v1/auth/refresh            │
     │  { refresh_token }                    │
     │──────────────────────────────────────▶│
     │                                       │  Validate refresh token
     │                                       │  Check not blacklisted
     │                                       │  Issue new token pair
     │                                       │  Blacklist old refresh token
     │  200 { access_token, refresh_token }  │
     │◀──────────────────────────────────────│
     │                                       │
     │  POST /api/v1/auth/logout             │
     │  Authorization: Bearer <access_token> │
     │──────────────────────────────────────▶│
     │                                       │  Add access token to blacklist
     │                                       │  Add refresh token to blacklist
     │  204 No Content                       │
     │◀──────────────────────────────────────│
```

### JWT Token Lifecycle

| Token Type    | Lifetime | Storage Recommendation      | Notes                              |
|---------------|----------|-----------------------------|-------------------------------------|
| Access Token  | 15 min   | Memory (variable)           | Short-lived; used on every request |
| Refresh Token | 7 days   | HttpOnly cookie or secure storage | Used only to obtain a new pair |

- **Blacklisting:** On logout, both tokens are stored in Redis with their remaining TTL. Subsequent requests with blacklisted tokens return `401`.
- **Rotation:** Each call to `/auth/refresh` invalidates the submitted refresh token and issues a fresh pair (refresh token rotation).
- **Signature:** RS256 or HS256 (configurable). All tokens include `sub` (user_id), `iat`, and `exp` claims.

### Using Tokens in Requests

```http
GET /api/v1/auth/me HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
```

### Token Refresh Flow

When the client receives a `401` with `"code": "token_expired"`, it should:

1. Pause in-flight requests.
2. `POST /api/v1/auth/refresh` with the stored refresh token.
3. On success, store the new token pair and retry the original requests.
4. On `401` from `/auth/refresh`, clear stored tokens and redirect to login.

---

## 3. Rate Limiting

### Policy Table

| Client Type | Limit      | Window     | Algorithm       |
|-------------|------------|------------|-----------------|
| Guest       | 30 req/min | 60 seconds | Sliding window  |
| Authenticated user | 60 req/min | 60 seconds | Sliding window |

> Premium tier limits are reserved for future use.

### Response Headers

Every response includes rate-limit headers:

| Header                  | Description                                      |
|-------------------------|--------------------------------------------------|
| `X-RateLimit-Limit`     | Maximum requests allowed in the window          |
| `X-RateLimit-Remaining` | Remaining requests in the current window        |
| `X-RateLimit-Reset`     | Unix timestamp when the window resets           |
| `Retry-After`           | Seconds to wait (present only on `429` response)|

**Example headers on a normal response:**

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 47
X-RateLimit-Reset: 1741870380
```

### 429 Rate Limit Exceeded

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests. Please slow down.",
    "retry_after": 14
  },
  "meta": null,
  "version": "1.0"
}
```

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 14
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1741870380
```

### Sliding Window Algorithm

The sliding window is implemented using Redis sorted sets:

1. Each request is recorded as a member with its Unix timestamp as score.
2. On each request, members older than `now - window_size` are removed (`ZREMRANGEBYSCORE`).
3. The current count is the size of the set (`ZCARD`).
4. If count ≥ limit, return `429`; otherwise, add the new entry and proceed.
5. The key expires automatically after `window_size` seconds of inactivity.

---

## 4. Error Handling

### Error Response Format

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "string",
    "message": "Human-readable description",
    "details": { }
  },
  "meta": null,
  "version": "1.0"
}
```

### Error Codes Table

| HTTP Status | Code                   | Description                                          | Resolution                                        |
|-------------|------------------------|------------------------------------------------------|---------------------------------------------------|
| `400`       | `validation_error`     | Request body or query parameter failed validation   | Fix the fields listed in `details`                |
| `401`       | `unauthorized`         | Authorization header missing                        | Include a valid Bearer token                      |
| `401`       | `token_invalid`        | JWT signature or format is invalid                  | Re-authenticate                                   |
| `401`       | `token_expired`        | Access token has expired                            | Use refresh token to obtain a new access token   |
| `401`       | `token_revoked`        | Token has been blacklisted (post-logout)            | Re-authenticate                                   |
| `403`       | `forbidden`            | Authenticated but not the resource owner            | Use the correct account or check permissions      |
| `404`       | `not_found`            | Requested resource does not exist                   | Verify the ID or path                             |
| `409`       | `conflict`             | Duplicate action (double like, already friends)     | Check current state before retrying               |
| `422`       | `unprocessable_entity` | FastAPI schema validation failure                   | Check types and required fields                   |
| `429`       | `rate_limit_exceeded`  | Too many requests                                   | Back off for `retry_after` seconds                |
| `500`       | `internal_error`       | Unhandled server-side exception                     | Retry after a delay; report if persistent         |
| `503`       | `service_unavailable`  | Database or Redis is not healthy                    | Check `/ready` for service status                 |

### Error Examples

**400 — Validation Error**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": {
      "email": ["value is not a valid email address"],
      "password": ["must be at least 8 characters"]
    }
  },
  "meta": null,
  "version": "1.0"
}
```

**401 — Token Expired**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "token_expired",
    "message": "Access token has expired. Please refresh your session.",
    "details": {}
  },
  "meta": null,
  "version": "1.0"
}
```

**403 — Forbidden**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "forbidden",
    "message": "You do not have permission to modify this resource.",
    "details": {}
  },
  "meta": null,
  "version": "1.0"
}
```

**404 — Not Found**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "not_found",
    "message": "Post with id '99999' not found.",
    "details": {}
  },
  "meta": null,
  "version": "1.0"
}
```

**409 — Conflict**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "conflict",
    "message": "You have already liked this post.",
    "details": {}
  },
  "meta": null,
  "version": "1.0"
}
```

### Handling Expired Access Tokens

```
Client receives 401 { "code": "token_expired" }
  │
  ├─▶ POST /api/v1/auth/refresh { "refresh_token": "..." }
  │       ├─▶ 200: Store new tokens, retry original request
  │       └─▶ 401: Clear all tokens, redirect user to /login
```

---

## 5. Versioning Strategy

### URL-Based Versioning

The API uses URL path versioning (`/api/v1/`). The version segment is mandatory and will not change for backward-compatible updates.

### Deprecation Policy

1. A new version (`/api/v2/`) is introduced for breaking changes.
2. The old version receives a `Deprecation` response header with a sunset date:
   ```http
   Deprecation: true
   Sunset: Sat, 01 Jan 2027 00:00:00 GMT
   Link: <http://localhost:8000/api/v2/>; rel="successor-version"
   ```
3. Deprecated versions are supported for a minimum of **6 months** after announcement.

### Breaking vs Non-Breaking Changes

| Change Type                          | Classification  | Version Bump |
|--------------------------------------|-----------------|--------------|
| Add new optional field to response   | Non-breaking    | No           |
| Add new optional query parameter     | Non-breaking    | No           |
| Add new endpoint                     | Non-breaking    | No           |
| Remove a field from response         | **Breaking**    | Yes          |
| Change field type or rename field    | **Breaking**    | Yes          |
| Remove an endpoint                   | **Breaking**    | Yes          |
| Change authentication requirement    | **Breaking**    | Yes          |
| Change HTTP method for an endpoint   | **Breaking**    | Yes          |

---

## 6. Endpoints by Module

### 6.1 Auth

Base path: `/api/v1/auth`

---

#### `POST /auth/register`

Register a new user account.

- **Auth required:** No
- **Request body:**

```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

- **Common errors:** `400` (validation), `409` (email/username already taken)

---

#### `POST /auth/login`

Authenticate an existing user.

- **Auth required:** No
- **Request body:**

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

- **Response `200`:** Same as `/auth/register`
- **Common errors:** `401` (invalid credentials), `400` (validation)

---

#### `POST /auth/logout`

Invalidate the current session tokens.

- **Auth required:** Yes (Bearer)
- **Request body:**

```json
{
  "refresh_token": "eyJhbGci..."
}
```

- **Response:** `204 No Content`
- **Common errors:** `401`

---

#### `POST /auth/refresh`

Obtain a new access/refresh token pair.

- **Auth required:** No
- **Request body:**

```json
{
  "refresh_token": "eyJhbGci..."
}
```

- **Response `200`:** Same token structure as `/auth/register`
- **Common errors:** `401` (revoked or expired refresh token)

---

#### `GET /auth/me`

Retrieve the currently authenticated user's profile.

- **Auth required:** Yes (Bearer)
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "id": "u_01HX",
    "username": "johndoe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "avatar_url": "https://cdn.example.com/avatars/johndoe.jpg",
    "bio": "Software engineer",
    "created_at": "2025-01-15T10:30:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

### 6.2 Users

Base path: `/api/v1/users`

---

#### `GET /users/{user_id}`

Get a user's public profile. Response is cached for **300 seconds**.

- **Auth required:** No
- **Path params:** `user_id` (string)
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "id": "u_01HX",
    "username": "johndoe",
    "full_name": "John Doe",
    "avatar_url": "https://cdn.example.com/avatars/johndoe.jpg",
    "bio": "Software engineer",
    "friend_count": 142,
    "is_online": true,
    "created_at": "2025-01-15T10:30:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

- **Common errors:** `404`

---

#### `PUT /users/{user_id}`

Update the authenticated user's profile.

- **Auth required:** Yes (Bearer; must be the same user)
- **Request body:** (all fields optional)

```json
{
  "full_name": "John M. Doe",
  "bio": "Full-stack engineer @ ACME",
  "location": "Tokyo, Japan"
}
```

- **Response `200`:** Updated user profile (same shape as `GET /users/{user_id}`)
- **Common errors:** `400`, `403`, `404`

---

#### `POST /users/{user_id}/avatar`

Upload a new avatar image.

- **Auth required:** Yes (Bearer; must be the same user)
- **Request:** `multipart/form-data` with field `file` (JPEG/PNG/WebP, max 5 MB)
- **Response `200`:**

```json
{
  "success": true,
  "data": { "avatar_url": "https://cdn.example.com/avatars/u_01HX_1741870000.jpg" },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `GET /users/{user_id}/posts`

List posts authored by a user. Requires authentication (friend/privacy check).

- **Auth required:** Yes
- **Query params:** `page`, `limit`
- **Response `200`:** Paginated list of post objects (see Post schema in §6.4)

---

#### `GET /users/{user_id}/friends`

List a user's friends.

- **Auth required:** Yes
- **Response `200`:** Paginated list of user profile objects

---

#### `GET /users/online`

Return the list of user IDs currently online.

- **Auth required:** Yes
- **Response `200`:**

```json
{
  "success": true,
  "data": { "online_user_ids": ["u_01HX", "u_02AY", "u_03BZ"] },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `GET /users/{user_id}/online`

Check if a specific user is currently online.

- **Auth required:** Yes
- **Response `200`:**

```json
{
  "success": true,
  "data": { "user_id": "u_01HX", "is_online": true },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

### 6.3 Friends

Base path: `/api/v1/friends`

---

#### `POST /friends/request`

Send a friend request.

- **Auth required:** Yes
- **Request body:**

```json
{ "receiver_id": "u_02AY" }
```

- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "request_id": "fr_09ZX",
    "sender_id": "u_01HX",
    "receiver_id": "u_02AY",
    "status": "pending",
    "created_at": "2026-03-13T08:00:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

- **Common errors:** `409` (request already sent or already friends), `404` (user not found)

---

#### `POST /friends/accept`

Accept a pending friend request.

- **Auth required:** Yes
- **Request body:**

```json
{ "request_id": "fr_09ZX" }
```

- **Response `200`:** Updated friend request with `"status": "accepted"`
- **Common errors:** `404` (request not found), `403` (not the receiver)

---

#### `POST /friends/reject`

Reject a pending friend request.

- **Auth required:** Yes
- **Request body:**

```json
{ "request_id": "fr_09ZX" }
```

- **Response `200`:** Updated friend request with `"status": "rejected"`

---

#### `DELETE /friends/{user_id}`

Remove a friend.

- **Auth required:** Yes
- **Response:** `204 No Content`
- **Common errors:** `404` (not friends with this user)

---

#### `GET /friends/mutual/{user_id}`

Get mutual friends between the authenticated user and another user.

- **Auth required:** Yes
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "mutual_friends": [
      { "id": "u_03BZ", "username": "janedoe", "avatar_url": "..." }
    ],
    "count": 1
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

### 6.4 Posts

Base path: `/api/v1/posts`

---

#### `POST /posts`

Create a new post.

- **Auth required:** Yes
- **Request body:**

```json
{
  "content": "Hello world! 🌍",
  "visibility": "friends",
  "media_ids": ["med_001", "med_002"]
}
```

`visibility` values: `public`, `friends`, `only_me`

- **Response `201`:**

```json
{
  "success": true,
  "data": {
    "id": "p_0A1B",
    "author": { "id": "u_01HX", "username": "johndoe", "avatar_url": "..." },
    "content": "Hello world! 🌍",
    "visibility": "friends",
    "media": [],
    "reaction_counts": { "LIKE": 0, "LOVE": 0, "HAHA": 0, "WOW": 0, "SAD": 0, "ANGRY": 0 },
    "comment_count": 0,
    "share_count": 0,
    "created_at": "2026-03-13T09:00:00Z",
    "updated_at": "2026-03-13T09:00:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `GET /posts/{post_id}`

Get post detail. Cached for **120 seconds**.

- **Auth required:** No
- **Response `200`:** Post object as above
- **Common errors:** `404`

---

#### `PUT /posts/{post_id}`

Edit a post. Owner only.

- **Auth required:** Yes
- **Request body:** `{ "content": "Updated text", "visibility": "public" }` (fields optional)
- **Response `200`:** Updated post object
- **Common errors:** `403`, `404`

---

#### `DELETE /posts/{post_id}`

Delete a post. Owner only.

- **Auth required:** Yes
- **Response:** `204 No Content`

---

#### `GET /posts/{post_id}/comments`

List comments on a post.

- **Auth required:** No
- **Query params:** `page`, `limit`
- **Response `200`:** Paginated list of comment objects

---

#### `POST /posts/{post_id}/comments`

Add a comment to a post.

- **Auth required:** Yes
- **Request body:** `{ "content": "Great post!" }`
- **Response `201`:**

```json
{
  "success": true,
  "data": {
    "id": "c_XY12",
    "post_id": "p_0A1B",
    "author": { "id": "u_01HX", "username": "johndoe", "avatar_url": "..." },
    "content": "Great post!",
    "created_at": "2026-03-13T09:05:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `DELETE /posts/{post_id}/comments/{comment_id}`

Delete a comment. Owner or post owner only.

- **Auth required:** Yes
- **Response:** `204 No Content`

---

#### `POST /posts/{post_id}/like` / `DELETE /posts/{post_id}/like`

Add or remove a simple like on a post.

- **Auth required:** Yes
- **`POST` Response `200`:** `{ "liked": true, "total_likes": 15 }`
- **`DELETE` Response `200`:** `{ "liked": false, "total_likes": 14 }`
- **Common errors:** `409` (already liked on POST)

---

#### `POST /posts/{post_id}/react`

Add or update a reaction.

- **Auth required:** Yes
- **Request body:** `{ "type": "LOVE" }` — one of `LIKE | LOVE | HAHA | WOW | SAD | ANGRY`
- **Response `200`:** `{ "reaction_type": "LOVE", "counts": { "LIKE": 3, "LOVE": 7, ... } }`

---

#### `DELETE /posts/{post_id}/react`

Remove the authenticated user's reaction.

- **Auth required:** Yes
- **Response `200`:** Updated reaction counts

---

#### `GET /posts/{post_id}/reactions`

List all reactions on a post.

- **Auth required:** No
- **Response `200`:** Paginated list of `{ user, reaction_type }` objects

---

#### `POST /posts/{post_id}/share`

Share a post.

- **Auth required:** Yes
- **Request body:** `{ "content": "Check this out!", "visibility": "public" }` (optional)
- **Response `201`:** Share object with `share_id`

---

#### `DELETE /posts/{post_id}/share/{share_id}`

Remove a share.

- **Auth required:** Yes (must be share owner)
- **Response:** `204 No Content`

---

#### `POST /posts/{post_id}/media`

Upload media to attach to a post.

- **Auth required:** Yes
- **Request:** `multipart/form-data`, field `file`
- **Response `201`:** Media object (see §6.8)

---

### 6.5 Feed

#### `GET /feed`

Get the authenticated user's personalized feed.

- **Auth required:** Yes
- **Query params:** `page` (default 1), `limit` (default 20)
- **Cache strategy:** Cache-first using Redis sorted set (ZSET), scored by post timestamp
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "posts": [ /* array of post objects */ ]
  },
  "error": null,
  "meta": { "total": 87, "page": 1, "limit": 20, "has_next": true },
  "version": "1.0"
}
```

---

### 6.6 Messages

Base path: `/api/v1/messages`

---

#### `GET /messages`

List all conversations (most recent message per conversation partner).

- **Auth required:** Yes
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "partner": { "id": "u_02AY", "username": "janedoe", "avatar_url": "..." },
        "last_message": { "content": "Hey!", "sent_at": "2026-03-13T10:00:00Z" },
        "unread_count": 3
      }
    ]
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `GET /messages/{user_id}`

Get full message history with a specific user.

- **Auth required:** Yes
- **Query params:** `page`, `limit`
- **Response `200`:** Paginated list of message objects

---

#### `POST /messages`

Send a direct message. Also dispatched via Redis pub/sub to the recipient's WebSocket connection.

- **Auth required:** Yes
- **Request body:**

```json
{
  "receiver_id": "u_02AY",
  "content": "Hey! Are you free this weekend?"
}
```

- **Response `201`:**

```json
{
  "success": true,
  "data": {
    "id": "msg_001",
    "sender_id": "u_01HX",
    "receiver_id": "u_02AY",
    "content": "Hey! Are you free this weekend?",
    "is_seen": false,
    "sent_at": "2026-03-13T10:01:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `POST /messages/{message_id}/seen`

Mark a message as seen.

- **Auth required:** Yes (must be the recipient)
- **Response `200`:** `{ "message_id": "msg_001", "seen_at": "2026-03-13T10:02:00Z" }`

---

#### `GET /messages/unread-count`

Get total unread message count for the authenticated user.

- **Auth required:** Yes
- **Response `200`:** `{ "unread_count": 5 }`

---

### 6.7 Notifications

Base path: `/api/v1/notifications`

---

#### `GET /notifications`

List notifications for the authenticated user.

- **Auth required:** Yes
- **Query params:** `page`, `limit`
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "notifications": [
      {
        "id": "notif_001",
        "type": "reaction",
        "actor": { "id": "u_02AY", "username": "janedoe" },
        "entity": { "type": "post", "id": "p_0A1B" },
        "message": "janedoe reacted LOVE to your post.",
        "is_read": false,
        "created_at": "2026-03-13T09:30:00Z"
      }
    ]
  },
  "error": null,
  "meta": { "total": 24, "page": 1, "limit": 20, "has_next": true },
  "version": "1.0"
}
```

Notification `type` values: `like`, `reaction`, `comment`, `share`, `friend_request`, `friend_accept`

---

#### `GET /notifications/unread-count`

Get unread notification count. Cached for **30 seconds**.

- **Auth required:** Yes
- **Response `200`:** `{ "unread_count": 4 }`

---

#### `POST /notifications/{notification_id}/read`

Mark a single notification as read.

- **Auth required:** Yes
- **Response `200`:** `{ "notification_id": "notif_001", "is_read": true }`

---

#### `POST /notifications/read-all`

Mark all notifications as read.

- **Auth required:** Yes
- **Response `200`:** `{ "marked_count": 12 }`

---

### 6.8 Media

Base path: `/api/v1/media`

---

#### `POST /media/upload`

Upload a media file linked to an entity.

- **Auth required:** Yes
- **Query params:** `entity_type` (`post` | `message`), `entity_id`
- **Request:** `multipart/form-data`, field `file`
- **Response `201`:**

```json
{
  "success": true,
  "data": {
    "id": "med_001",
    "entity_type": "post",
    "entity_id": "p_0A1B",
    "url": "https://cdn.example.com/media/med_001.jpg",
    "media_type": "image/jpeg",
    "size_bytes": 204800,
    "width": 1920,
    "height": 1080,
    "created_at": "2026-03-13T09:01:00Z"
  },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

#### `GET /media`

List media for an entity.

- **Auth required:** Yes
- **Query params:** `entity_type`, `entity_id`
- **Response `200`:** List of media objects

---

#### `GET /media/{media_id}`

Get media metadata.

- **Auth required:** Yes
- **Response `200`:** Single media object

---

#### `DELETE /media/{media_id}`

Delete a media file.

- **Auth required:** Yes (must be uploader)
- **Response:** `204 No Content`

---

#### `GET /media/{media_id}/stream`

Stream a media file. Supports HTTP Range requests (`206 Partial Content`). May redirect to an S3 presigned URL.

- **Auth required:** No (URL contains signed token)
- **Response:** `200 OK` or `206 Partial Content` or `302 Found` (S3 redirect)

---

#### `GET /media/{media_id}/presigned-url`

Generate a time-limited presigned URL for direct S3 access.

- **Auth required:** Yes
- **Response `200`:**

```json
{
  "success": true,
  "data": { "url": "https://s3.amazonaws.com/bucket/med_001.jpg?X-Amz-Expires=3600&...", "expires_in": 3600 },
  "error": null,
  "meta": null,
  "version": "1.0"
}
```

---

### 6.9 Search

#### `GET /search/users`

Search for users by username or full name.

- **Auth required:** Yes
- **Query params:** `q` (string, min 2 chars), `limit` (default 20)
- **Response `200`:**

```json
{
  "success": true,
  "data": {
    "users": [
      { "id": "u_02AY", "username": "janedoe", "full_name": "Jane Doe", "avatar_url": "..." }
    ]
  },
  "error": null,
  "meta": { "total": 3, "page": 1, "limit": 20, "has_next": false },
  "version": "1.0"
}
```

---

### 6.10 Health & Metrics

These endpoints are **unauthenticated** and used for infrastructure monitoring.

---

#### `GET /health`

Liveness probe.

```json
{ "status": "ok", "uptime_seconds": 86400 }
```

---

#### `GET /ready`

Readiness probe — checks database and Redis connectivity.

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

Returns `503` with `"status": "degraded"` if any dependency is unhealthy.

---

#### `GET /metrics/simple`

Lightweight metrics summary.

```json
{ "uptime_seconds": 86400, "online_users": 237 }
```

---

#### `GET /metrics`

Prometheus-format text metrics (scrape target for Prometheus server).

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 18423
...
```

---

## 7. Caching Behavior

| Endpoint                             | Cache TTL  | Cache Key Pattern                          | Invalidated By                          |
|--------------------------------------|------------|--------------------------------------------|-----------------------------------------|
| `GET /users/{user_id}`               | 300 s      | `user:profile:{user_id}`                  | `PUT /users/{user_id}`, avatar upload  |
| `GET /posts/{post_id}`               | 120 s      | `post:detail:{post_id}`                   | `PUT`, `DELETE` post, new reaction/comment |
| `GET /feed`                          | Cache-first ZSET | `feed:{user_id}` (sorted set)       | New post by friend, post deleted        |
| `GET /notifications/unread-count`    | 30 s       | `notif:unread:{user_id}`                  | New notification, mark read             |
| User online status (internal)        | 60 s       | `presence:{user_id}`                      | WebSocket connect/disconnect            |

### Cache Invalidation Strategy

- **Write-through:** Profile and post caches are invalidated immediately on write by deleting the Redis key.
- **TTL expiry:** Feed and notification count caches expire naturally; a background task refreshes the feed ZSET on new post events.
- **Pub/Sub:** Cross-instance cache invalidation is coordinated via a dedicated Redis pub/sub channel (`cache:invalidate`).

### Cache-First Feed

The feed uses a Redis sorted set scored by post creation timestamp:

1. On `GET /feed?page=1`, read from ZSET with `ZREVRANGEBYSCORE`.
2. If the set is empty or stale, rebuild from the database and populate the ZSET.
3. New posts from friends are pushed onto the ZSET via a background worker triggered by the post creation event.
