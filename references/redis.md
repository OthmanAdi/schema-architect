# Redis Schema Patterns (Caching Layer)

## Table of Contents

1. Key Naming Convention
2. Cache-Aside Pattern
3. Session Management
4. Rate Limiting
5. Event Streaming
6. TTL Policies
7. Configuration Template

## 1. Key Naming Convention

All Redis keys follow this namespace pattern:

```
{service}:{entity}:{id}:{field}
```

Examples:
```
app:user:42:profile          → JSON hash of user profile
app:session:abc123           → session data with TTL
app:cache:products:list:p1   → cached product list page 1
app:ratelimit:api:10.0.0.1  → sorted set for sliding window
app:lock:order:99            → distributed lock
```

Multi-tenant prefix:
```
t:{tenant_id}:{service}:{entity}:{id}
t:7:app:user:42:profile
```

Rules:
- Colons `:` as separators, never dots or slashes
- Lowercase everything
- Service name first for cluster routing with hash tags
- Keep keys under 512 bytes (shorter is faster)

## 2. Cache-Aside Pattern

The primary caching strategy for SQLite data:

```
READ:  App → Redis GET → hit? return : SQLite SELECT → Redis SET with TTL → return
WRITE: App → SQLite UPDATE → Redis DEL (invalidate) → return
```

Key design for cache-aside:
```
app:cache:{table}:{id}           → single record cache
app:cache:{table}:list:{hash}    → query result cache (hash of query params)
app:cache:{table}:count          → count cache for pagination
```

Invalidation rules:
- On single record update: delete `app:cache:{table}:{id}`
- On any write to table: delete `app:cache:{table}:list:*` (use SCAN, never KEYS)
- On schema migration: flush `app:cache:*` namespace

## 3. Session Management

```
app:session:{session_id} → HASH {
    user_id:    "42"
    tenant_id:  "7"
    roles:      '["admin","editor"]'
    ip:         "10.0.0.1"
    created_at: "2026-03-29T12:00:00Z"
}
TTL: 86400 (24 hours)
```

Sliding expiration: reset TTL on each access with `EXPIRE`.

Session index for admin (find all sessions for a user):
```
app:user:{user_id}:sessions → SET of session_ids
```

## 4. Rate Limiting

Sliding window with sorted sets:

```
Key:    app:ratelimit:{scope}:{identifier}
Score:  Unix timestamp (microseconds)
Member: Unique request ID

ZADD    app:ratelimit:api:10.0.0.1 {now_us} {request_id}
ZREMRANGEBYSCORE app:ratelimit:api:10.0.0.1 0 {now_us - window_us}
ZCARD   app:ratelimit:api:10.0.0.1
EXPIRE  app:ratelimit:api:10.0.0.1 {window_seconds}
```

If ZCARD > limit, reject request. Window and limit configurable per scope.

## 5. Event Streaming

Redis Streams for event sourcing alongside SQLite snapshots:

```
Stream: app:events:{entity_type}
Entry:  { action: "create", entity_id: "42", data: "{json}", actor: "user:7" }

XADD app:events:orders * action create entity_id 42 data '{"total":9900}'
XREAD COUNT 10 BLOCK 5000 STREAMS app:events:orders $
```

Consumer groups for reliable processing:
```
XGROUP CREATE app:events:orders workers $ MKSTREAM
XREADGROUP GROUP workers worker-1 COUNT 10 BLOCK 5000 STREAMS app:events:orders >
XACK app:events:orders workers {message_id}
```

Use streams for: audit events, cache invalidation signals, cross-service notifications.

## 6. TTL Policies

| Key Pattern | TTL | Rationale |
|---|---|---|
| `app:cache:{table}:{id}` | 300s (5 min) | Single record — short, frequent invalidation |
| `app:cache:{table}:list:*` | 60s (1 min) | List queries — stale quickly on writes |
| `app:session:*` | 86400s (24h) | Session — sliding expiration on access |
| `app:ratelimit:*` | Equal to window | Rate limit — auto-cleanup |
| `app:lock:*` | 30s | Distributed lock — prevent deadlocks |
| `app:events:*` | No TTL | Streams — use XTRIM MAXLEN for retention |

Rules:
- EVERY cache key MUST have a TTL — no immortal cache keys
- Sessions use sliding TTL (reset on access)
- Locks use short TTL as safety net against crashes
- Streams use MAXLEN trim, not TTL

## 7. Configuration Template

The `redis-schema.toml` file documents all key namespaces:

```toml
[service]
name = "app"
version = "1.0.0"

[namespaces.cache]
pattern = "{service}:cache:{table}:{id}"
ttl_seconds = 300
description = "Single-record cache-aside for SQLite tables"

[namespaces.session]
pattern = "{service}:session:{session_id}"
ttl_seconds = 86400
sliding = true
description = "User session data"

[namespaces.ratelimit]
pattern = "{service}:ratelimit:{scope}:{identifier}"
ttl_seconds = 60
description = "Sliding window rate limiter"

[namespaces.events]
pattern = "{service}:events:{entity_type}"
maxlen = 10000
description = "Event stream for entity changes"

[namespaces.lock]
pattern = "{service}:lock:{resource}:{id}"
ttl_seconds = 30
description = "Distributed advisory locks"
```
