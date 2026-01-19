#!/usr/bin/env bash
# Local CI validation script - runs same checks as GitHub Actions CI
# Run this before pushing to ensure CI will pass

set -e  # Exit on first error

echo "========================================="
echo "🔍 Running Local CI Validation"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

failed_checks=()

# Function to run check and track failures
run_check() {
    local check_name="$1"
    shift
    echo -e "${YELLOW}▶ ${check_name}...${NC}"
    if "$@"; then
        echo -e "${GREEN}✓ ${check_name} passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ ${check_name} FAILED${NC}"
        echo ""
        failed_checks+=("$check_name")
        return 1
    fi
}

# 1. Lint with ruff
run_check "Ruff lint" uv run ruff check app/ tests/ bin/ || true

# 2. Check formatting with ruff
run_check "Ruff format check" uv run ruff format --check app/ tests/ bin/ || true

# 3. Type check with basedpyright
run_check "Basedpyright type check" uv run basedpyright app/ bin/ || true

# 4. Run tests with pytest
run_check "Pytest" uv run pytest -v --tb=short tests/ || true

# 5. Complexity gate (on scripts)
run_check "Complexity gate (scripts)" uv run python scripts/complexity_gate.py --paths scripts || true

# 6. Spec lint
run_check "Spec lint" uv run python scripts/spec_lint.py || true

# 7. Traceability
run_check "Traceability" uv run python scripts/traceability.py || true

# 8. Security scan (informational only, matches CI continue-on-error)
echo -e "${YELLOW}▶ Bandit security scan (informational)...${NC}"
uv run bandit -r app/ -ll -ii --format txt || true
echo -e "${GREEN}✓ Bandit scan completed (warnings may exist)${NC}"
echo ""

# Summary
echo "========================================="
echo "📊 Validation Summary"
echo "========================================="

if [ ${#failed_checks[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All CI checks passed!${NC}"
    echo ""
    echo "Safe to push. CI should pass."
    exit 0
else
    echo -e "${RED}❌ ${#failed_checks[@]} check(s) FAILED:${NC}"
    for check in "${failed_checks[@]}"; do
        echo -e "  ${RED}✗${NC} $check"
    done
    echo ""
    echo -e "${YELLOW}⚠️  Fix these issues before pushing to avoid CI failures.${NC}"
    exit 1
fi
