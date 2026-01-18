---
id: TECH-011
domain: technology
---

# TECH-011: Web Ingestion Integration Testing

Complete guide for testing B2B dealer web scraping and data ingestion.

## Overview

Web ingestion tests the complete chain:
1. **Authenticate** → Login to B2B dealer portal
2. **Fetch** → Download product pages using Playwright/httpx
3. **Parse** → Extract data using CSS selectors (mapping YAML)
4. **Normalize** → Clean and standardize product data
5. **Ingest** → Upsert into SQLite database
6. **Verify** → Search and retrieve ingested data

## Prerequisites

```bash
# Install Playwright for JavaScript-heavy sites
uv sync --extra integration
playwright install chromium

# Set dealer credentials
export DEALER_CICLOPROMO_USERNAME='your-username'
export DEALER_CICLOPROMO_PASSWORD='your-password'
export DEALER_CICLODIFFUSIONE_USERNAME='your-username'
export DEALER_CICLODIFFUSIONE_PASSWORD='your-password'
export DEALER_RMS_USERNAME='your-username'
export DEALER_RMS_PASSWORD='your-password'
```

## Quick Test (Automated)

```bash
# Test all dealers with credentials
chmod +x scripts/test_web_ingestion.sh
./scripts/test_web_ingestion.sh

# Test specific dealer
./scripts/test_web_ingestion.sh ciclopromo all

# Test only policy (shipping rules)
./scripts/test_web_ingestion.sh ciclopromo policy

# Test only catalog (products)
./scripts/test_web_ingestion.sh ciclopromo catalogo
```

## Manual Testing - Step by Step

### Test 1: CicloPromo (Form Login)

**Platform**: Custom Cartzilla
**Login**: Form-based authentication
**Mapping**: `providers/web-ciclopromo.yaml`

```bash
# 1. Reset database
uv run python -m app.cli reset-db

# 2. Sync policy (shipping rules)
uv run python -m app.cli dealer-sync ciclopromo --mode policy

# Verify policy was extracted
sqlite3 app.db "SELECT * FROM dealer_policy WHERE dealer_code = 'ciclopromo';"

# 3. Sync catalog (first 2 pages only for testing)
uv run python -m app.cli dealer-sync ciclopromo --mode catalogo --max-pages 2

# 4. Verify ingestion
uv run python -m app.cli dump-md | grep -i ciclopromo | head -20

# 5. Test search
uv run python -m app.cli search-cli "shimano"
```

**Expected Results**:
- Policy: Free shipping threshold and base cost extracted
- Catalog: 20-100+ products from 2 pages
- Products have: name, brand, mpn, price, stock status
- Search returns CicloPromo products

**Common Issues**:
- Login fails → Check credentials
- No products → Check mapping selectors (website may have changed)
- Slow → Expected for first run (downloads images, builds cache)

---

### Test 2: Ciclodiffusione (StoreDen Platform)

**Platform**: StoreDen
**Login**: REST API authentication
**Mapping**: `providers/web-ciclodiffusione.yaml`

```bash
# 1. Sync with limited pages
uv run python -m app.cli dealer-sync ciclodiffusione --max-pages 2 --delay 1.0

# 2. Verify ingestion
uv run python -m app.cli dump-md | grep -i ciclodiffusione | head -20

# 3. Check specific fields
sqlite3 app.db "
SELECT p.name, p.brand, p.mpn, o.price, o.in_stock
FROM offer o
JOIN product p ON o.product_id = p.id
WHERE o.supplier = 'Ciclodiffusione'
LIMIT 10;
"

# 4. Test search on ingested data
uv run python -m app.cli search-cli "campagnolo"
```

**Expected Results**:
- Products with OpenGraph meta tags properly extracted
- Breadcrumb categories extracted
- Prices from sale tags parsed correctly
- Multiple offers per product (if available)

---

### Test 3: RMS (Angular SPA)

**Platform**: Custom Angular SPA
**Login**: SPA-mode (requires Playwright)
**Mapping**: `providers/web-rms.yaml`
**Challenge**: JavaScript-rendered content

```bash
# 1. Sync RMS (requires Playwright for SPA rendering)
uv run python -m app.cli dealer-sync rms --max-pages 2 --delay 1.5

# 2. Verify products loaded
uv run python -m app.cli dump-md | grep -i rms | head -20

# 3. Check product structure
sqlite3 app.db "
SELECT p.name, p.category, o.price
FROM offer o
JOIN product p ON o.product_id = p.id
WHERE o.supplier = 'RMS'
LIMIT 10;
"
```

**Expected Results**:
- Products from Angular-rendered `.product-card` elements
- Dynamic prices extracted after JavaScript execution
- Categories from SPA navigation

**Common Issues**:
- Timeout errors → Increase `--delay` to 2.0 or higher
- Empty results → SPA needs more time to render, check Playwright logs
- Authentication fails → Verify credentials, check preflight_url

---

## Verification Checklist

After ingestion, verify data quality:

### 1. Product Coverage

```bash
# Count products by supplier
sqlite3 app.db "
SELECT supplier, COUNT(*) as products
FROM offer
GROUP BY supplier;
"
```

### 2. Data Quality

```bash
# Check for missing critical fields
sqlite3 app.db "
SELECT COUNT(*) as missing_name FROM product WHERE name IS NULL OR name = '';
SELECT COUNT(*) as missing_price FROM offer WHERE price IS NULL OR price <= 0;
SELECT COUNT(*) as missing_supplier FROM offer WHERE supplier IS NULL;
"
```

### 3. Search Functionality

```bash
# Search should return results
uv run python -m app.cli search-cli "catena shimano"
uv run python -m app.cli search-cli "freno campagnolo"
uv run python -m app.cli search-cli "ruote"
```

### 4. Quote Generation

```bash
# Find a product with known PN
sqlite3 app.db "
SELECT p.mpn, p.name, o.price, o.supplier
FROM product p
JOIN offer o ON p.id = o.product_id
WHERE p.mpn LIKE '%HG%'
LIMIT 1;
"

# Generate quote with that PN
uv run python -m app.cli quote-cli \
  --pn "CN-HG601-11" \
  --qty 2 \
  --customer "Integration Test"

# Verify quote files created
ls -lh out/quotes/
```

---

## Full Integration Test Script

Run the complete test:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Web Ingestion Full Test"
echo "=========================="

# 1. Setup
echo "Step 1: Reset database"
uv run python -m app.cli reset-db

# 2. Test each dealer
DEALERS=("ciclopromo" "ciclodiffusione" "rms")

for dealer in "${DEALERS[@]}"; do
    echo ""
    echo "Testing $dealer..."

    # Check credentials
    username_var="DEALER_${dealer^^}_USERNAME"
    if [ -z "${!username_var:-}" ]; then
        echo "⚠️  Skipping $dealer (no credentials)"
        continue
    fi

    # Sync dealer (policy + catalog, limit to 2 pages for speed)
    if uv run python -m app.cli dealer-sync "$dealer" --max-pages 2 --delay 1.0; then
        echo "✓ $dealer sync completed"
    else
        echo "✗ $dealer sync failed"
        continue
    fi

    # Verify data
    PRODUCTS=$(sqlite3 app.db "SELECT COUNT(*) FROM offer WHERE supplier LIKE '${dealer^}%';")
    echo "✓ $dealer: $PRODUCTS products ingested"
done

# 3. Test search across all dealers
echo ""
echo "Step 3: Testing search..."
RESULTS=$(uv run python -m app.cli search-cli "shimano" | grep -c "│" || true)
if [ "$RESULTS" -gt 3 ]; then
    echo "✓ Search working ($RESULTS results)"
else
    echo "✗ Search returned insufficient results"
fi

# 4. Test quote generation
echo ""
echo "Step 4: Testing quote generation..."
# Get first available product PN
PN=$(sqlite3 app.db "SELECT mpn FROM product WHERE mpn IS NOT NULL LIMIT 1;")
if [ -n "$PN" ]; then
    uv run python -m app.cli quote-cli --pn "$PN" --qty 1 --customer "Test"
    if [ -d "out/quotes" ]; then
        echo "✓ Quote generated successfully"
    else
        echo "✗ Quote generation failed"
    fi
else
    echo "⚠️  No products with PN available for quote test"
fi

echo ""
echo "✅ Web ingestion test completed"
```

---

## Troubleshooting

### Authentication Issues

**Symptom**: "Login failed" or "401 Unauthorized"

**Fix**: Verify credentials in .env, check if dealer changed login URL

---

### Parsing Issues

**Symptom**: Products ingested but fields are NULL/empty

```bash
# Test mapping on local HTML
uv run python -m app.cli fetch-web \
  --html providers/html/example.html \
  --mapping providers/web-ciclopromo.yaml

# Inspect what was extracted
uv run python -m app.cli dump-md | head -20
```

**Fix**: Update mapping YAML selectors (website HTML changed)

---

### Performance Issues

**Symptom**: Very slow ingestion (>30s per page)

```bash
# Increase delay between requests
uv run python -m app.cli dealer-sync ciclopromo --delay 2.0

# Reduce max pages for testing
uv run python -m app.cli dealer-sync ciclopromo --max-pages 1
```

**Fix**: Add delays to avoid rate limiting, use caching

---

### SPA Rendering Issues (RMS)

**Symptom**: No products from RMS (Angular SPA)

```bash
# Verify Playwright is installed
playwright --version

# Run with debug logging
DEBUG=pw:api uv run python -m app.cli dealer-sync rms --max-pages 1
```

**Fix**: Ensure Playwright chromium is installed, increase wait timeouts

---

## Integration with CI/CD

**Note**: Web ingestion tests require credentials and are **NOT** run in CI by default.

To run in CI:
1. Add credentials as GitHub Secrets
2. Add `--run-integration` flag to pytest
3. Expect slower runs (network I/O, Playwright overhead)

```yaml
# .github/workflows/integration-tests.yml
- name: Run web ingestion tests
  env:
    DEALER_CICLOPROMO_USERNAME: ${{ secrets.CICLOPROMO_USER }}
    DEALER_CICLOPROMO_PASSWORD: ${{ secrets.CICLOPROMO_PASS }}
  run: |
    pytest --run-integration tests/test_b2b_integration.py -v
```

---

## Performance Benchmarks

Expected timing for web ingestion (2 pages per dealer):

| Dealer | Pages | Products | Time | Notes |
|--------|-------|----------|------|-------|
| CicloPromo | 2 | 40-60 | ~15s | Form login, httpx |
| Ciclodiffusione | 2 | 30-50 | ~12s | API auth, httpx |
| RMS | 2 | 20-40 | ~25s | SPA, Playwright required |

**Full catalog** (50+ pages): 5-15 minutes per dealer

---

## Next Steps

After successful web ingestion testing:

1. **Expand Coverage**: Increase `--max-pages` for production runs
2. **Schedule Sync**: Add cron job for daily dealer sync
3. **Monitor Quality**: Track missing fields, price changes
4. **Add Dealers**: Create mappings for new B2B portals

---

*Last updated: 2026-01-17*
