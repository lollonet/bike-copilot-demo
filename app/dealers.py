"""Dealer registry loader.

This module reads providers/dealers.yaml and exposes typed configurations
for higher-level CLI commands (dealer-sync, dealer-snapshot).
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
class DealerLoginConfig:
    mode: str
    url: str | None = None
    method: str = "POST"
    username_field: str | None = None
    password_field: str | None = None
    extra_fields: dict[str, Any] = field(
        default_factory=dict
    )  # Preserve YAML types (bool, int, str, etc.)
    preflight_url: str | None = None
    encoding: str = "form"  # form | multipart
    encode_base64: bool = False  # Base64-encode username and password


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
    login: DealerLoginConfig | None


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
    entries = _dealer_entries(raw)
    return [_build_dealer_config(entry) for entry in entries]


def _dealer_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    dealers_raw = raw.get("dealers", [])
    if not isinstance(dealers_raw, list):
        raise ValueError("dealers must be a list in providers/dealers.yaml")
    entries: list[dict[str, Any]] = []
    for entry in dealers_raw:
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _build_dealer_config(entry: dict[str, Any]) -> DealerConfig:
    key, name, dtype, base_url_env, platform, mapping, policy_url = _dealer_base_fields(
        entry
    )
    auth = _dealer_auth(entry)
    seeds = _dealer_seeds(entry)
    login_cfg = _dealer_login(entry)
    return DealerConfig(
        key=key,
        name=name or key,
        type=dtype,
        base_url_env=base_url_env,
        platform=platform,
        mapping=mapping,
        policy_url=policy_url,
        auth=auth,
        seeds=seeds,
        login=login_cfg,
    )


def _dealer_base_fields(
    entry: dict[str, Any],
) -> tuple[str, str, str, str | None, str | None, str | None, str | None]:
    key = _str_or_empty(entry.get("key"))
    name = _str_or_empty(entry.get("name") or key)
    dtype = _str_or_empty(entry.get("type") or "web")
    base_url_env = _optional_str(entry.get("base_url_env"))
    platform = _optional_str(entry.get("platform"))
    mapping = _optional_str(entry.get("mapping"))
    policy_url = _optional_str(entry.get("policy_url"))
    return key, name, dtype, base_url_env, platform, mapping, policy_url


def _dealer_auth(entry: dict[str, Any]) -> DealerAuthConfig:
    auth_raw = entry.get("auth") or {}
    mode_env = _optional_str(auth_raw.get("mode_env"))  # type: ignore[union-attr]
    username_env = _optional_str(auth_raw.get("username_env"))  # type: ignore[union-attr]
    password_env = _optional_str(auth_raw.get("password_env"))  # type: ignore[union-attr]
    cookie_env = _optional_str(auth_raw.get("cookie_env"))  # type: ignore[union-attr]
    return DealerAuthConfig(
        mode_env=mode_env,
        username_env=username_env,
        password_env=password_env,
        cookie_env=cookie_env,
    )


def _dealer_seeds(entry: dict[str, Any]) -> DealerSeeds:
    seeds_raw = entry.get("seeds") or {}
    urls_raw = seeds_raw.get("urls") or []  # type: ignore[union-attr]
    urls: list[str] = []
    if isinstance(urls_raw, list):
        for u in urls_raw:
            urls.append(str(u))
    sitemap = (
        str(seeds_raw.get("sitemap") or "").strip() or None  # type: ignore[union-attr]
    )
    return DealerSeeds(urls=urls, sitemap=sitemap)


def _dealer_login(entry: dict[str, Any]) -> DealerLoginConfig | None:
    login_raw = entry.get("login") or {}
    if not isinstance(login_raw, dict) or not login_raw.get("mode"):
        return None
    extra_fields = _dealer_login_extra_fields(login_raw)
    return DealerLoginConfig(
        mode=_str_or_empty(login_raw.get("mode")).lower(),
        url=_optional_str(login_raw.get("url")),
        method=_str_or_empty(login_raw.get("method") or "POST").upper(),
        username_field=_optional_str(login_raw.get("username_field")),
        password_field=_optional_str(login_raw.get("password_field")),
        extra_fields=extra_fields,
        preflight_url=_optional_str(login_raw.get("preflight_url")),
        encoding=(_str_or_empty(login_raw.get("encoding") or "form")).lower() or "form",
    )


def _dealer_login_extra_fields(login_raw: dict[str, Any]) -> dict[str, Any]:
    extra_fields_raw = login_raw.get("extra_fields") or {}
    extra_fields: dict[str, Any] = {}
    if isinstance(extra_fields_raw, dict):
        for k, v in extra_fields_raw.items():
            extra_fields[str(k)] = v
    return extra_fields


def _str_or_empty(value: Any) -> str:
    return str(value or "").strip()


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def find_dealer(key: str) -> DealerConfig | None:
    target = key.strip().lower()
    for d in load_dealers():
        if d.key.lower() == target or d.name.lower() == target:
            return d
    return None
