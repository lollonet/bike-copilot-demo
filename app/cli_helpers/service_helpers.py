"""Helper functions for service-related CLI commands."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import httpx
import rich
import typer

from ..dealers import DealerConfig, DealerLoginConfig, find_dealer
from ..ingest import IngestStats, upsert
from ..models import SessionLocal, create_all
from ..policy import parse_policy_html
from .fetch_helpers import upsert_dealer_policy

# Type alias for sitemap parser function
ParseSitemapFn = Callable[
    [str, dict[str, str] | None, int | None, httpx.Client | None], list[str]
]


# --- DealerSession and Authentication ---


class DealerSession:
    """HTTP session for dealer with authentication state."""

    def __init__(self, client: httpx.Client, login_cfg: DealerLoginConfig | None):
        self.client = client
        self.login_cfg = login_cfg

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()


def env_value(name: str | None) -> str:
    """Get environment variable value or empty string.

    Args:
        name: Environment variable name

    Returns:
        Environment variable value or empty string
    """
    if not name:
        return ""
    return os.getenv(name, "").strip()


def login_mode(cfg: DealerConfig) -> str | None:
    """Determine login mode for dealer configuration.

    Args:
        cfg: Dealer configuration

    Returns:
        Login mode string or None
    """
    if cfg.login:
        return cfg.login.mode
    if cfg.auth.mode_env:
        mode = os.getenv(cfg.auth.mode_env, "").strip().lower()
        return mode or None
    return None


def build_http_client() -> httpx.Client:
    """Build HTTP client with standard configuration.

    Returns:
        Configured httpx.Client
    """
    headers = {"User-Agent": "BikeCopilotBot/0.1"}
    return httpx.Client(
        timeout=15.0, headers=headers, follow_redirects=True, verify=True
    )


def build_dealer_session(cfg: DealerConfig) -> DealerSession:
    """Build authenticated dealer session.

    Args:
        cfg: Dealer configuration

    Returns:
        Authenticated DealerSession

    Raises:
        typer.BadParameter: If authentication fails
    """
    client = build_http_client()
    mode = login_mode(cfg)
    username = env_value(cfg.auth.username_env)
    password = env_value(cfg.auth.password_env)
    cookie = env_value(cfg.auth.cookie_env)

    if mode == "cookie":
        apply_cookie_auth(client, cfg, cookie)
    elif mode == "basic":
        apply_basic_auth(client, cfg, username, password)
    elif mode == "form":
        perform_form_login(client, cfg, username, password)
    elif mode == "spa":
        perform_spa_login(client, cfg, username, password)
    return DealerSession(client, cfg.login)


def apply_cookie_auth(
    client: httpx.Client, cfg: DealerConfig, cookie: str | None
) -> None:
    """Apply cookie-based authentication.

    Args:
        client: HTTP client to configure
        cfg: Dealer configuration
        cookie: Cookie value

    Raises:
        typer.BadParameter: If cookie is missing
    """
    if not cookie:
        raise typer.BadParameter(
            f"Nessun cookie impostato per {cfg.name}; definisci {cfg.auth.cookie_env}."
        )
    client.headers["Cookie"] = cookie


def apply_basic_auth(
    client: httpx.Client,
    cfg: DealerConfig,
    username: str | None,
    password: str | None,
) -> None:
    """Apply HTTP basic authentication.

    Args:
        client: HTTP client to configure
        cfg: Dealer configuration
        username: Username
        password: Password

    Raises:
        typer.BadParameter: If credentials are missing
    """
    if not username or not password:
        raise typer.BadParameter(
            f"Credenziali mancanti per {cfg.name}; definisci {cfg.auth.username_env} e {cfg.auth.password_env}."
        )
    client.auth = (username, password)  # type: ignore[assignment]


def require_login_cfg(cfg: DealerConfig) -> DealerLoginConfig:
    """Require login configuration to be present.

    Args:
        cfg: Dealer configuration

    Returns:
        Login configuration

    Raises:
        typer.BadParameter: If login config is missing
    """
    if not cfg.login:
        raise typer.BadParameter(
            f"Configurazione login mancante per {cfg.name} (section login in providers/dealers.yaml)."
        )
    if not cfg.login.url:
        raise typer.BadParameter(f"login.url non impostato per {cfg.name}.")
    return cfg.login


def perform_preflight(
    client: httpx.Client, cfg: DealerConfig, login_cfg: DealerLoginConfig
) -> None:
    """Perform preflight request if configured.

    Args:
        client: HTTP client
        cfg: Dealer configuration
        login_cfg: Login configuration

    Raises:
        typer.BadParameter: If preflight fails
    """
    if not login_cfg.preflight_url:
        return
    pre_resp = client.get(login_cfg.preflight_url)
    if pre_resp.status_code >= 400:
        raise typer.BadParameter(
            f"Preflight fallito per {cfg.name}: HTTP {pre_resp.status_code}"
        )
    client.headers["Referer"] = login_cfg.preflight_url


def ensure_credentials(
    cfg: DealerConfig, username: str | None, password: str | None
) -> None:
    """Ensure credentials are present.

    Args:
        cfg: Dealer configuration
        username: Username
        password: Password

    Raises:
        typer.BadParameter: If credentials are missing
    """
    if not username or not password:
        raise typer.BadParameter(
            f"Credenziali mancanti per {cfg.name}; definisci {cfg.auth.username_env} e {cfg.auth.password_env}."
        )


def build_login_payload_items(
    login_cfg: DealerLoginConfig, username: str, password: str
) -> list[tuple[str, str]]:
    """Build form login payload items.

    Args:
        login_cfg: Login configuration
        username: Username
        password: Password

    Returns:
        List of (field_name, value) tuples
    """
    items: list[tuple[str, str]] = list((login_cfg.extra_fields or {}).items())
    user_field = login_cfg.username_field or ""
    pass_field = login_cfg.password_field or ""
    if user_field:
        items.append((user_field, username))
    if pass_field:
        items.append((pass_field, password))
    return items


def submit_form_login_request(
    client: httpx.Client,
    cfg: DealerConfig,
    login_cfg: DealerLoginConfig,
    payload_items: list[tuple[str, str]],
) -> httpx.Response:
    """Submit form login request.

    Args:
        client: HTTP client
        cfg: Dealer configuration
        login_cfg: Login configuration
        payload_items: Form fields

    Returns:
        HTTP response

    Raises:
        typer.BadParameter: If unsupported method
    """
    method = (login_cfg.method or "POST").upper()
    url = login_cfg.url or ""
    if method == "POST":
        encoding = (login_cfg.encoding or "form").lower()
        if encoding == "multipart":
            files = [(k, (None, v)) for k, v in payload_items]
            return client.post(url, files=files)
        form_data = dict(payload_items)
        return client.post(url, data=form_data)
    if method == "GET":
        query_params = dict(payload_items)
        return client.get(url, params=query_params)
    raise typer.BadParameter(f"Metodo login {method} non supportato per {cfg.name}.")


def perform_form_login(
    client: httpx.Client,
    cfg: DealerConfig,
    username: str | None,
    password: str | None,
) -> None:
    """Perform form-based login.

    Args:
        client: HTTP client
        cfg: Dealer configuration
        username: Username
        password: Password

    Raises:
        typer.BadParameter: If login fails
    """
    login_cfg = require_login_cfg(cfg)
    ensure_credentials(cfg, username, password)
    perform_preflight(client, cfg, login_cfg)

    payload_items = build_login_payload_items(login_cfg, username or "", password or "")
    resp = submit_form_login_request(client, cfg, login_cfg, payload_items)
    if resp.status_code >= 400:
        raise typer.BadParameter(
            f"Login fallito per {cfg.name}: HTTP {resp.status_code}"
        )


def build_spa_payload(
    login_cfg: DealerLoginConfig,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Build SPA login JSON payload.

    Args:
        login_cfg: Login configuration
        username: Username
        password: Password

    Returns:
        JSON payload dictionary
    """
    import base64

    payload: dict[str, Any] = dict(login_cfg.extra_fields or {})

    # Encode credentials if configured
    if login_cfg.encode_base64:
        username = base64.b64encode(username.encode()).decode()
        password = base64.b64encode(password.encode()).decode()

    if login_cfg.username_field:
        payload[login_cfg.username_field] = username
    if login_cfg.password_field:
        payload[login_cfg.password_field] = password
    return payload


def submit_spa_login_request(
    client: httpx.Client,
    login_cfg: DealerLoginConfig,
    payload: dict[str, Any],
) -> httpx.Response:
    """Submit SPA login request.

    Args:
        client: HTTP client
        login_cfg: Login configuration
        payload: JSON payload

    Returns:
        HTTP response
    """
    client.headers["Content-Type"] = "application/json"
    url = login_cfg.url or ""
    return client.post(url, json=payload)


def extract_spa_token(resp: httpx.Response) -> str | None:
    """Extract authentication token from SPA login response.

    Args:
        resp: HTTP response

    Returns:
        Token string or None
    """
    try:
        auth_data = resp.json()
    except ValueError:
        # Non-JSON response: fall back to cookies/session state.
        return None
    if not isinstance(auth_data, dict):
        # Unexpected JSON shape: do not fail dealer sync; just skip token extraction.
        return None
    token = auth_data.get("token") or auth_data.get("access_token")
    if isinstance(token, str) and token:
        return token
    return None


def perform_spa_login(
    client: httpx.Client,
    cfg: DealerConfig,
    username: str | None,
    password: str | None,
) -> None:
    """Perform SPA-based login.

    Args:
        client: HTTP client
        cfg: Dealer configuration
        username: Username
        password: Password

    Raises:
        typer.BadParameter: If login fails
    """
    login_cfg = require_login_cfg(cfg)
    ensure_credentials(cfg, username, password)
    perform_preflight(client, cfg, login_cfg)

    payload = build_spa_payload(login_cfg, username or "", password or "")
    resp = submit_spa_login_request(client, login_cfg, payload)
    if resp.status_code >= 400:
        raise typer.BadParameter(
            f"Login SPA fallito per {cfg.name}: HTTP {resp.status_code}"
        )

    token = extract_spa_token(resp)
    if token:
        client.headers["Authorization"] = f"Bearer {token}"


# --- Dealer Sync Helpers ---


def require_dealer_cfg(dealer: str) -> DealerConfig:
    """Find and require dealer configuration.

    Args:
        dealer: Dealer key or name

    Returns:
        Dealer configuration

    Raises:
        typer.BadParameter: If dealer not found
    """
    cfg = find_dealer(dealer)
    if cfg is None:
        raise typer.BadParameter(
            f"Dealer '{dealer}' non trovato in providers/dealers.yaml"
        )
    return cfg


def print_dealer_intro(cfg: DealerConfig) -> None:
    """Print dealer introduction message.

    Args:
        cfg: Dealer configuration
    """
    rich.print(
        f"[bold]Dealer[/bold]: {cfg.name} (tipo={cfg.type}, platform={cfg.platform})"
    )


def sync_dealer_policy_if_needed(
    cfg: DealerConfig, mode_l: str, session: DealerSession
) -> None:
    """Sync dealer policy if mode requires it.

    Args:
        cfg: Dealer configuration
        mode_l: Sync mode (all, policy, catalogo)
        session: Authenticated dealer session
    """
    if mode_l not in ("all", "policy") or not cfg.policy_url:
        return
    rich.print(f"[cyan]Scarico policy da[/cyan] {cfg.policy_url}")
    r = session.client.get(cfg.policy_url)
    r.raise_for_status()
    ext = parse_policy_html(r.text)
    create_all()
    with SessionLocal() as db:
        upsert_dealer_policy(db, cfg.name, ext)
    rich.print(
        {
            "dealer": cfg.name,
            "base_cost": ext.base_cost,
            "free_threshold": ext.free_threshold,
            "lead_days_std": ext.lead_days_std,
            "confidence": ext.confidence,
        }
    )


def can_sync_catalog(
    cfg: DealerConfig,
    mode_l: str,
    mapping_path: Path | None,
) -> bool:
    """Check if catalog sync is possible.

    Args:
        cfg: Dealer configuration
        mode_l: Sync mode
        mapping_path: Path to mapping YAML

    Returns:
        True if catalog sync is possible
    """
    if mode_l not in ("all", "catalogo"):
        return False
    if cfg.type != "web":
        rich.print(
            f"[yellow]Tipo '{cfg.type}' non ancora supportato per ingest automatico[/yellow]"
        )
        return False
    if not cfg.mapping or mapping_path is None:
        rich.print(
            "[yellow]Nessun mapping configurato per questo dealer (campo 'mapping' mancante).[/yellow]"
        )
        return False
    return True


def collect_dealer_urls(
    cfg: DealerConfig,
    session: DealerSession,
    parse_sitemap_urls: ParseSitemapFn,
) -> list[str]:
    """Collect all dealer URLs from seeds and sitemaps.

    Args:
        cfg: Dealer configuration
        session: Authenticated dealer session
        parse_sitemap_urls: Sitemap parser function

    Returns:
        List of product URLs
    """
    urls: list[str] = []
    urls.extend(cfg.seeds.urls)
    if cfg.seeds.sitemap:
        rich.print(f"[cyan]Leggo sitemap[/cyan] {cfg.seeds.sitemap}")
        more = parse_sitemap_urls(cfg.seeds.sitemap, None, None, session.client)
        urls.extend(more)
    return urls


def dealer_progress_cb(
    page_url: str,
    page_idx: int,
    products_total: int,
    offers_total: int,
) -> None:
    """Progress callback for dealer catalog ingestion.

    Args:
        page_url: Current page URL
        page_idx: Page index
        products_total: Total products found
        offers_total: Total offers found
    """
    parsed = urlparse(page_url)
    params = parse_qs(parsed.query or "")
    page_hint = params.get("page", [""])[0] or params.get("skip", [""])[0]
    label = page_hint or str(page_idx)
    location = parsed.path or page_url
    rich.print(
        f"[dim]  ↳ pagina {label} ({location}) "
        f"prodotti={products_total} offerte={offers_total}[/dim]"
    )


def run_dealer_catalog_ingest(
    cfg: DealerConfig,
    urls: list[str],
    mapping_path: Path,
    session: DealerSession,
    max_pages: int,
    delay: float,
    fetch_and_parse_urls: Callable,
) -> None:
    """Run dealer catalog ingestion.

    Args:
        cfg: Dealer configuration
        urls: List of URLs to ingest
        mapping_path: Path to mapping YAML
        session: Authenticated dealer session
        max_pages: Maximum pages to follow
        delay: Delay between requests
        fetch_and_parse_urls: URL fetching function
    """
    rich.print(f"[cyan]Ingest catalogo[/cyan] da {len(urls)} seed")

    products, offers = fetch_and_parse_urls(
        urls=urls,
        mapping_yaml=mapping_path,
        follow_next=True,
        max_pages=max_pages,
        delay_sec=delay,
        headers=None,
        session=session.client,
        progress_cb=dealer_progress_cb,
    )
    stats: IngestStats = upsert(products, offers)
    rich.print(
        {
            "dealer": cfg.name,
            "products_new": stats.products_new,
            "products_updated": stats.products_updated,
            "offers_upserted": stats.offers_upserted,
            "offers_skipped": stats.offers_skipped,
        }
    )


def sync_dealer_catalog_if_needed(
    cfg: DealerConfig,
    mode_l: str,
    session: DealerSession,
    max_pages: int,
    delay: float,
    mapping_path: Path | None,
) -> None:
    """Sync dealer catalog if mode requires it.

    Args:
        cfg: Dealer configuration
        mode_l: Sync mode
        session: Authenticated dealer session
        max_pages: Maximum pages to follow
        delay: Delay between requests
        mapping_path: Path to mapping YAML
    """
    if not can_sync_catalog(cfg, mode_l, mapping_path):
        return
    from ..adapters.web_adapter import (
        fetch_and_parse_urls,
        parse_sitemap_urls,
    )

    urls = collect_dealer_urls(cfg, session, parse_sitemap_urls)
    if not urls:
        rich.print(
            "[yellow]Nessun URL seed configurato per il dealer; salta ingest catalogo.[/yellow]"
        )
        return
    if mapping_path is None:
        raise typer.BadParameter("Path mapping mancante per ingest catalogo")
    run_dealer_catalog_ingest(
        cfg, urls, mapping_path, session, max_pages, delay, fetch_and_parse_urls
    )
