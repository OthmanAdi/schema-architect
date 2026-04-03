# Rust Database Bindings

## Table of Contents

1. SQLite with sqlx
2. Redis with redis-rs
3. Neo4j with neo4rs
4. Model Patterns
5. Error Handling
6. Connection Management

## 1. SQLite with sqlx

Preferred: `sqlx` (async, compile-time checked queries, no DSL).

```toml
# Cargo.toml
[dependencies]
sqlx = { version = "0.8", features = ["runtime-tokio", "sqlite"] }
tokio = { version = "1", features = ["full"] }
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
serde = { version = "1", features = ["derive"] }
```

Model struct:

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct User {
    pub id: i64,
    pub external_id: String,
    pub email: String,
    pub name: String,
    pub status: String,
    pub created_at: String,
    pub updated_at: String,
    pub version: i64,
}

impl User {
    pub fn external_uuid(&self) -> Uuid {
        Uuid::parse_str(&self.external_id).expect("valid uuid in DB")
    }
}
```

Repository pattern:

```rust
use sqlx::SqlitePool;

pub struct UserRepo {
    pool: SqlitePool,
}

impl UserRepo {
    pub fn new(pool: SqlitePool) -> Self {
        Self { pool }
    }

    pub async fn find_by_id(&self, id: i64) -> sqlx::Result<Option<User>> {
        sqlx::query_as::<_, User>("SELECT * FROM users WHERE id = ?")
            .bind(id)
            .fetch_optional(&self.pool)
            .await
    }

    pub async fn create(&self, email: &str, name: &str) -> sqlx::Result<i64> {
        let external_id = Uuid::new_v4().to_string();
        let result = sqlx::query(
            "INSERT INTO users (external_id, email, name) VALUES (?, ?, ?)"
        )
            .bind(&external_id)
            .bind(email)
            .bind(name)
            .execute(&self.pool)
            .await?;
        Ok(result.last_insert_rowid())
    }

    pub async fn update_optimistic(&self, user: &User) -> sqlx::Result<bool> {
        let result = sqlx::query(
            "UPDATE users SET email = ?, name = ?, version = version + 1,
             updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
             WHERE id = ? AND version = ?"
        )
            .bind(&user.email)
            .bind(&user.name)
            .bind(user.id)
            .bind(user.version)
            .execute(&self.pool)
            .await?;
        Ok(result.rows_affected() > 0)
    }
}
```

Connection pool:

```rust
use sqlx::sqlite::{SqliteConnectOptions, SqlitePoolOptions};

pub async fn create_pool(db_path: &str) -> sqlx::Result<SqlitePool> {
    let options = SqliteConnectOptions::new()
        .filename(db_path)
        .create_if_missing(true)
        .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal)
        .busy_timeout(std::time::Duration::from_secs(5))
        .foreign_keys(true);

    let pool = SqlitePoolOptions::new()
        .max_connections(5)
        .connect_with(options)
        .await?;

    // Run pragmas
    sqlx::query("PRAGMA synchronous = NORMAL").execute(&pool).await?;
    sqlx::query("PRAGMA cache_size = -64000").execute(&pool).await?;

    Ok(pool)
}
```

## 2. Redis with redis-rs

```toml
[dependencies]
redis = { version = "0.27", features = ["tokio-comp", "connection-manager"] }
```

Cache layer:

```rust
use redis::AsyncCommands;

pub struct CacheLayer {
    conn: redis::aio::ConnectionManager,
    prefix: String,
}

impl CacheLayer {
    pub async fn new(redis_url: &str, service: &str) -> redis::RedisResult<Self> {
        let client = redis::Client::open(redis_url)?;
        let conn = redis::aio::ConnectionManager::new(client).await?;
        Ok(Self { conn, prefix: service.to_string() })
    }

    fn key(&self, entity: &str, id: &str) -> String {
        format!("{}:cache:{}:{}", self.prefix, entity, id)
    }

    pub async fn get_cached<T: serde::de::DeserializeOwned>(
        &mut self, entity: &str, id: &str,
    ) -> redis::RedisResult<Option<T>> {
        let key = self.key(entity, id);
        let data: Option<String> = self.conn.get(&key).await?;
        Ok(data.and_then(|s| serde_json::from_str(&s).ok()))
    }

    pub async fn set_cached<T: serde::Serialize>(
        &mut self, entity: &str, id: &str, value: &T, ttl_secs: u64,
    ) -> redis::RedisResult<()> {
        let key = self.key(entity, id);
        let json = serde_json::to_string(value).map_err(|e|
            redis::RedisError::from((redis::ErrorKind::TypeError, "serialize", e.to_string()))
        )?;
        self.conn.set_ex(&key, &json, ttl_secs).await
    }

    pub async fn invalidate(&mut self, entity: &str, id: &str) -> redis::RedisResult<()> {
        let key = self.key(entity, id);
        self.conn.del(&key).await
    }
}
```

## 3. Neo4j with neo4rs

```toml
[dependencies]
neo4rs = "0.8"
```

Graph client:

```rust
use neo4rs::{Graph, query};

pub struct GraphClient {
    graph: Graph,
}

impl GraphClient {
    pub async fn new(uri: &str, user: &str, pass: &str) -> Result<Self, neo4rs::Error> {
        let graph = Graph::new(uri, user, pass).await?;
        Ok(Self { graph })
    }

    pub async fn ensure_constraints(&self) -> Result<(), neo4rs::Error> {
        self.graph.run(query(
            "CREATE CONSTRAINT uniq_user_userId IF NOT EXISTS
             FOR (u:User) REQUIRE u.userId IS UNIQUE"
        )).await?;
        Ok(())
    }

    pub async fn upsert_user(&self, user_id: &str, email: &str) -> Result<(), neo4rs::Error> {
        self.graph.run(
            query("MERGE (u:User {userId: $uid}) SET u.email = $email, u.updatedAt = datetime()")
                .param("uid", user_id)
                .param("email", email)
        ).await
    }

    pub async fn add_relationship(
        &self, from_id: &str, to_id: &str, rel_type: &str,
    ) -> Result<(), neo4rs::Error> {
        let cypher = format!(
            "MATCH (a:User {{userId: $from}}), (b:User {{userId: $to}})
             MERGE (a)-[:{}]->(b)", rel_type  // rel_type must be validated
        );
        self.graph.run(query(&cypher).param("from", from_id).param("to", to_id)).await
    }
}
```

## 4. Model Patterns

Shared model with DB-specific conversions:

```rust
/// Domain model — database-agnostic
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserDomain {
    pub id: Uuid,
    pub email: String,
    pub name: String,
    pub status: UserStatus,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum UserStatus { Active, Suspended, Deleted }

/// Convert from SQLite row
impl From<User> for UserDomain {
    fn from(row: User) -> Self {
        Self {
            id: Uuid::parse_str(&row.external_id).unwrap(),
            email: row.email,
            name: row.name,
            status: match row.status.as_str() {
                "active" => UserStatus::Active,
                "suspended" => UserStatus::Suspended,
                _ => UserStatus::Deleted,
            },
            created_at: DateTime::parse_from_rfc3339(&row.created_at)
                .unwrap().with_timezone(&Utc),
        }
    }
}
```

## 5. Error Handling

Unified error type across all three databases:

```rust
#[derive(Debug, thiserror::Error)]
pub enum DbError {
    #[error("SQLite error: {0}")]
    Sqlite(#[from] sqlx::Error),
    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),
    #[error("Neo4j error: {0}")]
    Neo4j(#[from] neo4rs::Error),
    #[error("Not found: {entity} {id}")]
    NotFound { entity: String, id: String },
    #[error("Conflict: optimistic lock failed")]
    OptimisticLock,
}
```

## 6. Connection Management

Unified database context:

```rust
pub struct DbContext {
    pub sqlite: SqlitePool,
    pub redis: CacheLayer,
    pub graph: GraphClient,
}

impl DbContext {
    pub async fn new(config: &DbConfig) -> Result<Self, DbError> {
        let sqlite = create_pool(&config.sqlite_path).await?;
        let redis = CacheLayer::new(&config.redis_url, &config.service_name).await?;
        let graph = GraphClient::new(&config.neo4j_uri, &config.neo4j_user, &config.neo4j_pass).await?;
        graph.ensure_constraints().await?;
        Ok(Self { sqlite, redis, graph })
    }
}
```
