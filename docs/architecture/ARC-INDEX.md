---
id: ARC-INDEX
domain: architecture
status: approved
source_of_truth: true
related: [REQ-INDEX, TECH-INDEX]
acceptance:
  - "All ARC-### files exist and have valid front-matter"
  - "Architecture diagrams are up-to-date with implementation"
  - "Key decisions documented with rationale"
---

# Architecture Index

## Overview

Bike Copilot follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────┐
│                  UI Layer                    │
│            (Jinja2 + HTMX)                  │
├─────────────────────────────────────────────┤
│                 API Layer                    │
│               (FastAPI)                      │
├─────────────────────────────────────────────┤
│              Service Layer                   │
│    (Search, Optimizer, Quote, Crawl)        │
├─────────────────────────────────────────────┤
│               Data Layer                     │
│         (SQLAlchemy + SQLite)               │
├─────────────────────────────────────────────┤
│             External Layer                   │
│    (Dealer websites via Playwright/httpx)   │
└─────────────────────────────────────────────┘
```

## Architecture Documents

| ID | Name | Description |
|----|------|-------------|
| [ARC-010](ARC-010.overview.md) | System Overview | Components, data flow, deployment |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite | Local deployment, zero config, sufficient scale |
| UI Framework | Jinja2 + HTMX | SSR, no JS build, rapid prototyping |
| Scraping | Playwright + httpx | SPA support + lightweight fallback |
| API | FastAPI | Type-safe, async-ready, auto-docs |

## Naming Convention

- `ARC-010` to `ARC-019`: System overview and layers
- `ARC-020` to `ARC-029`: Component details
- `ARC-030` to `ARC-039`: Integration patterns
- `ARC-040` to `ARC-049`: Deployment and operations
