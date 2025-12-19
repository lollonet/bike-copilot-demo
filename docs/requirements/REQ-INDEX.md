---
id: REQ-INDEX
domain: requirements
status: approved
source_of_truth: true
related: [ARC-INDEX, TECH-INDEX]
acceptance:
  - "All REQ-### files exist and have valid front-matter"
  - "Each REQ has SMART acceptance criteria"
  - "Traceability matrix links REQ to tests and commits"
---

# Requirements Index

## Overview

Bike Copilot is a B2B bike parts price aggregation platform for bike shop owners and mechanics. It crawls dealer catalogs via web scraping, enables multi-dealer price comparison, optimizes orders across suppliers, and generates professional quotes.

**Target Users**: Bike shop owners, workshop mechanics
**Deployment**: Local installation on shop PC
**Scale**: 3-5 curated dealers
**Status**: Prototype

## Requirements List

| ID | Name | Priority | Status |
|----|------|----------|--------|
| [REQ-001](REQ-001.search.md) | Product Search | MUST | approved |
| [REQ-002](REQ-002.offers-display.md) | Offers Display | MUST | approved |
| [REQ-003](REQ-003.optimizer.md) | Order Optimizer | MUST | approved |
| [REQ-004](REQ-004.cart.md) | Shopping Cart | MUST | approved |
| [REQ-005](REQ-005.quotes.md) | Quote Generation | MUST | approved |
| [REQ-006](REQ-006.dealer-config.md) | Dealer Configuration | MUST | approved |
| [REQ-007](REQ-007.crawling.md) | Data Crawling | MUST | approved |
| [REQ-008](REQ-008.kpi.md) | Quality KPIs | SHOULD | approved |

## Priority Legend

- **MUST**: Core functionality, system unusable without it
- **SHOULD**: Important but system functional without it
- **COULD**: Desirable enhancement
- **WONT**: Explicitly out of scope for current version

## Naming Convention

- `REQ-001` to `REQ-099`: Functional requirements
- `REQ-100` to `REQ-199`: Non-functional requirements (future)
- `REQ-200` to `REQ-299`: Integration requirements (future)
