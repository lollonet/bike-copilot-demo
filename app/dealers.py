from __future__ import annotations

"""Dealer registry loader.

This module reads providers/dealers.yaml and exposes typed configurations
for higher-level CLI commands (dealer-sync, dealer-snapshot).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DealerAuthConfig:
    mode_env: str | None
    username_env: str | None
    password_env: str | None
    cookie_env: str | None


@dataclass(frozen=True)
class DealerSeeds:
    urls: list[str]
    sitemap: str | None


@dataclass(frozen=True)
class DealerConfig:
    key: str
    name: str
    type: str  # web|csv|pdf (per ora supportiamo web)
    base_url_env: str | None
    platform: str | None
    mapping: str | None
    policy_url: str | None
    auth: DealerAuthConfig
    seeds: DealerSeeds


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dealers_yaml_path() -> Path:
    return _repo_root() / "providers" / "dealers.yaml"


def _load_raw() -> dict[str, Any]:
    path = _dealers_yaml_path()
    if not path.is_file():
        return {"dealers": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("providers/dealers.yaml root must be a mapping")
    return data


def load_dealers() -> list[DealerConfig]:
    raw = _load_raw()
    dealers_raw = raw.get("dealers", [])
    dealers: list[DealerConfig] = []
    if not isinstance(dealers_raw, list):
        raise ValueError("dealers must be a list in providers/dealers.yaml")
    for entry in dealers_raw:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        name = str(entry.get("name") or key or "").strip()
        dtype = str(entry.get("type") or "web").strip()
        base_url_env = str(entry.get("base_url_env") or "").strip() or None
        platform = str(entry.get("platform") or "").strip() or None
        mapping = str(entry.get("mapping") or "").strip() or None
        policy_url = str(entry.get("policy_url") or "").strip() or None

        auth_raw = entry.get("auth") or {}
        mode_env = str(auth_raw.get("mode_env") or "").strip() or None  # type: ignore[union-attr]
        username_env = (
            str(auth_raw.get("username_env") or "").strip() or None  # type: ignore[union-attr]
        )
        password_env = (
            str(auth_raw.get("password_env") or "").strip() or None  # type: ignore[union-attr]
        )
        cookie_env = (
            str(auth_raw.get("cookie_env") or "").strip() or None  # type: ignore[union-attr]
        )
        auth = DealerAuthConfig(
            mode_env=mode_env,
            username_env=username_env,
            password_env=password_env,
            cookie_env=cookie_env,
        )

        seeds_raw = entry.get("seeds") or {}
        urls_raw = seeds_raw.get("urls") or []  # type: ignore[union-attr]
        urls: list[str] = []
        if isinstance(urls_raw, list):
            for u in urls_raw:
                urls.append(str(u))
        sitemap = str(seeds_raw.get("sitemap") or "").strip() or None  # type: ignore[union-attr]
        seeds = DealerSeeds(urls=urls, sitemap=sitemap)

        dealers.append(
            DealerConfig(
                key=key,
                name=name or key,
                type=dtype,
                base_url_env=base_url_env,
                platform=platform,
                mapping=mapping,
                policy_url=policy_url,
                auth=auth,
                seeds=seeds,
            )
        )
    return dealers


def find_dealer(key: str) -> DealerConfig | None:
    target = key.strip().lower()
    for d in load_dealers():
        if d.key.lower() == target or d.name.lower() == target:
            return d
    return None

