# Naming Conventions

Universal naming rules applied across all databases and languages.

## SQL (SQLite)

| Element | Convention | Example |
|---|---|---|
| Tables | `snake_case`, plural nouns | `users`, `order_items` |
| Columns | `snake_case` | `created_at`, `user_id` |
| Primary keys | `id` (always) | `users.id` |
| Foreign keys | `{singular_table}_id` | `order_items.order_id` |
| Indexes | `idx_{table}_{columns}` | `idx_orders_user_id` |
| Unique constraints | `uniq_{table}_{columns}` | `uniq_users_email` |
| Check constraints | `chk_{table}_{rule}` | `chk_orders_status` |
| Booleans | `is_` or `has_` prefix | `is_active`, `has_verified` |
| Timestamps | `_at` suffix | `created_at`, `deleted_at` |
| Money | `_in_cents` suffix, INTEGER | `price_in_cents` |
| Migrations | `YYYYMMDDHHMMSS_description.sql` | `20260329120000_create_users.sql` |

## Redis Keys

| Element | Convention | Example |
|---|---|---|
| Separator | colon `:` | `app:cache:users:42` |
| Case | all lowercase | `app:session:abc123` |
| Service prefix | first segment | `app:`, `auth:`, `billing:` |
| Entity segment | singular noun | `user`, `order`, `product` |
| Multi-tenant | `t:{tid}:` prefix | `t:7:app:user:42` |

## Neo4j

| Element | Convention | Example |
|---|---|---|
| Node labels | PascalCase singular noun | `:User`, `:OrderItem` |
| Relationship types | UPPER_SNAKE_CASE verb | `:PURCHASED`, `:BELONGS_TO` |
| Properties | camelCase | `userId`, `createdAt` |
| Constraints | `uniq_{label}_{prop}` | `uniq_user_userId` |
| Indexes | `idx_{label}_{prop}` | `idx_user_email` |

## Rust

| Element | Convention | Example |
|---|---|---|
| Structs | PascalCase | `User`, `OrderItem` |
| Fields | snake_case | `external_id`, `created_at` |
| Enums | PascalCase variants | `UserStatus::Active` |
| Functions | snake_case | `find_by_id`, `create_pool` |
| Modules | snake_case | `models.rs`, `db.rs` |
| Constants | SCREAMING_SNAKE_CASE | `MAX_CONNECTIONS` |

## Go

| Element | Convention | Example |
|---|---|---|
| Structs | PascalCase (exported) | `User`, `OrderItem` |
| Fields | PascalCase (exported) | `ExternalID`, `CreatedAt` |
| JSON tags | snake_case | `` `json:"external_id"` `` |
| DB tags | snake_case | `` `db:"external_id"` `` |
| Functions | PascalCase (exported) | `FindByID`, `NewUserRepo` |
| Packages | lowercase, no underscores | `models`, `cache`, `graph` |
| Interfaces | `-er` suffix | `UserFinder`, `CacheWriter` |
| Errors | `Err` prefix | `ErrNotFound`, `ErrCacheMiss` |

## Cross-Database ID Mapping

SQLite `external_id` (UUID) = Neo4j `userId` property = Redis key segment.

Never expose SQLite integer `id` outside the service. Always use UUIDs for external communication and cross-database references.
