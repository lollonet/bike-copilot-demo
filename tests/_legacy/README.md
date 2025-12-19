# Legacy Tests Quarantine

This directory contains tests for legacy code moved to `app/_legacy/`.

## Why are these here?
These tests are excluded from the main CI pipeline (`make test`) because the underlying code is deprecated and currently undergoing a structural refactor. They often fail due to import paths or obsolete logic.

## How to run them?
You can run these tests manually to check for regressions during migration:

```bash
make test-legacy
```

## Migration Plan
1. Refactor `app/_legacy` modules into the new Clean Architecture structure.
2. Update or rewrite the corresponding tests.
3. Move valid tests back to `tests/` and delete obsolete ones.
