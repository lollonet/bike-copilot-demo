---
id: TRACEABILITY
domain: docs
status: approved
source_of_truth: true
related: [REQ-INDEX, ARC-INDEX, TECH-INDEX]
---

# Traceability Matrix

This document maps requirements to implementation files and tests.

## Requirements → Code → Tests

| REQ ID | Requirement | Primary Files | Tests | API Endpoints |
|--------|-------------|---------------|-------|---------------|
| [REQ-001](requirements/REQ-001.search.md) | Product Search | `app/search.py`, `app/pn.py` | `tests/test_search.py`, `tests/test_pn.py` | `POST /search`, `POST /facets` |
| [REQ-002](requirements/REQ-002.offers-display.md) | Offers Display | `app/ui.py`, `app/ui_pn.py`, `app/templates/` | `tests/test_ui.py` | (UI routes) |
| [REQ-003](requirements/REQ-003.optimizer.md) | Order Optimizer | `app/optimizer.py`, `app/policy.py` | `tests/test_optimizer.py` | `POST /optimize` |
| [REQ-004](requirements/REQ-004.cart.md) | Cart Management | `app/ui.py`, `app/staging.py` | `tests/test_ui.py`, `tests/test_staging.py` | (UI routes) |
| [REQ-005](requirements/REQ-005.quotes.md) | Quote Generation | `app/quote.py`, `app/templates/` | `tests/test_quote_render.py` | `POST /quote` |
| [REQ-006](requirements/REQ-006.dealer-config.md) | Dealer Config | `app/dealers.py`, `app/policy.py`, `providers/` | `tests/test_dealers.py` | `GET /dealers` |
| [REQ-007](requirements/REQ-007.crawling.md) | Data Crawling | `app/ingest.py`, `app/adapters/` | `tests/test_ingest.py`, `tests/test_web_adapter.py` | (CLI only) |
| [REQ-008](requirements/REQ-008.kpi.md) | Quality KPIs | `app/api.py` (kpi routes) | `tests/test_api.py` | `GET /kpi/today`, `GET /kpi/summary` |

## Code Modules → Purpose

| Module | Purpose | Used By |
|--------|---------|---------|
| `app/api.py` | FastAPI routes | REQ-001, REQ-003, REQ-005, REQ-006, REQ-008 |
| `app/cli.py` | Typer CLI commands | REQ-007 |
| `app/search.py` | Search service | REQ-001 |
| `app/pn.py` | Part number normalization | REQ-001 |
| `app/optimizer.py` | Order optimization | REQ-003 |
| `app/policy.py` | Dealer shipping policies | REQ-003, REQ-006 |
| `app/quote.py` | Quote PDF generation | REQ-005 |
| `app/dealers.py` | Dealer configuration loader | REQ-006 |
| `app/ingest.py` | Data ingestion orchestrator | REQ-007 |
| `app/staging.py` | Cart staging | REQ-004 |
| `app/models.py` | SQLAlchemy ORM models | All |
| `app/types.py` | Pydantic request/response models | All |
| `app/config.py` | Environment configuration | All |

## Adapters (Crawling)

| Adapter | Purpose | Test |
|---------|---------|------|
| `app/adapters/web_adapter.py` | Web scraping orchestration | `tests/test_web_adapter.py` |
| `app/adapters/playwright_fetcher.py` | Playwright browser automation | (integration) |
| `app/adapters/csv_adapter.py` | CSV file ingestion | `tests/test_csv_adapter.py` |
| `app/adapters/csv_mapped_adapter.py` | Mapped CSV ingestion | `tests/test_csv_mapped_adapter.py` |
| `app/adapters/pdf_adapter.py` | PDF catalog extraction | `tests/test_pdf_adapter.py` |

## Test Coverage Summary

| Test File | Covers | REQ |
|-----------|--------|-----|
| `tests/test_search.py` | Search functionality | REQ-001 |
| `tests/test_pn.py` | Part number matching | REQ-001 |
| `tests/test_optimizer.py` | Optimization algorithms | REQ-003 |
| `tests/test_quote_render.py` | Quote PDF rendering | REQ-005 |
| `tests/test_dealers.py` | Dealer config loading | REQ-006 |
| `tests/test_ingest.py` | Data ingestion | REQ-007 |
| `tests/test_web_adapter.py` | Web scraping | REQ-007 |
| `tests/test_api.py` | API endpoints | REQ-001, REQ-003, REQ-005, REQ-008 |
| `tests/test_ui.py` | UI routes | REQ-002, REQ-004 |

## Verification Checklist

To verify a requirement is implemented:

1. Check the "Primary Files" column for implementation
2. Run the tests in the "Tests" column
3. If API endpoint exists, test with curl (see [API Examples](api/examples.md))

```bash
# Run tests for a specific requirement
uv run pytest tests/test_search.py -v  # REQ-001
uv run pytest tests/test_optimizer.py -v  # REQ-003
```

## Gap Analysis

| REQ | Implementation | Tests | Status |
|-----|---------------|-------|--------|
| REQ-001 | Complete | Complete | ✅ |
| REQ-002 | Complete | Partial | ⚠️ |
| REQ-003 | Complete | Complete | ✅ |
| REQ-004 | Complete | Partial | ⚠️ |
| REQ-005 | Complete | Complete | ✅ |
| REQ-006 | Complete | Complete | ✅ |
| REQ-007 | Complete | Complete | ✅ |
| REQ-008 | Complete | Partial | ⚠️ |

Legend: ✅ Full coverage | ⚠️ Needs more tests | ❌ Missing
