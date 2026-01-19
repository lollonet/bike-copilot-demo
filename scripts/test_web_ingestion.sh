#!/usr/bin/env bash
set -euo pipefail

# Web Ingestion Integration Test
# Tests complete chain: Fetch → Parse → Ingest → Search

DEALER="${1:-}"
MODE="${2:-all}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_step() {
    echo -e "${BLUE}▶${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

check_credentials() {
    local dealer_key=$1
    local username_var="DEALER_${dealer_key^^}_USERNAME"
    local password_var="DEALER_${dealer_key^^}_PASSWORD"

    if [ -z "${!username_var:-}" ] || [ -z "${!password_var:-}" ]; then
        return 1
    fi
    return 0
}

test_dealer() {
    local dealer=$1
    local mode=$2

    echo ""
    echo "========================================="
    echo "Testing: $dealer"
    echo "Mode: $mode"
    echo "========================================="

    # Check if credentials are available
    if ! check_credentials "$dealer"; then
        log_warning "Credentials not found for $dealer (skipping)"
        log_warning "Set DEALER_${dealer^^}_USERNAME and DEALER_${dealer^^}_PASSWORD"
        return 0
    fi

    log_success "Credentials found"

    # Get baseline count
    log_step "Getting baseline product count..."
    BEFORE=$(uv run python -m app.cli dump-md 2>/dev/null | wc -l || echo "0")
    log_success "Baseline: $BEFORE products"

    # Run dealer sync
    log_step "Running dealer-sync for $dealer (mode: $mode)..."
    if uv run python -m app.cli dealer-sync "$dealer" --mode "$mode" --max-pages 2 --delay 1.0; then
        log_success "Dealer sync completed"
    else
        log_error "Dealer sync failed"
        return 1
    fi

    # Get new count
    log_step "Counting products after sync..."
    AFTER=$(uv run python -m app.cli dump-md 2>/dev/null | wc -l || echo "0")
    ADDED=$((AFTER - BEFORE))

    if [ "$ADDED" -gt 0 ]; then
        log_success "Added $ADDED new products (total: $AFTER)"
    else
        log_warning "No new products added (total: $AFTER)"
    fi

    # Test search functionality
    log_step "Testing search on ingested data..."

    # Try common search terms for bike parts
    local search_terms=("shimano" "campagnolo" "catena" "freno")
    local search_success=false

    for term in "${search_terms[@]}"; do
        RESULTS=$(uv run python -m app.cli search-cli "$term" 2>/dev/null | grep -c "│" || true)
        if [ "$RESULTS" -gt 3 ]; then
            log_success "Search '$term' returned $RESULTS results"
            search_success=true
            break
        fi
    done

    if [ "$search_success" = false ]; then
        log_warning "No search results found for common terms"
    fi

    # Sample products from this dealer
    log_step "Sample products from $dealer:"
    uv run python -c "
import sqlite3
conn = sqlite3.connect('app.db')
cur = conn.cursor()
cur.execute('''
    SELECT p.name, o.price, o.in_stock, o.supplier
    FROM offer o
    JOIN product p ON o.product_id = p.id
    WHERE o.supplier = ?
    LIMIT 5
''', ('${dealer^}',))
for row in cur.fetchall():
    print(f'  • {row[0][:50]:50} | €{row[1]:6.2f} | Stock: {row[2]} | {row[3]}')
conn.close()
" 2>/dev/null || log_warning "Could not sample products"

    echo ""
    log_success "Test completed for $dealer"
    return 0
}

# Main execution
echo ""
echo "╔═══════════════════════════════════════╗"
echo "║   Web Ingestion Integration Test     ║"
echo "╚═══════════════════════════════════════╝"
echo ""

# Check if database exists
if [ ! -f "app.db" ]; then
    log_warning "Database not found - creating..."
    uv run python -m app.cli reset-db
fi

# Test specific dealer or all
if [ -n "$DEALER" ]; then
    # Test single dealer
    test_dealer "$DEALER" "$MODE"
else
    # Test all dealers with credentials
    log_step "Scanning for dealers with credentials..."

    DEALERS=("ciclopromo" "ciclodiffusione" "rms")
    TESTED=0

    for dealer in "${DEALERS[@]}"; do
        if check_credentials "$dealer"; then
            test_dealer "$dealer" "all"
            TESTED=$((TESTED + 1))
        else
            log_warning "Skipping $dealer (no credentials)"
        fi
    done

    echo ""
    echo "========================================="
    echo "Summary: Tested $TESTED dealers"
    echo "========================================="

    if [ "$TESTED" -eq 0 ]; then
        echo ""
        log_error "No dealers tested - credentials missing"
        echo ""
        echo "To test web ingestion, set environment variables:"
        echo "  export DEALER_CICLOPROMO_USERNAME='your-username'"
        echo "  export DEALER_CICLOPROMO_PASSWORD='your-password'"
        echo "  export DEALER_CICLODIFFUSIONE_USERNAME='your-username'"
        echo "  export DEALER_CICLODIFFUSIONE_PASSWORD='your-password'"
        echo "  export DEALER_RMS_USERNAME='your-username'"
        echo "  export DEALER_RMS_PASSWORD='your-password'"
        echo ""
        exit 1
    fi
fi

echo ""
log_success "All tests completed"
