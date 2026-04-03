# Neo4j Graph Schema Patterns

## Table of Contents

1. Node and Relationship Design
2. Naming Conventions
3. Constraints and Indexes
4. Common Graph Patterns
5. Cypher Query Patterns
6. Integration with SQLite

## 1. Node and Relationship Design

Nodes represent entities. Relationships represent verbs between them.

```cypher
// Nodes — PascalCase labels, properties as camelCase
(:User {userId: "uuid", email: "...", createdAt: datetime()})
(:Product {productId: "uuid", name: "...", priceInCents: 4999})
(:Role {name: "admin", description: "..."})
(:Tenant {tenantId: "uuid", name: "..."})

// Relationships — UPPER_SNAKE_CASE verbs, with properties when needed
(:User)-[:PURCHASED {quantity: 2, purchasedAt: datetime()}]->(:Product)
(:User)-[:HAS_ROLE {grantedAt: datetime(), grantedBy: "uuid"}]->(:Role)
(:User)-[:BELONGS_TO]->(:Tenant)
(:User)-[:FOLLOWS {since: datetime()}]->(:User)
```

Rules:
- Node labels are **nouns** in PascalCase: `User`, `Product`, `OrderItem`
- Relationships are **verbs** in UPPER_SNAKE_CASE: `PURCHASED`, `FOLLOWS`, `CREATED_BY`
- Never use nouns for relationships (not `:FRIENDSHIP`, use `:FRIENDS_WITH`)
- Store the same `userId`/`productId` UUIDs as in SQLite for cross-DB joins
- Timestamps use Neo4j `datetime()` type, not strings

## 2. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Node labels | PascalCase noun | `:User`, `:OrderItem` |
| Relationship types | UPPER_SNAKE_CASE verb | `:PURCHASED`, `:REPORTS_TO` |
| Properties | camelCase | `userId`, `createdAt`, `priceInCents` |
| Indexes | `idx_{label}_{property}` | `idx_user_email` |
| Constraints | `uniq_{label}_{property}` | `uniq_user_userId` |

## 3. Constraints and Indexes

Apply these at schema creation time:

```cypher
// Uniqueness constraints (also create indexes automatically)
CREATE CONSTRAINT uniq_user_userId IF NOT EXISTS
FOR (u:User) REQUIRE u.userId IS UNIQUE;

CREATE CONSTRAINT uniq_product_productId IF NOT EXISTS
FOR (p:Product) REQUIRE p.productId IS UNIQUE;

// Existence constraints (enterprise edition)
CREATE CONSTRAINT req_user_email IF NOT EXISTS
FOR (u:User) REQUIRE u.email IS NOT NULL;

// Node key constraints (composite uniqueness)
CREATE CONSTRAINT key_tenant_user IF NOT EXISTS
FOR (u:User) REQUIRE (u.tenantId, u.email) IS NODE KEY;

// Indexes for frequently queried properties
CREATE INDEX idx_user_email IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX idx_product_name IF NOT EXISTS FOR (p:Product) ON (p.name);

// Full-text index for search
CREATE FULLTEXT INDEX ft_product_search IF NOT EXISTS
FOR (p:Product) ON EACH [p.name, p.description];

// Relationship property index
CREATE INDEX idx_purchased_date IF NOT EXISTS
FOR ()-[r:PURCHASED]-() ON (r.purchasedAt);
```

## 4. Common Graph Patterns

### Access Control Graph (Advanced Stage)

```cypher
(:User)-[:HAS_ROLE]->(:Role)-[:PERMITS {actions: ["read","write"]}]->(:Resource)
(:Role)-[:INHERITS_FROM]->(:Role)  // role hierarchy

// Query: Can user X do action Y on resource Z?
MATCH (u:User {userId: $uid})-[:HAS_ROLE]->(r:Role)-[:PERMITS]->(res:Resource {name: $resource})
WHERE $action IN r.actions
RETURN count(r) > 0 AS permitted
```

### Recommendation Engine

```cypher
// Users who bought X also bought Y
MATCH (u:User)-[:PURCHASED]->(:Product {productId: $pid})<-[:PURCHASED]-(other:User)
MATCH (other)-[:PURCHASED]->(rec:Product)
WHERE NOT (u)-[:PURCHASED]->(rec)
RETURN rec.name, count(other) AS score ORDER BY score DESC LIMIT 10
```

### Organization Hierarchy

```cypher
(:Employee)-[:REPORTS_TO]->(:Employee)
(:Department)-[:PART_OF]->(:Division)
(:Employee)-[:WORKS_IN]->(:Department)

// Find all reports (recursive)
MATCH (mgr:Employee {userId: $uid})<-[:REPORTS_TO*1..10]-(report:Employee)
RETURN report.name, length(path) AS depth
```

### Knowledge Graph (Advanced Stage)

```cypher
(:Concept)-[:RELATED_TO {weight: 0.85}]->(:Concept)
(:Document)-[:MENTIONS]->(:Concept)
(:User)-[:INTERESTED_IN]->(:Concept)
```

## 5. Cypher Query Patterns

### Parameterized Queries (always use parameters, never string concatenation)

```cypher
// Good — parameterized
MATCH (u:User {userId: $userId}) RETURN u

// Bad — injection risk
MATCH (u:User {userId: '${userId}'}) RETURN u
```

### Batch Operations

```cypher
// Use UNWIND for bulk inserts
UNWIND $users AS userData
MERGE (u:User {userId: userData.userId})
SET u.email = userData.email, u.name = userData.name, u.updatedAt = datetime()
```

### Pagination

```cypher
MATCH (u:User)
WHERE u.createdAt < $cursor
RETURN u ORDER BY u.createdAt DESC LIMIT $pageSize
```

## 6. Integration with SQLite

Neo4j stores relationships and graph queries. SQLite stores the full entity data. They share UUIDs.

```
SQLite: users table (id, external_id, email, name, ..., all columns)
Neo4j:  (:User {userId: external_id, email})  ← minimal properties for graph queries

Sync pattern:
1. Write to SQLite (source of truth for entity data)
2. Publish event to Redis Stream
3. Consumer creates/updates Neo4j node with UUID + graph-relevant properties
4. Graph queries return UUIDs → fetch full data from SQLite
```

Only store properties in Neo4j that are needed for graph traversal or filtering. Full entity data lives in SQLite.
