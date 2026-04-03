# Integration Patterns: SQLite + Redis + Neo4j

## Table of Contents

1. Data Flow Architecture
2. Early Stage Integration
3. Advanced Stage Integration
4. Sync Strategies
5. Query Routing

## 1. Data Flow Architecture

Each database has a distinct role. Data flows between them via application code and events.

```
                    ┌─────────────┐
                    │  Application │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │  SQLite   │   │  Redis    │   │  Neo4j    │
     │  (truth)  │   │  (speed)  │   │  (graph)  │
     └──────────┘   └──────────┘   └──────────┘
     Source of       Cache layer    Relationship
     truth for       + sessions     queries +
     all entity      + rate limits  access control
     data            + events       + recommendations
```

Rules:
- SQLite is ALWAYS the source of truth for entity data
- Redis caches SQLite data and handles ephemeral state
- Neo4j stores relationships and graph-queryable properties only
- Cross-DB references use UUIDs (SQLite `external_id` = Neo4j `userId` = Redis key segment)

## 2. Early Stage Integration

Minimal integration — add complexity only when needed.

### Read Path (with cache)

```
Client request
  → Check Redis cache
    → HIT: return cached data
    → MISS: query SQLite → store in Redis (TTL 5min) → return
```

### Write Path

```
Client write
  → Write to SQLite (transaction)
  → Invalidate Redis cache key
  → If graph-relevant: update Neo4j node/relationship
  → Return success
```

### When to Add Neo4j

Add Neo4j only when you have queries that are painful in SQL:
- "Find all users connected to user X within 3 degrees"
- "What products do friends of user X like?"
- "Can user X access resource Y through any role chain?"

If your queries are simple JOINs, SQLite is sufficient. Do not add Neo4j preemptively.

## 3. Advanced Stage Integration

Event-driven integration with eventual consistency.

### Write Path (event-sourced)

```
Client write
  → Write to SQLite (transaction)
  → Publish event to Redis Stream: app:events:{entity_type}
  → Return success (async processing below)

Event consumers (background workers):
  → Consumer 1: Update Redis cache (write-through)
  → Consumer 2: Update Neo4j graph nodes/relationships
  → Consumer 3: Write to audit log
  → Consumer 4: Trigger notifications
```

### Read Path (CQRS)

```
Simple entity lookup:
  → Redis cache → SQLite fallback

Complex relationship query:
  → Neo4j (returns UUIDs) → SQLite (hydrate full entities) → Redis (cache result)

Aggregation/analytics:
  → SQLite (with appropriate indexes)

Real-time leaderboard/ranking:
  → Redis sorted sets (pre-computed)
```

### Consistency Model

| Pair | Consistency | Strategy |
|---|---|---|
| SQLite → Redis | Eventual (seconds) | Cache invalidation on write + TTL |
| SQLite → Neo4j | Eventual (seconds) | Event consumer processes stream |
| Redis → Client | Strong for sessions | Direct read, sliding TTL |

Acceptable staleness: cache data can be up to TTL seconds old. Graph data can be up to consumer lag behind. Session data is always current.

## 4. Sync Strategies

### SQLite → Neo4j Sync

Only sync properties needed for graph queries:

```
SQLite users table:
  id, external_id, email, name, status, bio, avatar_url, preferences_json, ...

Neo4j User node:
  userId (= external_id), email, status
  (only what's needed for MATCH/WHERE in graph queries)
```

Sync trigger: Redis Stream consumer.

```
Event: { action: "update", entity: "user", id: "uuid-123", fields: ["email", "status"] }

Consumer logic:
  if any synced field changed:
    MERGE (u:User {userId: $id}) SET u.email = $email, u.status = $status
```

### Cache Invalidation Patterns

| Pattern | When | Implementation |
|---|---|---|
| **Delete on write** | Default for single records | `DEL app:cache:users:42` |
| **Delete pattern on write** | When list caches exist | `SCAN` + `DEL` matching `app:cache:users:list:*` |
| **Write-through** | When read latency is critical | Update cache in same transaction as DB write |
| **TTL-only** | When slight staleness is OK | No active invalidation, rely on TTL expiry |

## 5. Query Routing

Decision tree for where to run a query:

```
Is it a graph traversal (paths, recommendations, access control)?
  → YES: Neo4j (return UUIDs, hydrate from SQLite if needed)
  → NO: continue

Is it a simple key-value lookup by ID?
  → YES: Redis cache first, SQLite fallback
  → NO: continue

Is it a filtered list with pagination?
  → YES: Check Redis for cached result, else SQLite with indexes
  → NO: continue

Is it an aggregation or report?
  → YES: SQLite directly (indexes + query optimization)
  → NO: continue

Is it real-time ranking or counting?
  → YES: Redis sorted sets or HyperLogLog
  → NO: SQLite as default
```
