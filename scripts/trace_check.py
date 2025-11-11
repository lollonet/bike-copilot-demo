#!/usr/bin/env python3
import subprocess
import sys
import re

REQ_RE = re.compile(r"REQ-[0-9]{3,}")
diff = subprocess.run(
    ["git", "diff", "--cached", "-U0"], capture_output=True, text=True
).stdout
added = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
in_src = [l for l in added if re.search(r"^diff --git a/src/", diff, re.M)]
violations = 0
if in_src and not any(REQ_RE.search(l) for l in added):
    print(
        "[trace-check] ERROR: aggiunte in src/ senza tag REQ-### nelle linee inserite."
    )
    violations = 1
sys.exit(violations)
