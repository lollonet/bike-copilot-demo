# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Optimizer V1** ([#20](https://github.com/lollonet/bike-copilot-demo/pull/20)) - Nov 12, 2025
  - Multi-scenario quote optimization
  - API endpoint `/optimize` for programmatic access
  - Support for dealer constraints and shipping policies

- **KPI Summary & PN-First UI** ([#21](https://github.com/lollonet/bike-copilot-demo/pull/21)) - Nov 13, 2025
  - Dashboard with key performance indicators
  - Part number-first search interface

- **Comprehensive Test Coverage** ([#31](https://github.com/lollonet/bike-copilot-demo/pull/31)) - Nov 14, 2025
  - 146 total tests across core modules
  - Unit tests for search, optimizer, PN mapping, ingest

- **Dealer Management System** ([#33](https://github.com/lollonet/bike-copilot-demo/pull/33)) - Nov 14, 2025
  - Complete dealer configuration framework
  - Session management with automatic login/logout
  - Policy fetching and storage per dealer

- **Brand-Specific Seed URLs** ([#35](https://github.com/lollonet/bike-copilot-demo/pull/35)) - Nov 15, 2025
  - CicloPromo brand-specific seed URLs for better coverage

- **RMS Dealer Configuration** ([#36](https://github.com/lollonet/bike-copilot-demo/pull/36)) - Nov 15, 2025
  - Angular SPA support for dynamic content
  - RMS dealer authentication and catalog access

- **Structured Logging & Web Crawling** ([#55](https://github.com/lollonet/bike-copilot-demo/pull/55)) - Dec 17, 2025
  - JSON structured logging with trace context
  - Filter chips in UI
  - Web crawling with sitemap support
  - Playwright integration for JS-heavy sites

- **All Dealers Crawl** ([#60](https://github.com/lollonet/bike-copilot-demo/pull/60)) - Dec 17, 2025
  - Parallel crawling of all configured dealers
  - Makefile targets: `all-dealers-crawl`, `ingest-all`, `reconcile-offers`, `reset-db`
  - Fallback dealers list from providers when DB empty

- **Claude Code CI Workflows** ([#59](https://github.com/lollonet/bike-copilot-demo/pull/59), [#62](https://github.com/lollonet/bike-copilot-demo/pull/62)) - Dec 18, 2025
  - Automated PR review with Claude AI
  - Security scanning and vulnerability detection
  - Interactive workflow for PR comments

### Changed

- **Complexity Gates** ([#22](https://github.com/lollonet/bike-copilot-demo/pull/22), [#23](https://github.com/lollonet/bike-copilot-demo/pull/23)) - Nov 13, 2025
  - Cognitive complexity warnings in CI
  - App complexity observability with artifacts

- **Web Adapter Refactoring** ([#24](https://github.com/lollonet/bike-copilot-demo/pull/24)) - Nov 13, 2025
  - Stable pagination handling
  - Reduced cognitive complexity
  - Improved error handling

- **PR Sanitization** ([#25](https://github.com/lollonet/bike-copilot-demo/pull/25)) - Nov 13, 2025
  - Removed literal strings from PR titles/bodies

- **Core Module Refactoring** ([#26](https://github.com/lollonet/bike-copilot-demo/pull/26)-[#30](https://github.com/lollonet/bike-copilot-demo/pull/30)) - Nov 13-14, 2025
  - PN search: Extracted helper functions, reduced complexity
  - Optimizer: Split scenarios and cost calculation
  - Search: Extracted helpers for prefiltering, offers, facets
  - Ingest: Separated product, offer, PN mapping logic
  - CLI: Simplified `dump-md` and `pn-alias-import`

- **Complexity Cleanup** ([#37](https://github.com/lollonet/bike-copilot-demo/pull/37)) - Nov 15, 2025
  - Round 1 of complexity reduction

- **Logging & Session Refactor** ([#38](https://github.com/lollonet/bike-copilot-demo/pull/38), [#39](https://github.com/lollonet/bike-copilot-demo/pull/39)) - Nov 15, 2025
  - Dealer session management improvements
  - Infrastructure test coverage
  - Complexity gate compliance

- **UI Complexity Refactor** ([#40](https://github.com/lollonet/bike-copilot-demo/pull/40), [#41](https://github.com/lollonet/bike-copilot-demo/pull/41)) - Nov 16, 2025
  - UI complexity gate compliance
  - PN UI complexity improvements

- **SQLAlchemy 2.0 Migration** ([#54](https://github.com/lollonet/bike-copilot-demo/pull/54)) - Dec 17, 2025
  - Migrated to SQLAlchemy 2.0 with modern query patterns
  - Implemented dependency injection for database sessions
  - Achieved mypy clean type checking

- **Session Summaries** ([#56](https://github.com/lollonet/bike-copilot-demo/pull/56)) - Dec 17, 2025
  - Consolidated session summary format

- **SOTA Workflow Tools** ([#67](https://github.com/lollonet/bike-copilot-demo/pull/67)) - Dec 19, 2025
  - Standardized documentation with frontmatter
  - Workflow automation tools

- **ARC-001: UI Refactoring - Phase 1 & 2** ([#74](https://github.com/lollonet/bike-copilot-demo/pull/74)) - Jan 19, 2026
  - Created shared API client module (`app/api_client.py`)
  - Fixed CLI → UI architectural boundary violation
  - Removed ~50 lines of duplicated code
  - Added 10 comprehensive unit tests

- **ARC-001: UI Refactoring - Phase 3a** ([#75](https://github.com/lollonet/bike-copilot-demo/pull/75), [#77](https://github.com/lollonet/bike-copilot-demo/pull/77)) - Jan 19, 2026
  - Extracted search handler to `app/ui_handlers_search.py`
  - Created `app/ui_helpers.py` with shared utilities
  - Improved separation of concerns

- **ARC-001: UI Refactoring - Phase 3b** ([#78](https://github.com/lollonet/bike-copilot-demo/pull/78)) - Jan 19, 2026
  - Consolidated 5 repetitive facet handlers into factory function
  - Reduced duplication in `app/ui_handlers_filters.py`

- **ARC-001: UI Refactoring - Phase 3c** ([#79](https://github.com/lollonet/bike-copilot-demo/pull/79)) - Jan 19, 2026
  - Extracted cart handlers to `app/ui_handlers_cart.py` (7 functions)
  - Extracted quote handlers to `app/ui_handlers_quote.py` (3 functions)
  - **Total ui.py reduction: 1,130 → 727 lines (-35.6%)**

- **ARC-002: CLI Refactoring - Phase 1** ([#80](https://github.com/lollonet/bike-copilot-demo/pull/80)) - Jan 19, 2026
  - Extracted fetch commands to `app/commands/fetch_commands.py` (5 commands)
  - Created `app/cli_helpers/fetch_helpers.py` (6 helper functions)
  - Reduced cli.py from 1,861 to 1,609 lines (-13.5%)
  - Established modular architecture pattern

- **ARC-002: CLI Refactoring - Phase 2** ([#81](https://github.com/lollonet/bike-copilot-demo/pull/81)) - Jan 20, 2026
  - Extracted ingest commands to `app/commands/ingest_commands.py` (5 commands)
  - Created `app/cli_helpers/ingest_helpers.py` (20 helper functions)
  - Created `app/cli_helpers/common.py` (shared utilities)
  - Reduced cli.py from 1,607 to 1,033 lines (-35.7%)

- **ARC-002: CLI Refactoring - Phase 3** ([#82](https://github.com/lollonet/bike-copilot-demo/pull/82)) - Jan 20, 2026
  - Extracted data commands to `app/commands/data_commands.py` (2 commands)
  - Created `app/cli_helpers/data_helpers.py` (14 helper functions)
  - Reduced cli.py from 1,033 to 749 lines (-27.5%)
  - **Cumulative cli.py reduction: 1,861 → 749 lines (-59.7%)**

### Fixed

- **Skeptic Review Bugfixes** ([#58](https://github.com/lollonet/bike-copilot-demo/pull/58)) - Dec 18, 2025
  - Security fixes from automated code review
  - Trace context preservation
  - Price change tracking

- **Authentication & Testing** ([#60](https://github.com/lollonet/bike-copilot-demo/pull/60)) - Dec 18, 2025
  - Enforced auth default configuration
  - Fixed KPI endpoint tests

- **Type Safety** ([#57](https://github.com/lollonet/bike-copilot-demo/pull/57)) - Dec 17, 2025
  - Fixed typing for web adapter
  - Optional Playwright dependencies

- **CI Workflow Fixes** ([#68](https://github.com/lollonet/bike-copilot-demo/pull/68)-[#70](https://github.com/lollonet/bike-copilot-demo/pull/70)) - Dec 20, 2025
  - Fixed AI review triggers and automation
  - Fixed Claude review checkout on comment trigger
  - Silenced CI feedback noise

- **Ruff Lint Errors** ([#58](https://github.com/lollonet/bike-copilot-demo/pull/58)) - Dec 18, 2025
  - Resolved all linting violations

- **Claude Action Auth** ([#62](https://github.com/lollonet/bike-copilot-demo/pull/62)) - Dec 18, 2025
  - Fixed GitHub Actions authentication (OAuth vs API key)

- **Claude Secret Guard** ([#63](https://github.com/lollonet/bike-copilot-demo/pull/63)) - Dec 18, 2025
  - Protected workflows when ANTHROPIC_API_KEY is missing

- **Reverted Unintended Pushes** ([#61](https://github.com/lollonet/bike-copilot-demo/pull/61)) - Dec 19, 2025
  - Reverted accidental direct pushes to main

### Documentation

- **CI/CD Documentation** ([#32](https://github.com/lollonet/bike-copilot-demo/pull/32)) - Nov 14, 2025
  - Updated to match actual workflow implementation

- **General Improvements** ([#34](https://github.com/lollonet/bike-copilot-demo/pull/34)) - Nov 14, 2025
  - Code quality and documentation enhancements

- **Standardize SSOT** ([#66](https://github.com/lollonet/bike-copilot-demo/pull/66)) - Dec 19, 2025
  - Standardized with frontmatter

- **Session Logs Restructure** ([#70](https://github.com/lollonet/bike-copilot-demo/pull/70)) - Dec 20, 2025
  - Organized session logs for better tracking

- **Complete Documentation Rewrite** ([#71](https://github.com/lollonet/bike-copilot-demo/pull/71)) - Jan 16, 2026
  - Comprehensive REQ (requirements), ARC (architecture), TECH documentation
  - Standardized structure and formatting

- **README Alignment** ([#73](https://github.com/lollonet/bike-copilot-demo/pull/73)) - Jan 17, 2026
  - Cleaned up 12 obsolete legacy files
  - Aligned README with current architecture

### Security

- **Security Scanning** ([#64](https://github.com/lollonet/bike-copilot-demo/pull/64)) - Dec 19, 2025
  - Added automated vulnerability scanning
  - Integrated with Claude workflows

- **Skeptic Review Security Fixes** ([#58](https://github.com/lollonet/bike-copilot-demo/pull/58)) - Dec 18, 2025
  - Addressed high-priority security issues

### Removed

- **Claude Refactor Triggers** ([#72](https://github.com/lollonet/bike-copilot-demo/pull/72)) - Jan 16, 2026
  - Removed obsolete CI trigger configuration

- **Obsolete Documentation** ([#73](https://github.com/lollonet/bike-copilot-demo/pull/73)) - Jan 17, 2026
  - Removed 12 legacy files from root directory

---

## [0.1.0] - 2025-12-16

Initial release with core B2B bicycle parts aggregation functionality.

### Added
- Web scraping adapters for CicloPromo, Ciclodiffusione, RMS dealers
- CSV/PDF import adapters for static catalogs
- SQLite database with product/offer schema
- Full-text search with ranking
- Quote generation from search results
- Price history tracking
- CLI interface for dealer sync and search operations
- Playwright integration for JavaScript-rendered sites

[Unreleased]: https://github.com/lollonet/bike-copilot-demo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lollonet/bike-copilot-demo/releases/tag/v0.1.0
