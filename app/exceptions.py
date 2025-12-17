"""Domain-specific exception hierarchy for Bike Copilot."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain errors."""


class IngestError(DomainError):
    """Errors during data ingest (CSV/PDF/web)."""


class SearchError(DomainError):
    """Errors during search/facets/pn lookup."""


class OptimizationError(DomainError):
    """Errors during cart/quote optimization."""


class PolicyError(DomainError):
    """Errors while parsing dealer policies."""


class QuoteRenderError(DomainError):
    """Errors while rendering quote HTML/PDF."""
