---
id: ADR-001
domain: decisions
status: accepted
date: 2024-12-01
related: [TECH-010, ARC-010]
---

# ADR-001: SQLite as Primary Database

## Status

Accepted

## Context

Bike Copilot needs a database to store:
- Product catalog (~50K-100K products)
- Supplier offers with pricing
- Price history for tracking changes
- Dealer policies and configuration

The application is deployed locally on shop PCs (Windows/Mac/Linux) and must work without requiring database server installation or administration.

## Options Considered

### Option 1: PostgreSQL
**Pros:**
- Industry standard, battle-tested
- Advanced features (JSON, full-text search, CTEs)
- Excellent tooling and monitoring

**Cons:**
- Requires server installation and configuration
- Adds operational complexity for shop owners
- Overkill for single-user, local deployment

### Option 2: SQLite
**Pros:**
- Zero configuration, embedded in application
- Single file database, easy backup (copy file)
- WAL mode supports concurrent reads
- Sufficient performance for expected scale
- No network latency

**Cons:**
- Limited concurrent write throughput
- No built-in replication
- Fewer advanced features

### Option 3: DuckDB
**Pros:**
- Excellent for analytical queries
- Column-oriented, fast aggregations

**Cons:**
- Less mature ecosystem
- Not designed for OLTP workloads
- Limited ORM support

## Decision

**Use SQLite with WAL mode.**

## Rationale

1. **Local-first deployment**: Shop owners should not manage a database server
2. **Scale is modest**: <100K products, single user, read-heavy workload
3. **Backup simplicity**: Copy `data/bike.db` to backup
4. **Zero dependencies**: No external services to configure or monitor
5. **Performance**: Local disk access faster than network DB for this use case

## Configuration

```python
# WAL mode for concurrent reads during crawl
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

## Consequences

### Positive
- Simpler deployment and operations
- No database server to maintain
- Fast local queries
- Easy to backup and restore

### Negative
- Cannot scale to multi-user without significant changes
- No real-time replication
- Must migrate to PostgreSQL if SaaS deployment needed

### Mitigation
- SQLAlchemy ORM abstracts database-specific code
- Future migration path documented in ARC-010 evolution section

## References

- [SQLite When to Use](https://www.sqlite.org/whentouse.html)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
