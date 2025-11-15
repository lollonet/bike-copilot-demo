#!/usr/bin/env python3
import os
import re
from pathlib import Path
import yaml

REQ_RE = re.compile(r"(REQ-[0-9]{3,})")
MATRIX_PATH = Path("traceability/matrix.yaml").resolve()
SKIP_DIRS = {".git", ".venv", ".cache", "node_modules", "dist", "build", "traceability"}
TEXT_EXT = {
    ".md",
    ".yml",
    ".yaml",
    ".json",
    ".py",
    ".ts",
    ".js",
    ".java",
    ".go",
    ".rb",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".sh",
    ".tf",
    ".sql",
    ".kt",
    ".rs",
    ".php",
    ".scala",
    ".rst",
    ".tex",
    ".ini",
    ".cfg",
    ".toml",
}


def iter_candidate_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            p = Path(base) / fn
            if p.suffix.lower() in TEXT_EXT and p.resolve() != MATRIX_PATH:
                out.append(p)
    return out


def is_test_path(p: Path) -> bool:
    return "tests" in p.parts


def index_req_ids(paths: list[Path]) -> dict[str, dict[str, list[str]]]:
    raw_idx: dict[str, dict[str, set[str]]] = {}
    for p in paths:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for m in set(REQ_RE.findall(txt)):
            d = raw_idx.setdefault(m, {"files": set(), "tests": set()})
            target = "tests" if is_test_path(p) else "files"
            d[target].add(str(p))
    idx: dict[str, dict[str, list[str]]] = {}
    for req_id, data in raw_idx.items():
        idx[req_id] = {
            "files": sorted(data["files"]),
            "tests": sorted(data["tests"]),
        }
    return idx


def main() -> None:
    files = iter_candidate_files(Path("."))
    mapping = index_req_ids(files)
    out = {
        k: {"files": v["files"], "tests": v["tests"], "prs": [], "commits": []}
        for k, v in sorted(mapping.items())
    }  # type: ignore[index]
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_PATH.write_text(
        yaml.safe_dump(out, sort_keys=True, allow_unicode=True), encoding="utf-8"
    )
    print(
        f"[traceability] updated traceability/matrix.yaml with {len(out)} REQ entries"
    )


if __name__ == "__main__":
    main()
