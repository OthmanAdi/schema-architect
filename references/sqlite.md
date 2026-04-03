# SQLite Schema Patterns

## Table of Contents

1. Table Creation
2. Type System
3. Indexing Strategy
4. WAL Mode and Performance
5. Constraints and Validation
6. Common Enterprise Tables

## 1. Table Creation

Always use `STRICT` tables (SQLite 3.37+) to enforce type checking:

```sql
CREATE TABLE users (
    id          INTEGER PRIMARY KEY,  -- auto-increment via ROWID
    external_id TEXT    NOT NULL UNIQUE,  -- UUID for API exposure
    email       TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','deleted')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    version     INTEGER NOT NULL DEFAULT 1
) STRICT;
```

Key rules:
- `INTEGER PRIMARY KEY` aliases ROWID — fastest possible lookups
- Use `TEXT` for UUIDs and expose those externally, never raw integer IDs
- Store timestamps as ISO-8601 TEXT in UTC — portable and sortable
- Add `version` column for optimistic locking on mutable tables

## 2. Type System

SQLite STRICT mode supports five types:

| SQLite Type | Use For | Rust Type | Go Type |
|---|---|---|---|
| `INTEGER` | IDs, counts, booleans (0/1), enums as int | `i64` | `int64` |
| `REAL` | Floating point (avoid for money) | `f64` | `float64` |
| `TEXT` | Strings, UUIDs, ISO timestamps, JSON | `String` | `string` |
| `BLOB` | Binary data, encrypted fields | `Vec<u8>` | `[]byte` |
| `ANY` | Avoid — defeats strict typing | — | — |

For money/currency, store as `INTEGER` in smallest unit (cents) to avoid floating point errors.

## 3. Indexing Strategy

```sql
-- Every foreign key gets an index
CREATE INDEX idx_orders_user_id ON orders(user_id);

-- Composite indexes for common query patterns (leftmost prefix rule)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- Partial indexes for filtered queries (SQLite 3.8+)
CREATE INDEX idx_orders_active ON orders(user_id) WHERE status = 'active';

-- Covering indexes to avoid table lookups
CREATE INDEX idx_users_email_name ON users(email, name);

-- Expression indexes for case-insensitive search
CREATE INDEX idx_users_email_lower ON users(lower(email));
```

Rules:
- Index every column used in WHERE, JOIN, or ORDER BY
- Composite index column order matches query filter order
- Use partial indexes for status-filtered queries (saves space)
- Monitor with `EXPLAIN QUERY PLAN` — no full table scans on tables > 1000 rows

## 4. WAL Mode and Performance

Always enable WAL mode for concurrent read/write:

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;       -- safe with WAL
PRAGMA cache_size = -64000;        -- 64MB cache
PRAGMA foreign_keys = ON;          -- enforce FK constraints
PRAGMA auto_vacuum = INCREMENTAL;  -- reclaim space without full vacuum
```

Set these pragmas at connection open, before any queries.

## 5. Constraints and Validation

```sql
-- NOT NULL on everything unless genuinely optional
-- CHECK constraints for enums and ranges
-- UNIQUE constraints for natural keys
-- Foreign keys with explicit ON DELETE behavior

CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity   INTEGER NOT NULL CHECK(quantity > 0),
    unit_price INTEGER NOT NULL CHECK(unit_price >= 0),  -- cents
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;
```

ON DELETE policies:
- `CASCADE` — child rows deleted with parent (order_items when order deleted)
- `RESTRICT` — prevent parent deletion if children exist (products with orders)
- `SET NULL` — set FK to NULL (optional relationships)

## 6. Common Enterprise Tables

### Audit Log

```sql
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY,
    entity_type TEXT    NOT NULL,
    entity_id   INTEGER NOT NULL,
    action      TEXT    NOT NULL CHECK(action IN ('create','update','delete')),
    actor_id    INTEGER,
    diff_json   TEXT,  -- JSON of changed fields
    created_at  TEXT   NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_actor ON audit_log(actor_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);
```

### Migration Tracking

```sql
CREATE TABLE schema_migrations (
    version    TEXT    PRIMARY KEY,  -- timestamp: '20260329120000'
    name       TEXT    NOT NULL,
    checksum   TEXT    NOT NULL,     -- SHA-256 of migration file
    applied_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    rolled_back_at TEXT
) STRICT;
```

### Multi-Tenant Base Pattern

For advanced stage, every business table includes:

```sql
tenant_id INTEGER NOT NULL REFERENCES tenants(id),
-- Add tenant_id as first column in all composite indexes
CREATE INDEX idx_orders_tenant_status ON orders(tenant_id, status);
```
