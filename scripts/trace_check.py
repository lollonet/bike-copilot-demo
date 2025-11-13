#!/usr/bin/env python3
import subprocess
import sys
import re

REQ_RE = re.compile(r"REQ-[0-9]{3,}")
diff = subprocess.run(
    ["git", "diff", "--cached", "-U0"], capture_output=True, text=True
).stdout
added = [
    line
    for line in diff.splitlines()
    if line.startswith("+") and not line.startswith("+++")
]
in_src = [line for line in added if re.search(r"^diff --git a/src/", diff, re.M)]
violations = 0
if in_src and not any(REQ_RE.search(line) for line in added):
    print(
        "[trace-check] ERROR: aggiunte in src/ senza tag REQ-### nelle linee inserite."
    )
    violations = 1
sys.exit(violations)
