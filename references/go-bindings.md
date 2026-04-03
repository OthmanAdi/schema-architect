# Go Database Bindings

## Table of Contents

1. SQLite with database/sql + modernc
2. Redis with go-redis
3. Neo4j with neo4j-go-driver
4. Model Patterns
5. Error Handling
6. Connection Management

## 1. SQLite with database/sql

Preferred: `modernc.org/sqlite` (pure Go, no CGO) with `database/sql`.

```go
// go.mod dependencies
// modernc.org/sqlite
// github.com/google/uuid
```

Model struct:

```go
package models

import (
    "database/sql"
    "time"
    "github.com/google/uuid"
)

type User struct {
    ID         int64     `json:"-" db:"id"`
    ExternalID string    `json:"id" db:"external_id"`
    Email      string    `json:"email" db:"email"`
    Name       string    `json:"name" db:"name"`
    Status     string    `json:"status" db:"status"`
    CreatedAt  string    `json:"created_at" db:"created_at"`
    UpdatedAt  string    `json:"updated_at" db:"updated_at"`
    Version    int64     `json:"-" db:"version"`
}
```

Repository pattern:

```go
package repository

import (
    "context"
    "database/sql"
    "fmt"
    "github.com/google/uuid"
)

type UserRepo struct {
    db *sql.DB
}

func NewUserRepo(db *sql.DB) *UserRepo {
    return &UserRepo{db: db}
}

func (r *UserRepo) FindByID(ctx context.Context, id int64) (*User, error) {
    row := r.db.QueryRowContext(ctx,
        "SELECT id, external_id, email, name, status, created_at, updated_at, version FROM users WHERE id = ?", id)
    var u User
    err := row.Scan(&u.ID, &u.ExternalID, &u.Email, &u.Name, &u.Status, &u.CreatedAt, &u.UpdatedAt, &u.Version)
    if err == sql.ErrNoRows {
        return nil, nil
    }
    return &u, err
}

func (r *UserRepo) Create(ctx context.Context, email, name string) (int64, error) {
    extID := uuid.New().String()
    result, err := r.db.ExecContext(ctx,
        "INSERT INTO users (external_id, email, name) VALUES (?, ?, ?)",
        extID, email, name)
    if err != nil {
        return 0, err
    }
    return result.LastInsertId()
}

func (r *UserRepo) UpdateOptimistic(ctx context.Context, u *User) (bool, error) {
    result, err := r.db.ExecContext(ctx,
        `UPDATE users SET email = ?, name = ?, version = version + 1,
         updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
         WHERE id = ? AND version = ?`,
        u.Email, u.Name, u.ID, u.Version)
    if err != nil {
        return false, err
    }
    rows, _ := result.RowsAffected()
    return rows > 0, nil
}
```

Connection setup:

```go
package db

import (
    "database/sql"
    _ "modernc.org/sqlite"
)

func OpenSQLite(path string) (*sql.DB, error) {
    db, err := sql.Open("sqlite", path+"?_journal_mode=WAL&_busy_timeout=5000&_foreign_keys=ON")
    if err != nil {
        return nil, err
    }
    db.SetMaxOpenConns(1)  // SQLite: single writer
    db.SetMaxIdleConns(2)

    // Performance pragmas
    pragmas := []string{
        "PRAGMA synchronous = NORMAL",
        "PRAGMA cache_size = -64000",
        "PRAGMA auto_vacuum = INCREMENTAL",
    }
    for _, p := range pragmas {
        if _, err := db.Exec(p); err != nil {
            return nil, err
        }
    }
    return db, nil
}
```

## 2. Redis with go-redis

```go
// github.com/redis/go-redis/v9
```

Cache layer:

```go
package cache

import (
    "context"
    "encoding/json"
    "fmt"
    "time"
    "github.com/redis/go-redis/v9"
)

type CacheLayer struct {
    client *redis.Client
    prefix string
}

func NewCacheLayer(redisURL, service string) (*CacheLayer, error) {
    opts, err := redis.ParseURL(redisURL)
    if err != nil {
        return nil, err
    }
    return &CacheLayer{
        client: redis.NewClient(opts),
        prefix: service,
    }, nil
}

func (c *CacheLayer) key(entity, id string) string {
    return fmt.Sprintf("%s:cache:%s:%s", c.prefix, entity, id)
}

func (c *CacheLayer) Get(ctx context.Context, entity, id string, dest interface{}) error {
    data, err := c.client.Get(ctx, c.key(entity, id)).Bytes()
    if err == redis.Nil {
        return ErrCacheMiss
    }
    if err != nil {
        return err
    }
    return json.Unmarshal(data, dest)
}

func (c *CacheLayer) Set(ctx context.Context, entity, id string, value interface{}, ttl time.Duration) error {
    data, err := json.Marshal(value)
    if err != nil {
        return err
    }
    return c.client.Set(ctx, c.key(entity, id), data, ttl).Err()
}

func (c *CacheLayer) Invalidate(ctx context.Context, entity, id string) error {
    return c.client.Del(ctx, c.key(entity, id)).Err()
}

var ErrCacheMiss = fmt.Errorf("cache miss")
```

## 3. Neo4j with neo4j-go-driver

```go
// github.com/neo4j/neo4j-go-driver/v5
```

Graph client:

```go
package graph

import (
    "context"
    "github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

type GraphClient struct {
    driver neo4j.DriverWithContext
}

func NewGraphClient(uri, user, pass string) (*GraphClient, error) {
    driver, err := neo4j.NewDriverWithContext(uri, neo4j.BasicAuth(user, pass, ""))
    if err != nil {
        return nil, err
    }
    return &GraphClient{driver: driver}, nil
}

func (g *GraphClient) Close(ctx context.Context) error {
    return g.driver.Close(ctx)
}

func (g *GraphClient) EnsureConstraints(ctx context.Context) error {
    session := g.driver.NewSession(ctx, neo4j.SessionConfig{})
    defer session.Close(ctx)
    _, err := session.Run(ctx,
        `CREATE CONSTRAINT uniq_user_userId IF NOT EXISTS
         FOR (u:User) REQUIRE u.userId IS UNIQUE`, nil)
    return err
}

func (g *GraphClient) UpsertUser(ctx context.Context, userID, email string) error {
    session := g.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
    defer session.Close(ctx)
    _, err := session.Run(ctx,
        `MERGE (u:User {userId: $uid})
         SET u.email = $email, u.updatedAt = datetime()`,
        map[string]interface{}{"uid": userID, "email": email})
    return err
}

func (g *GraphClient) AddRelationship(ctx context.Context, fromID, toID, relType string) error {
    session := g.driver.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
    defer session.Close(ctx)
    cypher := fmt.Sprintf(
        `MATCH (a:User {userId: $from}), (b:User {userId: $to})
         MERGE (a)-[:%s]->(b)`, relType)
    _, err := session.Run(ctx, cypher,
        map[string]interface{}{"from": fromID, "to": toID})
    return err
}
```

## 4. Model Patterns

Domain model with DB-specific conversions:

```go
package domain

type UserDomain struct {
    ID        string     `json:"id"`
    Email     string     `json:"email"`
    Name      string     `json:"name"`
    Status    UserStatus `json:"status"`
    CreatedAt time.Time  `json:"created_at"`
}

type UserStatus string
const (
    StatusActive    UserStatus = "active"
    StatusSuspended UserStatus = "suspended"
    StatusDeleted   UserStatus = "deleted"
)

func UserFromRow(row *User) *UserDomain {
    t, _ := time.Parse(time.RFC3339, row.CreatedAt)
    return &UserDomain{
        ID:        row.ExternalID,
        Email:     row.Email,
        Name:      row.Name,
        Status:    UserStatus(row.Status),
        CreatedAt: t,
    }
}
```

## 5. Error Handling

Unified error type:

```go
package dberr

import "errors"

var (
    ErrNotFound       = errors.New("entity not found")
    ErrOptimisticLock = errors.New("optimistic lock conflict")
    ErrCacheMiss      = errors.New("cache miss")
)

type DbError struct {
    Source string // "sqlite", "redis", "neo4j"
    Op     string // "find", "create", "update"
    Err    error
}

func (e *DbError) Error() string {
    return fmt.Sprintf("%s.%s: %v", e.Source, e.Op, e.Err)
}

func (e *DbError) Unwrap() error { return e.Err }
```

## 6. Connection Management

Unified database context:

```go
package db

type DbContext struct {
    SQLite *sql.DB
    Redis  *CacheLayer
    Graph  *GraphClient
}

func NewDbContext(cfg *Config) (*DbContext, error) {
    sqlite, err := OpenSQLite(cfg.SQLitePath)
    if err != nil {
        return nil, fmt.Errorf("sqlite: %w", err)
    }
    redis, err := NewCacheLayer(cfg.RedisURL, cfg.ServiceName)
    if err != nil {
        return nil, fmt.Errorf("redis: %w", err)
    }
    graph, err := NewGraphClient(cfg.Neo4jURI, cfg.Neo4jUser, cfg.Neo4jPass)
    if err != nil {
        return nil, fmt.Errorf("neo4j: %w", err)
    }
    if err := graph.EnsureConstraints(context.Background()); err != nil {
        return nil, fmt.Errorf("neo4j constraints: %w", err)
    }
    return &DbContext{SQLite: sqlite, Redis: redis, Graph: graph}, nil
}

func (ctx *DbContext) Close() {
    ctx.SQLite.Close()
    ctx.Redis.client.Close()
    ctx.Graph.Close(context.Background())
}
```
