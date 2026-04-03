---
name: schema-architect
description: >
  Design and generate production-ready database schemas for SQLite, Redis, and Neo4j
  with type-safe Rust and Go bindings. Generates integrated multi-database architectures
  with migrations, validation, caching layers, and enterprise patterns.
  Use when: user asks to design a database schema, create data models, plan migrations,
  set up Redis caching, design a graph database, generate ORM models in Rust or Go,
  or architect a multi-database system. Triggers on: schema design, data modeling,
  database architecture, migration planning, cache strategy, graph modeling.
---

# Schema Architect

Production-ready database schema design for SQLite + Redis + Neo4j with Rust and Go.

## Workflow

Schema design involves these steps:

1. Gather requirements (stage, databases, language, domain)
2. Select architecture pattern
3. Generate schemas per database
4. Generate language bindings
5. Generate migrations and validation
6. Validate output (run `validate_schema.py`)

## Step 1: Gather Requirements

Determine these before generating anything:

| Question | Options | Default |
|---|---|---|
| **Stage** | `early` (MVP/startup) or `advanced` (scale/enterprise) | `early` |
| **Databases** | Any combination of `sqlite`, `redis`, `neo4j` | All three |
| **Language** | `rust`, `go`, or both | Both |
| **Domain** | The business domain (e-commerce, SaaS, IoT, etc.) | Ask user |

If the user provides a use case without specifying these, infer sensible defaults and confirm.

## Step 2: Select Architecture Pattern

**Early stage** — optimized for speed, simplicity, iteration:

```
SQLite ──── primary store (OLTP, local-first, embedded)
Redis  ──── session cache + rate limiting + pub/sub events
Neo4j  ──── relationship queries only when graph is justified
```

**Advanced stage** — optimized for scale, observability, governance:

```
SQLite ──── edge/embedded nodes, local write-ahead, sync buffer
Redis  ──── distributed cache, streams pipeline, leaderboards
Neo4j  ──── knowledge graph, access control graph, recommendation engine
```

For integrated multi-DB architectures, read `references/integration-patterns.md`.

## Step 3: Generate Schemas

For each selected database, read the corresponding reference and apply its patterns:

- **SQLite**: Read `references/sqlite.md` — normalization, WAL mode, strict typing, indexes
- **Redis**: Read `references/redis.md` — key namespacing, TTL policies, cache-aside pattern
- **Neo4j**: Read `references/neo4j.md` — node labels, relationship types, Cypher constraints

Apply naming conventions from `references/naming-conventions.md` to ALL generated schemas.

### Output per database

| Database | Files Generated |
|---|---|
| SQLite | `schema.sql`, migration files in `migrations/` dir |
| Redis | `redis-schema.toml` (key namespace + TTL config) |
| Neo4j | `constraints.cypher`, `schema.cypher` |

Use templates from `templates/` as starting points — fill in entity-specific content.

## Step 4: Generate Language Bindings

For each selected language, read the corresponding reference:

- **Rust**: Read `references/rust-bindings.md` — sqlx/diesel/sea-orm, redis-rs, neo4rs
- **Go**: Read `references/go-bindings.md` — database/sql/gorm, go-redis, neo4j-go-driver

Generate type-safe model structs with proper derives/tags, connection helpers, and repository patterns.

### Output per language

| Language | Files Generated |
|---|---|
| Rust | `models.rs`, `db.rs` (connection pool), `cache.rs`, `graph.rs` |
| Go | `models.go`, `db.go`, `cache.go`, `graph.go` |

## Step 5: Generate Migrations and Validation

Generate versioned migration files following `references/migration-patterns.md`:

- Timestamped filenames: `YYYYMMDDHHMMSS_description.sql`
- Every migration has an `up` and `down` section
- Include audit trail columns: `created_at`, `updated_at`, `version`
- For advanced stage: add `created_by`, `deleted_at` (soft delete), `tenant_id` (multi-tenancy)

## Step 6: Validate

Run the validation script against all generated files:

```bash
python3 /home/ubuntu/skills/schema-architect/scripts/validate_schema.py <output_directory>
```

The script checks naming conventions, foreign key consistency, index coverage, and migration ordering. Fix any reported issues before delivering.

## Enterprise Patterns by Stage

### Early Stage Patterns

Apply these for MVPs, prototypes, and startups:

| Pattern | Implementation |
|---|---|
| **Single-tenant SQLite** | One DB file per deployment, WAL mode, `STRICT` tables |
| **Session cache** | Redis strings with `session:{user_id}` keys, 24h TTL |
| **Rate limiting** | Redis sorted sets with sliding window per API key |
| **Simple relationships** | SQLite foreign keys first; Neo4j only if graph queries emerge |
| **Soft delete** | `deleted_at` column, never hard-delete user data |
| **Optimistic locking** | `version INTEGER NOT NULL DEFAULT 1` on mutable tables |

### Advanced Stage Patterns

Apply these for production systems at scale:

| Pattern | Implementation |
|---|---|
| **Multi-tenant isolation** | `tenant_id` on every table, row-level security, Redis key prefix `t:{tid}:` |
| **CQRS** | SQLite for writes, Redis for read-through cache, Neo4j for complex queries |
| **Event sourcing** | Redis Streams as event log, SQLite as snapshot store |
| **Distributed cache** | Redis Cluster with consistent hashing, cache-aside + write-through |
| **Graph access control** | Neo4j `(:User)-[:HAS_ROLE]->(:Role)-[:PERMITS]->(:Resource)` |
| **Schema versioning** | Migration table with checksums, rollback scripts, blue-green deploys |
| **Audit trail** | Separate `audit_log` table with `entity_type`, `entity_id`, `action`, `diff_json` |
| **Connection pooling** | Rust: `sqlx::Pool` / Go: `sql.DB` with `SetMaxOpenConns`, Redis pool per service |

## Key Principles

These rules apply to ALL generated schemas regardless of database or stage:

1. **Normalize to 3NF minimum** — denormalize only with measured justification
2. **Every table gets a primary key** — prefer `INTEGER PRIMARY KEY` (SQLite) or UUIDs (distributed)
3. **Every foreign key gets an index** — no exceptions
4. **Timestamps on everything** — `created_at` and `updated_at` with UTC, never local time
5. **Constraints at the DB level** — NOT NULL, CHECK, UNIQUE enforced in schema, not just app code
6. **Redis keys are namespaced** — `{service}:{entity}:{id}:{field}` pattern always
7. **Neo4j relationships are verbs** — `FOLLOWS`, `PURCHASED`, `BELONGS_TO`, never nouns
8. **Migrations are immutable** — never edit a deployed migration, always create a new one
9. **Document everything** — inline SQL comments on non-obvious columns, README per schema dir
