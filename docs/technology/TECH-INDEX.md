---
id: TECH-INDEX
domain: technology
status: approved
source_of_truth: true
related: [ARC-INDEX, REQ-INDEX]
acceptance:
  - "All TECH-### files exist and have valid front-matter"
  - "Technology choices documented with rationale"
  - "Version constraints specified for all dependencies"
---

# Technology Index

## Overview

Bike Copilot uses a modern Python stack optimized for local-first deployment, minimal dependencies, and maintainability.

## Technology Documents

| ID | Name | Description |
|----|------|-------------|
| [TECH-010](TECH-010.stack.md) | Technology Stack | Runtime, libraries, database schema |

## Stack Summary

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Runtime | Python 3.12 + uv | Fast, reproducible environment |
| API | FastAPI | Type-safe, async, auto-docs |
| UI | Jinja2 + HTMX | SSR, no JS build, progressive enhancement |
| Database | SQLite (WAL) | Zero-config, local, sufficient scale |
| ORM | SQLAlchemy 2.0 | Typed models, async support |
| Validation | Pydantic v2 | Runtime validation, OpenAPI schemas |
| Scraping | Playwright + httpx | SPA support + lightweight fallback |
| PDF | wkhtmltopdf + Jinja2 | HTML-to-PDF rendering |
| CLI | Typer | Typed CLI commands |

## Naming Convention

- `TECH-010` to `TECH-019`: Runtime and stack
- `TECH-020` to `TECH-029`: Database and storage
- `TECH-030` to `TECH-039`: External integrations
- `TECH-040` to `TECH-049`: DevOps and tooling
