# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Dealer List Fallback** - Automatic fallback to providers YAML when database is empty (Dec 17)
- **All-Dealers Crawl** - New make targets for bulk dealer synchronization (Dec 17)
- **Offer Reconciliation** - Soft-delete stale offers with configurable cutoff (Dec 17)
- **Database Reset** - Clean reset capability for fresh ingestion (Dec 17)
- **Seed URL Crawling** - Full catalog crawl using configured seed URLs instead of search queries (Dec 17)
- **Code Review Integration** - Claude Code automated review in GitHub Actions workflow (Dec 18)
- **Ruff Linting** - Added ruff for Python linting and formatting (Dec 18)
- **Type Checking** - Basedpyright configuration for static type analysis (Dec 18)
- **Security Scanning** - Bandit security scanner in CI pipeline (Dec 19)
- **Base64 Authentication** - Support for Base64-encoded credentials in SPA login (Jan 18)
- **Web Ingestion Testing** - Comprehensive test suite and documentation for B2B scraping (Jan 18)

### Changed
- **RMS Authentication Endpoint** - Updated to correct API endpoint (apib2b.rms.it/users/authenticate) (Jan 18)
- **Authentication Defaults** - Enforced secure defaults for dealer authentication (Dec 18)
- **Price History** - Enhanced trace context and price change recording (Dec 18)
- **CI Workflows** - Improved Claude review workflows with sticky comments (Dec 19)

### Fixed
- **Skeptic Review Issues** - Applied security and correctness fixes from automated review (Dec 18)
- **Stale Offer Cutoff** - Fixed reconcile-offers timestamp handling (Dec 18)
- **Ruff Lint Errors** - Resolved all linting violations (Dec 18)
- **Claude Action Auth** - Fixed GitHub Actions authentication (OAuth token vs API key) (Dec 18)
- **Claude Secret Guard** - Protected workflows when ANTHROPIC_API_KEY is missing (Dec 18)
- **KPI Tests** - Fixed broken tests after authentication changes (Dec 18)

### Documentation
- **Complete REQ/ARC/TECH Rewrite** - Comprehensive documentation overhaul (#71) (Jan 16)
- **Crawl/Ingest Targets** - Documented new make targets for dealer operations (Dec 17)
- **Session Standards** - Added runbooks and workflow documentation (Dec 18)
- **RMS Authentication Notes** - Technical investigation documenting AES encryption requirement (Jan 18)

### Removed
- **Claude Refactor Triggers** - Removed obsolete CI trigger configuration (#72) (Jan 16)
- **Obsolete Documentation** - Cleaned up 12 legacy files from root directory (#73) (Jan 17)

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
