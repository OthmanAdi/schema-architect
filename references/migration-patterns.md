# Migration Patterns

## Table of Contents

1. File Naming and Structure
2. Migration Content Rules
3. Rollback Strategy
4. Schema Versioning Table
5. Early vs Advanced Stage

## 1. File Naming and Structure

```
migrations/
├── 20260329120000_create_users.sql
├── 20260329120001_create_products.sql
├── 20260329120002_create_orders.sql
├── 20260329120003_create_order_items.sql
├── 20260329120004_create_audit_log.sql
└── 20260329120005_add_tenant_id.sql
```

Timestamp format: `YYYYMMDDHHMMSS` — guarantees ordering across timezones and developers.

## 2. Migration Content Rules

Every migration file has two sections:

```sql
-- +migrate up
CREATE TABLE users (
    id          INTEGER PRIMARY KEY,
    external_id TEXT    NOT NULL UNIQUE,
    email       TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','suspended','deleted')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    version     INTEGER NOT NULL DEFAULT 1
) STRICT;

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);

-- +migrate down
DROP INDEX IF EXISTS idx_users_status;
DROP INDEX IF EXISTS idx_users_email;
DROP TABLE IF EXISTS users;
```

Rules:
- `up` creates or alters; `down` reverses exactly
- One logical change per migration (one table, or one set of related indexes)
- Never edit a migration after it has been applied to any environment
- Include indexes in the same migration as the table they index
- Down migrations drop in reverse order of creation

## 3. Rollback Strategy

Safe rollback patterns:

| Operation | Up | Down |
|---|---|---|
| Create table | `CREATE TABLE` | `DROP TABLE IF EXISTS` |
| Add column | `ALTER TABLE ADD COLUMN` | Not supported in SQLite — use table rebuild |
| Add index | `CREATE INDEX` | `DROP INDEX IF EXISTS` |
| Add constraint | Rebuild table with constraint | Rebuild table without constraint |

SQLite limitation: `ALTER TABLE` cannot drop columns (before 3.35) or add constraints. For these operations, use the table rebuild pattern:

```sql
-- +migrate up (add NOT NULL column with default)
ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT '';

-- +migrate up (complex: add constraint requires rebuild)
CREATE TABLE users_new (...new schema...);
INSERT INTO users_new SELECT ... FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;
-- Recreate all indexes
```

## 4. Schema Versioning Table

Track applied migrations:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    rolled_back_at TEXT
) STRICT;
```

Before applying a migration:
1. Check if version exists in `schema_migrations`
2. If exists and not rolled back, skip
3. If not exists, apply and insert record with SHA-256 checksum of file
4. On rollback, set `rolled_back_at` timestamp (never delete the record)

## 5. Early vs Advanced Stage

### Early Stage Migrations

Keep it simple:
- Sequential numbering is fine
- Manual application via script
- Single developer can manage
- Focus on getting schema right, iterate fast

```bash
# Simple migration runner
for f in migrations/*.sql; do
    sqlite3 app.db < "$f"
done
```

### Advanced Stage Migrations

Production-grade:
- CI/CD pipeline runs migrations automatically
- Checksum verification prevents tampering
- Blue-green deployment: apply migration, verify, switch traffic
- Separate read/write migration phases for zero-downtime:
  1. Add new column (nullable) — deploy
  2. Backfill data — deploy
  3. Add NOT NULL constraint — deploy
  4. Remove old column — deploy (next release)

Neo4j migrations follow the same timestamp pattern but use `.cypher` extension:

```
neo4j-migrations/
├── 20260329120000_create_constraints.cypher
├── 20260329120001_create_indexes.cypher
└── 20260329120002_seed_roles.cypher
```
