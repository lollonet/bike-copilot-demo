---
id: ADR-003
domain: decisions
status: accepted
date: 2024-12-01
related: [TECH-010, ARC-010, REQ-007]
---

# ADR-003: Playwright for Web Scraping

## Status

Accepted

## Context

Bike Copilot needs to crawl dealer websites to fetch product and pricing data. Dealers use various platforms:
- Static HTML sites
- SPAs with JavaScript rendering
- Sites with anti-bot measures

The crawler must handle all these cases reliably.

## Options Considered

### Option 1: httpx + BeautifulSoup Only
**Pros:**
- Lightweight, fast
- Simple to implement
- Low resource usage

**Cons:**
- Cannot handle JavaScript-rendered content
- Limited for SPAs
- Blocked by some anti-bot systems

### Option 2: Selenium
**Pros:**
- Mature, well-documented
- Handles JavaScript
- Large community

**Cons:**
- Heavy, slow startup
- Flaky, requires careful waits
- Complex WebDriver management

### Option 3: Playwright
**Pros:**
- Modern, fast browser automation
- Auto-wait for elements
- Handles SPAs naturally
- Headless and headed modes
- Better anti-detection than Selenium
- Single API for Chromium/Firefox/WebKit

**Cons:**
- Heavier than pure HTTP
- Requires browser binaries
- More complex than httpx

### Option 4: Hybrid (Playwright + httpx)
**Pros:**
- Use httpx for simple static sites (fast)
- Use Playwright for SPAs (capable)
- Best of both worlds

**Cons:**
- Two code paths to maintain
- Must detect which approach to use

## Decision

**Use Playwright as primary with httpx fallback for simple sites.**

Configuration per dealer specifies which approach:

```yaml
# providers/dealers.yaml
dealers:
  - key: dealer_a
    scraper: playwright  # SPA, needs JS
  - key: dealer_b
    scraper: httpx       # Static HTML
```

## Rationale

1. **SPA support**: Most modern dealer sites use JavaScript
2. **Reliability**: Playwright's auto-wait reduces flakiness
3. **Anti-detection**: Better than Selenium at avoiding blocks
4. **Flexibility**: httpx fallback for speed on simple sites
5. **Single install**: `playwright install chromium` handles binaries

## Implementation Pattern

```python
# Playwright for SPA
async def fetch_with_playwright(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        await browser.close()
        return content

# httpx for static
async def fetch_with_httpx(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

## Consequences

### Positive
- Handles all dealer site types
- Reliable scraping with auto-waits
- Good performance with httpx fallback
- Easier maintenance than Selenium

### Negative
- Requires Chromium binary (~200MB)
- Higher memory usage than pure HTTP
- Slower than httpx for simple pages

### Mitigation
- Use httpx where possible (configured per dealer)
- Run crawls during off-hours (3 AM)
- Browser reuse within crawl session

## References

- [Playwright Python Docs](https://playwright.dev/python/)
- [Web Scraping Best Practices](https://scrapfly.io/blog/web-scraping-best-practices/)
