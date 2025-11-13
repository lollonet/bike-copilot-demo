#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Iterable

import yaml


@dataclass
class Thresholds:
    mccabe_warn: int
    mccabe_fail: int
    cog_warn: int
    cog_fail: int
    loc_warn: int
    loc_fail: int


EXCLUDE_DIRS = [
    ".git",
    ".venv",
    ".cache",
    "dist",
    "build",
    ".ruff_cache",
    "node_modules",
]


def read_control(path: Path) -> tuple[Thresholds, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cplx = data.get("complexity", {})
    mccabe = cplx.get("mccabe", {})
    cognitive = cplx.get("cognitive", {})
    loc = cplx.get("func_loc", {})
    paths = cplx.get("paths", ["src", "scripts"]) or ["src", "scripts"]
    th = Thresholds(
        mccabe_warn=int(mccabe.get("warn", 8)),
        mccabe_fail=int(mccabe.get("fail", 12)),
        cog_warn=int(cognitive.get("warn", 12)),
        cog_fail=int(cognitive.get("fail", 15)),
        loc_warn=int(loc.get("warn", 25)),
        loc_fail=int(loc.get("fail", 30)),
    )
    return th, paths


def existing_paths(paths: Iterable[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        if Path(p).exists():
            out.append(p)
    if not out:
        out = ["."]
    return out


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command with uv tool caches confined to the workspace.

    This avoids permission issues on CI/sandboxes and ensures deterministic paths.
    """
    env = os.environ.copy()
    root = Path.cwd()
    env.setdefault("UV_CACHE_DIR", str(root / ".uv-cache"))
    env.setdefault("UV_TOOL_DIR", str(root / ".uv-tools"))
    env.setdefault("UV_PYTHON_INSTALL_DIR", str(root / ".uv-cache" / "python"))
    env.setdefault("XDG_CACHE_HOME", str(root / ".uv-cache"))
    return subprocess.run(
        cmd, text=True, capture_output=True, check=False, env=env
    )


def radon_cc(paths: list[str]) -> dict[str, list[dict[str, Any]]]:
    # JSON output includes endline for block LOC calc
    exclude = ",".join(f"*/{d}/*" for d in EXCLUDE_DIRS)
    cmd = [
        "uvx",
        "radon",
        "cc",
        "-s",
        "-j",
        "-e",
        exclude,
        *paths,
    ]
    res = run(cmd)
    if res.returncode not in (0, 1):
        print("[complexity] radon cc failed:\n" + res.stderr.strip())
        sys.exit(2)
    try:
        return json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        print("[complexity] failed to parse radon cc JSON output")
        sys.exit(2)


def _flake8_cmd(paths: list[str], warn_cog: int) -> list[str]:
    """Build flake8 command for cognitive-complexity WARN threshold."""
    exclude = ",".join(EXCLUDE_DIRS)
    return [
        "uvx",
        "--from",
        "flake8",
        "--with",
        "flake8-cognitive-complexity",
        "flake8",
        f"--max-cognitive-complexity={warn_cog}",
        "--select",
        "CCR",
        "--exclude",
        exclude,
        *paths,
    ]
<<<<<<< HEAD
    res = run(cmd)
    text = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
    # Keep only plugin violation lines (contain CCR)
    lines = [l for l in text.splitlines() if "CCR" in l]
    if res.returncode not in (0, 1) or (res.returncode != 0 and not lines):
        details = text.strip() or "(no output)"
        print("[complexity] flake8 cognitive-complexity failed:\n" + details)
        sys.exit(2)
    # Parse "(X > Y)" and split
=======


def _only_cog_lines(text: str) -> list[str]:
    """Extract only plugin violation lines containing the CCR code."""
    return [l for l in text.splitlines() if "CCR" in l]


def _split_warn_fail(lines: list[str], fail_cog: int) -> tuple[list[str], list[str]]:
    """Split lines into (warn, fail) by parsing "(X > Y)" numbers."""
>>>>>>> 50b13b1 (REQ-001: complexity gate — usa cache uv locale e riduci divergenze CI; confermato PASS su 'src scripts')
    import re

    warn_lines: list[str] = []
    fail_lines: list[str] = []
    pat = re.compile(r"\((\d+)\s*>\s*(\d+)\)")
    for l in lines:
        m = pat.search(l)
        if not m:
            warn_lines.append(l)
            continue
        lvl = int(m.group(1))
        if lvl > fail_cog:
            fail_lines.append(l)
        else:
            warn_lines.append(l)
    return warn_lines, fail_lines


def flake8_cognitive_both(
    paths: list[str], warn_cog: int, fail_cog: int
) -> tuple[list[str], list[str]]:
    """Run flake8 once and return (warn_lines, fail_lines)."""
    res = run(_flake8_cmd(paths, warn_cog))
    text = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
    lines = _only_cog_lines(text)
    if res.returncode not in (0, 1) or (res.returncode != 0 and not lines):
        details = text.strip() or "(no output)"
        print("[complexity] flake8 cognitive-complexity failed:\n" + details)
        sys.exit(2)
    return _split_warn_fail(lines, fail_cog)


def _summarize_cc(
    cc: dict[str, list[dict[str, Any]]], th: Thresholds
) -> tuple[list[str], list[str], list[str], list[str]]:
    mccabe_warn: list[str] = []
    mccabe_fail: list[str] = []
    loc_warn: list[str] = []
    loc_fail: list[str] = []
    def add_mccabe(ident: str, complexity: int) -> None:
        if complexity > th.mccabe_fail:
            mccabe_fail.append(f"{ident} McCabe={complexity} > {th.mccabe_fail}")
        elif complexity >= th.mccabe_warn:
            mccabe_warn.append(f"{ident} McCabe={complexity} ≥ {th.mccabe_warn}")

    def add_loc(ident: str, loc: int) -> None:
        if loc > th.loc_fail:
            loc_fail.append(f"{ident} LOC≈{loc} > {th.loc_fail}")
        elif loc >= th.loc_warn:
            loc_warn.append(f"{ident} LOC≈{loc} ≥ {th.loc_warn}")

    for file, blocks in cc.items():
        for b in blocks:
            complexity = int(b.get("complexity", 0))
            lineno = int(b.get("lineno", 0))
            endline = int(b.get("endline", lineno))
            loc = max(0, endline - lineno + 1)
            ident = f"{file}:{lineno} {b.get('type', 'func')} {b.get('name', '?')}"
            add_mccabe(ident, complexity)
            add_loc(ident, loc)
    return mccabe_warn, mccabe_fail, loc_warn, loc_fail


def _format_sections(
    m_warn: list[str],
    m_fail: list[str],
    l_warn: list[str],
    l_fail: list[str],
    cog_warn_lines: list[str],
    cog_fail_lines: list[str],
) -> list[str]:
    out: list[str] = []

    def add(label: str, items: list[str]) -> None:
        if items:
            out.append(label)
            out.extend("- " + x for x in items)

    add("[McCabe WARN]", m_warn)
    add("[LOC WARN]", l_warn)
    add("[Cognitive WARN]", cog_warn_lines)
    if cog_fail_lines:
        add("[Cognitive FAIL] violations:", cog_fail_lines)
    add("[McCabe FAIL]", m_fail)
    add("[LOC FAIL]", l_fail)
    return out


def evaluate(th: Thresholds, targets: list[str]) -> tuple[bool, list[str]]:
    cc = radon_cc(targets)
    m_warn, m_fail, l_warn, l_fail = _summarize_cc(cc, th)
    cog_warn_lines, cog_fail_lines = flake8_cognitive_both(
        targets, th.cog_warn, th.cog_fail
    )
    out = _format_sections(
        m_warn, m_fail, l_warn, l_fail, cog_warn_lines, cog_fail_lines
    )
    return bool(m_fail or l_fail or cog_fail_lines), out


def main() -> None:
    parser = argparse.ArgumentParser(description="Repository-wide complexity gate")
    parser.add_argument("--paths", nargs="*", default=None, help="paths to analyze")
    args = parser.parse_args()

    control = Path("CONTROL.yaml")
    if not control.exists():
        print("[complexity] CONTROL.yaml not found")
        sys.exit(2)

    th, control_paths = read_control(control)
    targets = existing_paths(args.paths or control_paths)
    has_fail, lines = evaluate(th, targets)
    if lines:
        print("\n" + "\n".join(lines))
    if has_fail:
        print("\n[complexity] Gate failed.")
        sys.exit(1)
    print("[complexity] Gate passed.")


if __name__ == "__main__":
    main()
