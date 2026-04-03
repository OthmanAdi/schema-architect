# schema-architect

> Design and generate production-ready database schemas for SQLite, Redis, and Neo4j — with type-safe Rust and Go bindings, migrations, validation, and enterprise patterns. One skill, any stack.

## What This Is

A skill for AI coding agents (Claude Code, Cursor, Codex CLI, and any agentskills-compatible agent) that guides you through designing complete, production-grade database architectures — normalized schemas, cache layers, graph models, versioned migrations, and type-safe language bindings.

**Two modes:**
- **Early stage** — SQLite + Redis + minimal Neo4j. Fast iteration, embedded-first, simple ops.
- **Advanced stage** — Distributed cache, CQRS, event sourcing, multi-tenancy, audit trails.

## Install

```bash
npx skills add OthmanAdi/schema-architect -g
```

Works with Claude Code, Cursor, and any agent supporting the agentskills protocol. Then just describe your domain — the skill activates automatically.

## What's Inside

```
schema-architect/
  SKILL.md                         # Main skill — loaded by the agent
  scripts/
    validate_schema.py             # Validates generated output (naming, FK consistency, indexes)
  references/
    sqlite.md                      # WAL mode, STRICT tables, normalization, indexes
    redis.md                       # Key namespacing, TTL policies, cache-aside pattern
    neo4j.md                       # Labels, relationship types, Cypher constraints
    rust-bindings.md               # sqlx/diesel/sea-orm, redis-rs, neo4rs patterns
    go-bindings.md                 # database/sql/gorm, go-redis, neo4j-go-driver patterns
    naming-conventions.md          # Snake_case rules, plural tables, index naming
    migration-patterns.md          # Versioned migrations, up/down, checksums
    integration-patterns.md        # Multi-DB architecture, CQRS, event sourcing
  templates/
    sqlite-migration.sql.tmpl      # Migration boilerplate with audit columns
    redis-schema.toml.tmpl         # Key namespace + TTL config
    neo4j-constraints.cypher.tmpl  # Constraint and index definitions
    rust-model.rs.tmpl             # sqlx model + repository pattern
    go-model.go.tmpl               # database/sql model + repository pattern
```

## Example

> "Design a schema for a SaaS task management app — SQLite + Redis cache, Rust bindings, early stage."

The skill gathers stage, databases, language, and domain — then generates:
- `schema.sql` with normalized tables, FK indexes, audit columns
- `migrations/20260101000000_initial.sql` with up/down
- `redis-schema.toml` with namespaced keys and TTL policies
- `models.rs`, `db.rs`, `cache.rs` — type-safe, ready to compile
- Validation report via `validate_schema.py`

## Databases Supported

| Database | Use Case |
|---|---|
| **SQLite** | Primary OLTP store, embedded, local-first |
| **Redis** | Session cache, rate limiting, pub/sub, streams |
| **Neo4j** | Relationship queries, access control graphs, recommendations |

## Languages Supported

| Language | ORM / Driver |
|---|---|
| **Rust** | sqlx, diesel, sea-orm + redis-rs + neo4rs |
| **Go** | database/sql, gorm + go-redis + neo4j-go-driver |

## Key Rules Enforced

- 3NF normalization minimum
- Every FK gets an index — no exceptions
- UTC timestamps on every table (`created_at`, `updated_at`)
- Redis keys namespaced: `{service}:{entity}:{id}:{field}`
- Neo4j relationships are verbs (`FOLLOWS`, not `FOLLOWER`)
- Migrations are immutable — never edit deployed, always create new

## Author

Ahmad Othman Ammar Adi — [OthmanAdi](https://github.com/OthmanAdi)
