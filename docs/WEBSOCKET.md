# Facebook Clone — WebSocket Reference

> **Version:** 1.0
> **Last updated:** 2026-03-13
> **WebSocket Endpoint:** `ws://localhost:8000/api/v1/ws`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Connection Flow](#2-connection-flow)
3. [Client → Server Events](#3-client--server-events)
4. [Server → Client Events (Push)](#4-server--client-events-push)
5. [Multi-Device Support](#5-multi-device-support)
6. [Reconnection Strategy](#6-reconnection-strategy)
7. [Cross-Process Delivery (Redis Pub/Sub)](#7-cross-process-delivery-redis-pubsub)
8. [Error Codes](#8-error-codes)
9. [Code Examples](#9-code-examples)

---

## 1. Overview

### Endpoint

```
ws://localhost:8000/api/v1/ws?token=<jwt_access_token>
```

For TLS environments:

```
wss://your-domain.com/api/v1/ws?token=<jwt_access_token>
```

### Authentication

Authentication is performed via a JWT access token passed as a **query parameter** at connection time. There is no `Authorization` header mechanism for the WebSocket handshake (browsers do not support custom headers during the WS upgrade).

| Parameter | Required | Description                             |
|-----------|----------|-----------------------------------------|
| `token`   | Yes      | A valid JWT access token (15-min TTL)  |

If the token is missing, invalid, expired, or blacklisted, the server closes the connection with code **4001**.

### Message Format

All messages are JSON objects with a mandatory `type` field:

```json
{
  "type": "event.name",
  "payload": { }
}
```

| Field     | Type     | Description                                      |
|-----------|----------|--------------------------------------------------|
| `type`    | `string` | Dot-separated event name (e.g., `chat.send`)    |
| `payload` | `object` | Event-specific data (may be empty `{}`)         |

### Connection Lifecycle

```
OPEN  → Token validated → User registered in ConnectionManager
                        → Presence broadcast to friends
                        → Subscribe to Redis channel user:{user_id}

ACTIVE → Bidirectional event exchange

CLOSE → User removed from ConnectionManager
      → Presence "offline" broadcast to friends (if last active connection)
```

---

## 2. Connection Flow

```
  Client                        API Server                       Redis
    │                               │                              │
    │  WS Upgrade Request           │                              │
    │  GET /api/v1/ws?token=xxx     │                              │
    │──────────────────────────────▶│                              │
    │                               │ Validate JWT signature       │
    │                               │ Check token expiry           │
    │                               │ Check token not blacklisted  │
    │                               │                              │
    │                               │──── HGET blacklist:token ───▶│
    │                               │◀─── nil (not blacklisted) ───│
    │                               │                              │
    │                               │ Extract user_id from sub     │
    │                               │ Register connection in       │
    │                               │ ConnectionManager            │
    │                               │ connections[user_id].add(ws) │
    │                               │                              │
    │  101 Switching Protocols      │                              │
    │◀──────────────────────────────│                              │
    │                               │                              │
    │                               │──── SET presence:user_id ───▶│
    │                               │     EX 60                    │
    │                               │                              │
    │                               │ Look up friend list          │
    │                               │ Publish user.online to each  │
    │                               │ friend's channel             │
    │                               │──── PUBLISH user:{friend} ──▶│
    │                               │     { type: user.online }    │
    │                               │                              │
    │                               │ Subscribe to own channel     │
    │                               │──── SUBSCRIBE user:{me} ────▶│
    │                               │                              │
    │  ◀── server push events ──────│◀─── messages from channel ───│
    │                               │                              │
    │  (connection stays open)      │                              │
    │  …                            │                              │
    │                               │                              │
    │  [Client disconnects]         │                              │
    │──────────────────── CLOSE ───▶│                              │
    │                               │ Remove from ConnectionManager│
    │                               │ DEL presence:user_id (if     │
    │                               │   last connection for user)  │
    │                               │──── PUBLISH user:{friend} ──▶│
    │                               │     { type: user.offline }   │
```

### Token Validation Steps (Detail)

1. **Format check** — ensure the token is a well-formed JWT (three Base64URL segments).
2. **Signature verification** — verify against the server's secret/public key.
3. **Expiry check** — reject if `exp` claim is in the past.
4. **Blacklist check** — look up `blacklist:{token_jti}` in Redis; reject if found.
5. **User existence** — confirm the `sub` (user_id) exists in the database.

---

## 3. Client → Server Events

### `ping`

Keepalive heartbeat. The server responds immediately with a `pong`. Clients should send a ping every **30 seconds** when the connection is idle to prevent proxy timeouts.

- **Payload:** `{}` (empty)
- **Server response:** `{ "type": "pong", "payload": {} }`

**Example:**

```json
// Client sends:
{ "type": "ping", "payload": {} }

// Server responds:
{ "type": "pong", "payload": {} }
```

---

### `chat.send`

Send a direct message to another user. The server persists the message to the database and delivers it to the recipient via Redis pub/sub.

- **Auth:** Must be connected (token validated at connection time)

**Payload schema:**

| Field         | Type     | Required | Description                              |
|---------------|----------|----------|------------------------------------------|
| `receiver_id` | `string` | Yes      | The recipient user's ID                 |
| `content`     | `string` | Yes      | Message text (max 2000 characters)      |
| `client_id`   | `string` | No       | Client-generated idempotency key        |

**Example:**

```json
// Client sends:
{
  "type": "chat.send",
  "payload": {
    "receiver_id": "u_02AY",
    "content": "Hey! Are you free this weekend?",
    "client_id": "local-uuid-1234"
  }
}

// Server acknowledges (sent back to sender only):
{
  "type": "chat.sent",
  "payload": {
    "message_id": "msg_001",
    "client_id": "local-uuid-1234",
    "sent_at": "2026-03-13T10:01:00Z"
  }
}
```

The recipient receives a `chat.message` push event (see §4).

---

### `chat.typing`

Broadcast a typing indicator to a conversation partner.

**Payload schema:**

| Field         | Type      | Required | Description                          |
|---------------|-----------|----------|--------------------------------------|
| `receiver_id` | `string`  | Yes      | The user who should see the indicator|
| `is_typing`   | `boolean` | Yes      | `true` = started typing, `false` = stopped |

**Example:**

```json
// Client sends:
{
  "type": "chat.typing",
  "payload": {
    "receiver_id": "u_02AY",
    "is_typing": true
  }
}
```

No server acknowledgement is sent to the sender. The recipient receives a `chat.typing` push event.

---

### `chat.seen`

Notify the sender that a message has been read.

**Payload schema:**

| Field         | Type     | Required | Description                              |
|---------------|----------|----------|------------------------------------------|
| `message_id`  | `string` | Yes      | The ID of the message being acknowledged |
| `sender_id`   | `string` | Yes      | The original sender's user ID            |

**Example:**

```json
// Client sends:
{
  "type": "chat.seen",
  "payload": {
    "message_id": "msg_001",
    "sender_id": "u_02AY"
  }
}
```

The original sender receives a `chat.seen` push event. The server also updates the message's `is_seen` flag in the database.

---

## 4. Server → Client Events (Push)

These events are sent by the server without a client request. Clients must register handlers for all events they care about.

---

### `chat.message`

Delivered when another user sends the authenticated user a direct message.

**Triggered by:** Recipient sends `chat.send`, or `POST /api/v1/messages` is called.

**Payload:**

```json
{
  "type": "chat.message",
  "payload": {
    "message_id": "msg_001",
    "sender": {
      "id": "u_02AY",
      "username": "janedoe",
      "avatar_url": "https://cdn.example.com/avatars/janedoe.jpg"
    },
    "content": "Hey! Are you free this weekend?",
    "sent_at": "2026-03-13T10:01:00Z",
    "is_seen": false
  }
}
```

---

### `chat.typing`

Typing indicator from a conversation partner.

**Triggered by:** Partner sends `chat.typing` event.

**Payload:**

```json
{
  "type": "chat.typing",
  "payload": {
    "sender_id": "u_02AY",
    "is_typing": true
  }
}
```

Clients should display the typing indicator for **3 seconds** after receiving `is_typing: true`. An explicit `is_typing: false` event or the 3-second timeout (whichever comes first) hides the indicator.

---

### `chat.seen`

Read receipt — the recipient has seen a message.

**Triggered by:** Recipient sends `chat.seen` event.

**Payload:**

```json
{
  "type": "chat.seen",
  "payload": {
    "message_id": "msg_001",
    "seen_by": "u_02AY",
    "seen_at": "2026-03-13T10:02:30Z"
  }
}
```

---

### `user.online`

A friend has connected to the WebSocket server.

**Triggered by:** A friend establishes a new WebSocket connection.

**Payload:**

```json
{
  "type": "user.online",
  "payload": {
    "user_id": "u_02AY",
    "username": "janedoe",
    "online_at": "2026-03-13T10:00:00Z"
  }
}
```

---

### `user.offline`

A friend has disconnected (all their connections closed).

**Triggered by:** Last WebSocket connection for a friend closes.

**Payload:**

```json
{
  "type": "user.offline",
  "payload": {
    "user_id": "u_02AY",
    "last_seen_at": "2026-03-13T10:45:00Z"
  }
}
```

---

### `notification.new`

A new notification has been created for the authenticated user.

**Triggered by:** Any social interaction targeting the user: like, reaction, comment, share, friend request received, friend request accepted.

**Payload:**

```json
{
  "type": "notification.new",
  "payload": {
    "notification_id": "notif_002",
    "notification_type": "reaction",
    "actor": {
      "id": "u_03BZ",
      "username": "bobsmith",
      "avatar_url": "https://cdn.example.com/avatars/bobsmith.jpg"
    },
    "entity": {
      "type": "post",
      "id": "p_0A1B",
      "preview": "Hello world! 🌍"
    },
    "message": "bobsmith reacted HAHA to your post.",
    "created_at": "2026-03-13T10:10:00Z"
  }
}
```

**`notification_type` values:**

| Value            | Description                              |
|------------------|------------------------------------------|
| `like`           | Someone liked your post                 |
| `reaction`       | Someone reacted to your post            |
| `comment`        | Someone commented on your post          |
| `share`          | Someone shared your post                |
| `friend_request` | Someone sent you a friend request       |
| `friend_accept`  | Someone accepted your friend request    |

---

## 5. Multi-Device Support

The `ConnectionManager` maintains a **per-user set of active connections**, allowing the same user to be connected from multiple browser tabs or devices simultaneously.

### Internal Structure

```python
# Pseudocode — ConnectionManager internal state
connections: dict[str, set[WebSocket]] = {
    "u_01HX": { ws_tab1, ws_mobile },
    "u_02AY": { ws_laptop },
}
```

### Broadcast to All Devices

When the server needs to push an event to a user, it iterates over **all active connections** for that `user_id` and sends the message to each:

```python
async def send_to_user(user_id: str, event: dict):
    for ws in connections.get(user_id, set()):
        await ws.send_json(event)
```

### Online/Offline Semantics

- A user is considered **online** if `connections[user_id]` is non-empty.
- The `user.online` broadcast is sent to friends only when the **first** connection for a user is established.
- The `user.offline` broadcast is sent to friends only when the **last** connection for a user is closed.
- Presence is also tracked in Redis (`SET presence:{user_id} 1 EX 60`) and refreshed by a periodic keepalive job.

### Deduplication

Incoming `chat.seen` and `chat.typing` events are idempotent — duplicate delivery across multiple server instances is handled by the receiver checking the database state before broadcasting.

---

## 6. Reconnection Strategy

Network interruptions are expected. Clients must implement automatic reconnection with exponential backoff to avoid thundering-herd effects on the server.

### Recommended Algorithm

```
attempt = 0
base_delay = 1000ms    // 1 second
max_delay  = 30000ms   // 30 seconds
jitter_factor = 0.3    // ±30% randomness

on_disconnect():
    attempt += 1
    delay = min(base_delay * 2^attempt, max_delay)
    jitter = delay * jitter_factor * (random() * 2 - 1)
    wait(delay + jitter)
    reconnect()
```

**Backoff schedule (without jitter):**

| Attempt | Delay  |
|---------|--------|
| 1       | 2 s    |
| 2       | 4 s    |
| 3       | 8 s    |
| 4       | 16 s   |
| 5+      | 30 s   |

### Detecting Disconnection

1. **Browser `close` event** — `ws.onclose` fires with a close code.
2. **Ping timeout** — if the server does not respond to a `ping` within **10 seconds**, assume the connection is dead and close/reconnect.
3. **Network change events** — listen for `online`/`offline` browser events and `visibilitychange` to trigger reconnection proactively.

```javascript
// Monitor ping round-trip
let pingTimer = null
let pongReceived = false

function startPing(ws) {
  pingTimer = setInterval(() => {
    pongReceived = false
    ws.send(JSON.stringify({ type: 'ping', payload: {} }))
    setTimeout(() => {
      if (!pongReceived) {
        ws.close()  // triggers reconnect
      }
    }, 10_000)
  }, 30_000)
}
```

### State Recovery After Reconnect

After a successful reconnect, the client should re-fetch any state it may have missed while disconnected:

1. **Unread messages** — `GET /api/v1/messages/unread-count`, then fetch conversations with new messages.
2. **Unread notifications** — `GET /api/v1/notifications/unread-count`, then `GET /api/v1/notifications` if count > 0.
3. **Online presence** — `GET /api/v1/users/online` to refresh the online status of friends.

---

## 7. Cross-Process Delivery (Redis Pub/Sub)

In production, multiple API server instances run behind a load balancer. A WebSocket connection is pinned to one instance, but messages may originate on a different instance. Redis pub/sub bridges this gap.

### Architecture

```
  Server Instance A                 Server Instance B
  ┌─────────────────┐               ┌─────────────────┐
  │  User u_01HX    │               │  User u_02AY    │
  │  (connected)    │               │  (connected)    │
  └────────┬────────┘               └────────┬────────┘
           │                                 │
           │ chat.send to u_02AY             │
           │                                 │
           ▼                                 │
  ┌─────────────────┐                        │
  │  PUBLISH        │                        │
  │  user:u_02AY    │                        │
  │  {chat.message} │                        │
  └────────┬────────┘                        │
           │                                 │
           ▼                                 │
  ┌──────────────────────────────────────────┤
  │               Redis                      │
  │  Channel: user:u_02AY                    │
  └──────────────────────┬───────────────────┘
                         │
                         │ SUBSCRIBE user:u_02AY
                         ▼
                ┌─────────────────┐
                │  Server B       │
                │  receives msg   │
                │  forwards to    │
                │  u_02AY's ws    │
                └─────────────────┘
```

### Channel Naming

| Channel Pattern       | Purpose                                      |
|-----------------------|----------------------------------------------|
| `user:{user_id}`      | Direct delivery to a specific user          |
| `broadcast:all`       | System-wide broadcasts (maintenance alerts) |

### Pattern Subscribe

Each server instance subscribes to **all user channels** using a pattern subscription at startup:

```python
await redis_pubsub.psubscribe("user:*")
```

On receiving a message, the instance checks its local `ConnectionManager` for matching user connections and delivers the event if found.

### Message Envelope (Internal)

Messages published to Redis include routing metadata:

```json
{
  "target_user_id": "u_02AY",
  "origin_server": "server-a-hostname",
  "event": {
    "type": "chat.message",
    "payload": { ... }
  }
}
```

The receiving server ignores the message if `target_user_id` is not in its local `ConnectionManager`, ensuring no duplicate delivery.

---

## 8. Error Codes

### WebSocket Close Codes

| Code   | Name                  | Cause                                                    | Client Action                          |
|--------|-----------------------|----------------------------------------------------------|----------------------------------------|
| `1000` | Normal closure        | Server or client closed the connection cleanly          | No reconnect needed (unless desired)  |
| `1001` | Going away            | Server is shutting down                                  | Reconnect with backoff                |
| `1006` | Abnormal closure      | Network-level drop (no close frame received)            | Reconnect with backoff                |
| `4001` | Unauthorized          | Token missing, malformed, expired, or blacklisted        | Re-authenticate, then reconnect       |
| `4003` | Forbidden             | User account suspended or banned                         | Show error to user; do not reconnect  |

### JSON Error Events

In addition to close codes, the server may send an error event before closing:

```json
{
  "type": "error",
  "payload": {
    "code": "token_expired",
    "message": "Your session has expired. Please log in again.",
    "close_code": 4001
  }
}
```

**`code` values in error events:**

| Code               | Description                                               |
|--------------------|-----------------------------------------------------------|
| `token_expired`    | JWT access token has passed its expiry time              |
| `token_invalid`    | JWT signature verification failed                        |
| `token_revoked`    | Token is on the blacklist (post-logout)                  |
| `rate_limited`     | Too many connections from this IP                        |
| `server_error`     | Unexpected server-side exception                         |
| `invalid_message`  | Received message is not valid JSON or missing `type`     |
| `unknown_event`    | `type` field does not match any known event              |

---

## 9. Code Examples

### Full JavaScript Client

The following example demonstrates a production-quality WebSocket client with authentication, event handling, ping/keepalive, and exponential backoff reconnection.

```javascript
/**
 * FacebookCloneWebSocketClient
 * Manages a persistent, auto-reconnecting WebSocket connection.
 */
class FacebookCloneWebSocketClient {
  constructor({ getAccessToken, onMessage, onPresenceChange, onNotification }) {
    this.getAccessToken = getAccessToken   // async fn → string token
    this.onMessage = onMessage             // handler for chat.message
    this.onPresenceChange = onPresenceChange  // handler for user.online/offline
    this.onNotification = onNotification   // handler for notification.new

    this.ws = null
    this.attempt = 0
    this.maxDelay = 30_000
    this.baseDelay = 1_000
    this.pingInterval = null
    this.pingTimeout = null
    this.shouldReconnect = true
    this.messageHandlers = {}

    // Register internal handlers
    this._registerHandlers()
  }

  // ─── Connection Management ──────────────────────────────────────────────

  async connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    const token = await this.getAccessToken()
    const url = `ws://localhost:8000/api/v1/ws?token=${token}`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      console.log('[WS] Connected')
      this.attempt = 0
      this._startPing()
    }

    this.ws.onmessage = (event) => {
      let msg
      try {
        msg = JSON.parse(event.data)
      } catch {
        console.error('[WS] Received non-JSON message', event.data)
        return
      }
      this._dispatch(msg)
    }

    this.ws.onclose = (event) => {
      console.log(`[WS] Closed — code: ${event.code}`)
      this._stopPing()

      // 4001 = auth failure; don't reconnect blindly — refresh token first
      if (event.code === 4001) {
        this._handleAuthError()
        return
      }

      // 4003 = banned; do not reconnect
      if (event.code === 4003) {
        console.error('[WS] Connection forbidden — not reconnecting')
        return
      }

      if (this.shouldReconnect) {
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = (err) => {
      console.error('[WS] Error:', err)
      // onclose will fire immediately after; let it handle reconnect
    }
  }

  disconnect() {
    this.shouldReconnect = false
    this._stopPing()
    this.ws?.close(1000, 'Client disconnected')
  }

  // ─── Send Helpers ────────────────────────────────────────────────────────

  sendMessage(receiverId, content, clientId = crypto.randomUUID()) {
    this._send('chat.send', { receiver_id: receiverId, content, client_id: clientId })
    return clientId
  }

  sendTyping(receiverId, isTyping) {
    this._send('chat.typing', { receiver_id: receiverId, is_typing: isTyping })
  }

  markSeen(messageId, senderId) {
    this._send('chat.seen', { message_id: messageId, sender_id: senderId })
  }

  // ─── Internal ────────────────────────────────────────────────────────────

  _send(type, payload = {}) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Cannot send — socket not open')
      return
    }
    this.ws.send(JSON.stringify({ type, payload }))
  }

  _dispatch(msg) {
    const handler = this.messageHandlers[msg.type]
    if (handler) {
      handler(msg.payload)
    } else {
      console.debug('[WS] Unhandled event type:', msg.type)
    }
  }

  _registerHandlers() {
    this.messageHandlers = {
      'pong': () => {
        // Pong received — clear the pending timeout
        clearTimeout(this.pingTimeout)
        this.pingTimeout = null
      },

      'chat.message': (payload) => {
        this.onMessage?.(payload)
      },

      'chat.typing': (payload) => {
        // Bubble up to UI layer
        this.onMessage?.({ _meta: 'typing', ...payload })
      },

      'chat.seen': (payload) => {
        this.onMessage?.({ _meta: 'seen', ...payload })
      },

      'chat.sent': (payload) => {
        // Delivery acknowledgement for our own sent message
        console.debug('[WS] Message delivered:', payload.message_id)
      },

      'user.online': (payload) => {
        this.onPresenceChange?.({ ...payload, is_online: true })
      },

      'user.offline': (payload) => {
        this.onPresenceChange?.({ ...payload, is_online: false })
      },

      'notification.new': (payload) => {
        this.onNotification?.(payload)
      },

      'error': (payload) => {
        console.error('[WS] Server error event:', payload)
      }
    }
  }

  // ─── Ping / Keepalive ────────────────────────────────────────────────────

  _startPing() {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState !== WebSocket.OPEN) return

      this._send('ping', {})

      // If no pong arrives within 10s, forcibly close (triggers reconnect)
      this.pingTimeout = setTimeout(() => {
        console.warn('[WS] Ping timeout — closing stale connection')
        this.ws.close()
      }, 10_000)
    }, 30_000)
  }

  _stopPing() {
    clearInterval(this.pingInterval)
    clearTimeout(this.pingTimeout)
    this.pingInterval = null
    this.pingTimeout = null
  }

  // ─── Reconnection ────────────────────────────────────────────────────────

  _scheduleReconnect() {
    this.attempt += 1
    const delay = Math.min(this.baseDelay * Math.pow(2, this.attempt), this.maxDelay)
    const jitter = delay * 0.3 * (Math.random() * 2 - 1)
    const effectiveDelay = Math.round(delay + jitter)

    console.log(`[WS] Reconnecting in ${effectiveDelay}ms (attempt ${this.attempt})`)
    setTimeout(() => this.connect(), effectiveDelay)
  }

  async _handleAuthError() {
    console.warn('[WS] Auth error — attempting token refresh before reconnect')
    try {
      // Assumes your auth service can refresh the token externally
      await this.getAccessToken(/* forceRefresh = */ true)
      this._scheduleReconnect()
    } catch {
      console.error('[WS] Token refresh failed — user must re-login')
      // Redirect to login or dispatch a global logout event
      window.dispatchEvent(new CustomEvent('auth:session-expired'))
    }
  }

  // ─── State Recovery ──────────────────────────────────────────────────────

  async recoverState() {
    // Call after a successful reconnect to sync missed data
    const [unreadMessages, unreadNotifs, onlineUsers] = await Promise.all([
      fetch('/api/v1/messages/unread-count', { headers: this._authHeaders() }).then(r => r.json()),
      fetch('/api/v1/notifications/unread-count', { headers: this._authHeaders() }).then(r => r.json()),
      fetch('/api/v1/users/online', { headers: this._authHeaders() }).then(r => r.json()),
    ])

    return {
      unreadMessages: unreadMessages.data?.unread_count ?? 0,
      unreadNotifications: unreadNotifs.data?.unread_count ?? 0,
      onlineUserIds: onlineUsers.data?.online_user_ids ?? [],
    }
  }

  _authHeaders() {
    const token = this.getAccessToken()  // sync if cached
    return { 'Authorization': `Bearer ${token}` }
  }
}

// ─── Usage ───────────────────────────────────────────────────────────────────

const wsClient = new FacebookCloneWebSocketClient({
  getAccessToken: async (forceRefresh = false) => {
    if (forceRefresh) {
      const res = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: localStorage.getItem('refresh_token') }),
      })
      const { data } = await res.json()
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      return data.access_token
    }
    return localStorage.getItem('access_token')
  },

  onMessage: (payload) => {
    if (payload._meta === 'typing') {
      // show typing indicator in UI
      showTypingIndicator(payload.sender_id, payload.is_typing)
    } else if (payload._meta === 'seen') {
      // update message read receipt in UI
      markMessageAsSeen(payload.message_id, payload.seen_by)
    } else {
      // append new message to conversation
      appendMessage(payload)
    }
  },

  onPresenceChange: ({ user_id, is_online }) => {
    updateFriendPresence(user_id, is_online)
  },

  onNotification: (notification) => {
    showNotificationBadge(notification)
  },
})

// Connect on page load
wsClient.connect()

// Recover state after regaining network
window.addEventListener('online', async () => {
  await wsClient.connect()
  const state = await wsClient.recoverState()
  syncAppState(state)
})

// Sending a message
document.getElementById('send-btn').addEventListener('click', () => {
  const receiverId = getCurrentConversationUserId()
  const content = document.getElementById('message-input').value.trim()
  if (content) {
    wsClient.sendMessage(receiverId, content)
  }
})

// Typing indicators (debounced)
let typingTimer = null
document.getElementById('message-input').addEventListener('input', () => {
  const receiverId = getCurrentConversationUserId()
  wsClient.sendTyping(receiverId, true)
  clearTimeout(typingTimer)
  typingTimer = setTimeout(() => wsClient.sendTyping(receiverId, false), 2_000)
})
```

---

### Quick-Start Snippet

Minimal connection for testing purposes:

```javascript
const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?token=${token}`)

ws.onopen = () => {
  console.log('Connected')
  ws.send(JSON.stringify({ type: 'ping', payload: {} }))
}

ws.onmessage = ({ data }) => {
  const { type, payload } = JSON.parse(data)
  console.log('Event:', type, payload)
}

ws.onclose = ({ code }) => console.log('Closed with code:', code)
ws.onerror = (err) => console.error('Error:', err)
```
