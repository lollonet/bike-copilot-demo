"""Shared HTTP client for backend API calls."""

from __future__ import annotations

import os
from typing import Any

import httpx


# API configuration
API_BASE = os.environ.get("APP_API_BASE", "http://localhost:8000").rstrip("/")
_auth_credentials: tuple[str, str] | None = None
_basic_user = os.environ.get("APP_BASIC_USER")
_basic_pass = os.environ.get("APP_BASIC_PASS")
if _basic_user and _basic_pass:
    _auth_credentials = (_basic_user, _basic_pass)


def api_get(path: str, timeout: float = 15.0) -> dict[str, Any]:
    """
    Execute GET request to backend API.

    Args:
        path: API endpoint path (e.g., "/dealers")
        timeout: Request timeout in seconds (default: 15.0)

    Returns:
        JSON response as dictionary

    Raises:
        httpx.HTTPStatusError: If response status is not 2xx
    """
    with httpx.Client(timeout=timeout) as client:
        auth = _auth_credentials if _auth_credentials else httpx.USE_CLIENT_DEFAULT
        r = client.get(f"{API_BASE}{path}", auth=auth)
        r.raise_for_status()
        return r.json()


def api_post(
    path: str, payload: dict[str, Any], timeout: float = 20.0
) -> dict[str, Any]:
    """
    Execute POST request to backend API.

    Args:
        path: API endpoint path (e.g., "/quote")
        payload: JSON payload to send
        timeout: Request timeout in seconds (default: 20.0)

    Returns:
        JSON response as dictionary

    Raises:
        httpx.HTTPStatusError: If response status is not 2xx
    """
    with httpx.Client(timeout=timeout) as client:
        auth = _auth_credentials if _auth_credentials else httpx.USE_CLIENT_DEFAULT
        r = client.post(f"{API_BASE}{path}", json=payload, auth=auth)
        r.raise_for_status()
        return r.json()


def api_post_silent(
    path: str, payload: dict[str, Any], timeout: float = 10.0
) -> httpx.Response:
    """
    Execute POST request without raising on HTTP errors.

    Use this for cases where you need to inspect status codes manually.

    Args:
        path: API endpoint path
        payload: JSON payload to send
        timeout: Request timeout in seconds (default: 10.0)

    Returns:
        Full httpx.Response object
    """
    auth = _auth_credentials if _auth_credentials else None
    return httpx.post(f"{API_BASE}{path}", json=payload, auth=auth, timeout=timeout)
