---
id: ADR-002
domain: decisions
status: accepted
date: 2024-12-01
related: [TECH-010, ARC-010, REQ-002]
---

# ADR-002: Jinja2 + HTMX for UI

## Status

Accepted

## Context

Bike Copilot needs a web UI for:
- Product search with filters
- Price comparison across dealers
- Cart management
- Quote generation

The UI should be responsive, easy to maintain, and not require a complex frontend build pipeline.

## Options Considered

### Option 1: React/Vue SPA
**Pros:**
- Rich interactivity
- Large ecosystem
- Component reusability

**Cons:**
- Requires Node.js build pipeline
- Separate frontend/backend deployment
- State synchronization complexity
- Overkill for data-display focused UI

### Option 2: Gradio
**Pros:**
- Rapid prototyping
- Python-only, no JS needed
- Built-in components

**Cons:**
- Limited customization
- Not suitable for production B2B app
- Performance issues with large datasets
- Vendor lock-in to Gradio patterns

### Option 3: Jinja2 + HTMX
**Pros:**
- Server-side rendering, SEO-friendly
- No build step, no Node.js
- Progressive enhancement
- Python templates, single codebase
- HTMX handles AJAX without custom JS

**Cons:**
- Less interactive than SPA
- Learning curve for HTMX patterns
- Limited offline capability

## Decision

**Use Jinja2 templates with HTMX for progressive enhancement.**

## Rationale

1. **Simplicity**: No separate frontend build, single Python codebase
2. **Performance**: SSR is fast for data-heavy pages
3. **Maintainability**: Templates are straightforward HTML
4. **Progressive enhancement**: Works without JS, enhanced with HTMX
5. **No Node.js**: Reduces deployment complexity

## Implementation Pattern

```html
<!-- Search with HTMX -->
<form hx-post="/search" hx-target="#results" hx-swap="innerHTML">
  <input type="text" name="q" placeholder="Search PN, EAN, or name...">
  <button type="submit">Search</button>
</form>

<div id="results">
  <!-- Results loaded via HTMX -->
</div>
```

```python
# FastAPI endpoint returns HTML partial
@app.post("/search")
async def search(request: SearchRequest):
    results = await search_service.search(request.q)
    return templates.TemplateResponse(
        "partials/results.html",
        {"request": request, "results": results}
    )
```

## Consequences

### Positive
- Single deployment artifact
- Fast initial page loads
- Easy to debug (view source)
- No state management complexity
- Works on low-powered devices

### Negative
- Less suitable for highly interactive features
- Must be careful with HTMX patterns
- Limited offline functionality

### Mitigation
- Use HTMX extensions for complex interactions
- Consider Alpine.js for client-side state if needed
- Document HTMX patterns in codebase

## References

- [HTMX Documentation](https://htmx.org/docs/)
- [Hypermedia Systems](https://hypermedia.systems/)
