---
id: API-EXAMPLES
domain: api
status: approved
source_of_truth: false
related: [REQ-001, REQ-003, REQ-005, REQ-008]
---

# API Examples

Runnable curl examples for all main API endpoints.

**Base URL:** `http://localhost:8000`

## Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "db": true,
  "pdfkit": true,
  "version": "0.1.0"
}
```

## Product Search (REQ-001)

### Basic Text Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query_text": "shimano xt"}'
```

### Search by Part Number

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query_text": "M8100"}'
```

### Search with Filters

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "brake",
    "suppliers": ["rms", "b2bike"],
    "in_stock_only": true,
    "budget_max": 100.00
  }'
```

**Response (SearchResponse):**
```json
{
  "items": [
    {
      "id": 456,
      "brand": "Shimano",
      "mpn": "IM8100JLFPRA100",
      "supplier": "rms",
      "price": 89.90,
      "in_stock": true,
      "lead_time_days": 3,
      "score": 0.95,
      "pros": ["in stock", "fast shipping"],
      "cons": []
    }
  ],
  "ts": "2024-12-19T14:30:00Z"
}
```

## Facets

Get available filter options:

```bash
curl -X POST http://localhost:8000/facets \
  -H "Content-Type: application/json" \
  -d '{"query_text": ""}'
```

**Response:**
```json
{
  "facets": {
    "suppliers": ["rms", "b2bike", "ciclimatteoni"],
    "categories": ["brakes", "drivetrain", "wheels"]
  },
  "totals": {
    "products": 1523,
    "offers": 4521
  }
}
```

## Dealers List (REQ-006)

```bash
curl http://localhost:8000/dealers
```

**Response:**
```json
{
  "dealers": [
    {
      "name": "rms",
      "offers": 12500,
      "last_updated": "2024-12-19T03:15:00Z"
    },
    {
      "name": "b2bike",
      "offers": 8200,
      "last_updated": "2024-12-19T03:20:00Z"
    }
  ]
}
```

## Order Optimization (REQ-003)

### Best Price Scenario

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"maker_pn": "M8100", "qty": 1},
      {"maker_pn": "RT86", "qty": 2}
    ],
    "params": {
      "scenario": "miglior-prezzo"
    }
  }'
```

### Single Dealer Scenario

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"maker_pn": "M8100", "qty": 1},
      {"maker_pn": "RT86", "qty": 2}
    ],
    "params": {
      "scenario": "un-solo-dealer"
    }
  }'
```

**Response:**
```json
{
  "lines": [
    {
      "offer_id": 456,
      "maker_pn": "M8100",
      "name": "Shimano XT Brake",
      "dealer": "rms",
      "unit_price": 89.90,
      "qty": 1,
      "line_total": 89.90,
      "lead_time_days": 3
    }
  ],
  "dealers": ["rms"],
  "costs": {
    "subtotal": 89.90,
    "shipping": 8.50,
    "total": 98.40
  }
}
```

## Quote Generation (REQ-005)

**Note:** Requires Basic Auth credentials.

```bash
curl -X POST http://localhost:8000/quote \
  -u "admin:password" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"offer_id": 456, "qty": 1},
      {"offer_id": 789, "qty": 2}
    ],
    "customer_name": "Mario Rossi",
    "customer_contact": "mario@example.com",
    "validity_days": 7,
    "apply_vat": true,
    "vat_rate": 0.22
  }'
```

**Response:**
```json
{
  "content_type": "text/html",
  "filename": "quote-20241219-143052.html",
  "url": "/files/quote-20241219-143052.html"
}
```

### Download Generated Quote

```bash
# HTML version
curl -u "admin:password" \
  http://localhost:8000/files/quote-20241219-143052.html \
  -o quote.html

# PDF version (if wkhtmltopdf available)
curl -u "admin:password" \
  http://localhost:8000/files/quote-20241219-143052.pdf \
  -o quote.pdf
```

## KPI Endpoints (REQ-008)

**Note:** Both KPI endpoints require Basic Auth.

### Today's KPIs

Returns event counts for the current day (since midnight UTC).

```bash
curl -u "admin:password" http://localhost:8000/kpi/today
```

**Response:**
```json
{
  "ingest_complete": 5,
  "search": 127,
  "optimize": 23,
  "quote": 8
}
```

### KPI Summary

Returns comprehensive KPI metrics across all dealers.

```bash
curl -u "admin:password" http://localhost:8000/kpi/summary
```

**Response (KPISummaryResponse):**
```json
{
  "products_total": 15234,
  "products_with_offers": 12500,
  "coverage_pn_pct": 82.05,
  "offers_total": 45000,
  "offers_updated_24h": 38250,
  "updated_24h_pct": 85.0,
  "pn_unmapped": 234,
  "per_dealer": [
    {
      "dealer": "rms",
      "offers": 12500,
      "updated_24h_pct": 89.6,
      "lag_days": 0.5
    }
  ],
  "ts": "2024-12-19T14:30:00Z"
}
```

## Error Handling

All endpoints return errors in Problem format:

```json
{
  "kind": "not_found",
  "message": "offer_id 999 not found"
}
```

Common error codes:
- `400` - Bad request (invalid input)
- `401` - Unauthorized (missing/invalid credentials)
- `403` - Forbidden (access denied)
- `404` - Not found

## Testing with httpie

If you prefer [httpie](https://httpie.io/):

```bash
# Search
http POST :8000/search query_text="shimano"

# Optimize
http POST :8000/optimize items:='[{"maker_pn":"M8100","qty":1}]'

# Quote (with auth)
http -a admin:password POST :8000/quote \
  items:='[{"offer_id":456,"qty":1}]' \
  customer_name="Test" \
  customer_contact="test@example.com"
```
