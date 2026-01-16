#!/usr/bin/env python3
import sys
import os
import glob
import io
import yaml

err = 0
REQ_STATUS = {"draft", "approved", "deprecated"}
IDX = yaml.safe_load(open("docs/index.yaml"))


def fm(path):
    with open(path, "r", encoding="utf-8") as f:
        t = f.read()
    if not t.startswith("---\n"):
        return {}
    head = t.split("\n---\n", 1)[0].replace("---\n", "")
    return yaml.safe_load(io.StringIO(head)) or {}


def require(cond, msg):
    global err
    if not cond:
        print(f"[spec-lint] ERROR: {msg}")
        err = 1


ids = set()
for p in [IDX["requirements"], IDX["architecture"], IDX["technology"]]:
    if not os.path.exists(p):
        require(False, f"Missing SSoT file: {p}")
# Scan docs
for path in glob.glob("docs/**/*.md", recursive=True):
    if "/standards/" in path or "/api/" in path:
        continue
    meta = fm(path)
    require(meta.get("id"), f"Missing id in {path}")
    if "id" in meta:
        if meta["id"] in ids:
            require(False, f"Duplicate id {meta['id']} in {path}")
        ids.add(meta["id"])
    dom = meta.get("domain")
    # Allowed domains:
    #   requirements - REQ-### files (product/feature requirements)
    #   architecture - ARC-### files (system design, diagrams)
    #   technology   - TECH-### files (stack, dependencies, schema)
    #   decisions    - ADR-### files (architecture decision records)
    #   api          - API documentation (examples, contracts)
    #   docs         - General documentation (traceability, guides)
    require(
        dom in {"requirements", "architecture", "technology", "decisions", "api", "docs"},
        f"Bad domain in {path}",
    )
    if dom == "requirements":
        if meta.get("status") not in REQ_STATUS:
            require(False, f"Bad status in {path}")
        if not meta.get("acceptance"):
            require(False, f"Missing acceptance in {path}")
# No-overlap: id prefix vs domain
for path in glob.glob("docs/**/*.md", recursive=True):
    if "/standards/" in path or "/api/" in path:
        continue
    meta = fm(path)
    i = meta.get("id", "")
    d = meta.get("domain", "")
    if d == "requirements":
        require(i.startswith("REQ-"), f"ID {i} must start with REQ-")
    if d == "architecture":
        require(
            i.startswith("ARC-") or i == "ARC-INDEX", f"ID {i} must start with ARC-"
        )
    if d == "technology":
        require(
            i.startswith("TECH-") or i == "TECH-INDEX", f"ID {i} must start with TECH-"
        )
    if d == "decisions":
        require(i.startswith("ADR-"), f"ID {i} must start with ADR-")
sys.exit(err)
