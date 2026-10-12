"""Common constants and helpers shared across CLI commands."""

from __future__ import annotations

import httpx

# Shared constants
DEFAULT_USER_AGENT = "BikeCopilotBot/0.1"


def create_http_client(
    timeout: float = 10.0,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Client:
    """Create a configured httpx.Client with standard defaults.

    Args:
        timeout: Request timeout in seconds
        headers: Custom HTTP headers (will merge with default User-Agent)
        follow_redirects: Whether to follow HTTP redirects

    Returns:
        Configured httpx.Client instance
    """
    default_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        default_headers.update(headers)

    return httpx.Client(
        timeout=timeout,
        headers=default_headers,
        follow_redirects=follow_redirects,
        verify=True,
    )
