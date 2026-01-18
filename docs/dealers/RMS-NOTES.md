---
id: TECH-012
domain: technology
---

# TECH-012: RMS Authentication - Technical Notes

## Status: ⚠️ Not Automatable (Requires Manual Setup)

RMS B2B portal (`b2bnew.rms.it`) implements client-side encryption that prevents automated scraping.

## Investigation Summary

### What Works
- ✅ Browser login (Playwright): Successfully authenticates
- ✅ Endpoint identified: `https://apib2b.rms.it/users/authenticate`
- ✅ Base64 encoding: Implemented in our code

### What Doesn't Work
- ❌ Direct API calls: Return "Utente non trovato" (User not found)
- ❌ Simple Base64: Credentials must be encrypted, not just encoded

## Technical Details

### Browser Behavior (Working)
```javascript
POST https://apib2b.rms.it/users/authenticate
Headers:
  clientsecret: viDCGxiHMkspSOlACzb8v16NRMFhY0MGJJOpScNiqZOhVFOe8+3Xgl0nWnhag455
  ambito: ciclo
  content-type: application/json

Payload:
{
  "username": "UB4VIqE+ef83SKGGGCsqmQ==",  // AES-encrypted, then Base64
  "password": "hbgilNTSeqs+nTnE4Gl0Cg==",   // AES-encrypted, then Base64
  "idAzienda": 1
}
```

### Our Code (Not Working)
```json
{
  "username": "MDE1MzIzMDAwMQ==",  // Base64("0153230001")
  "password": "Z2lhbm5hOTF0cw==",   // Base64("gianna91ts")
  "remember_me": true
}
```

## Root Cause

RMS uses **client-side AES encryption**:
1. JavaScript extracts `clientsecret` from Angular app
2. Credentials are encrypted using AES-128 with the secret
3. Encrypted bytes are Base64-encoded before sending
4. Server decrypts using same secret

### Evidence
- Browser username decodes to: `501e1522a13e79ff3748a186182b2a99` (16 bytes hex)
- Our username decodes to: `0153230001` (plain text)
- Encryption key embedded in Angular bundle

## Options for Automation

### Option A: Reverse Engineer Encryption (Not Recommended)
**Effort**: High
**Maintenance**: Very High (breaks on every update)
**Steps**:
1. Decompile Angular bundle to find encryption function
2. Extract `clientsecret` from JavaScript
3. Implement AES encryption in Python
4. Update on every RMS website deploy

**Risk**: Anti-scraping measures intentional - may violate ToS

### Option B: Request API Access (Recommended)
**Effort**: Low
**Maintenance**: Low
**Steps**:
1. Contact RMS support
2. Request official B2B API credentials
3. Use documented endpoints

### Option C: Manual Export
**Effort**: Low (one-time)
**Maintenance**: Medium (periodic re-exports)
**Steps**:
1. Request CSV export from RMS
2. Use existing CSV adapter for import

### Option D: Skip RMS
**Effort**: Zero
**Impact**: Other dealers provide sufficient coverage:
- CicloPromo: 748 products
- Ciclodiffusione: 180 products
**Total**: 928 products without RMS

## Recommendation

**Use Option D (Skip for now) + Option B (API request)**

Rationale:
- Quick win: Focus on working dealers (CicloPromo, Ciclodiffusione)
- Long-term: Request official API access from RMS
- Avoid: Reverse engineering (high maintenance, potential legal issues)

## Historical Context

- **2025-11-15**: RMS seeds generated with `scripts/generate_rms_brand_seeds.py`
- **2026-01-18**: Authentication investigation revealed client-side encryption
- **2026-01-18**: Documented as "not automatable" pending API access

## Related Files

- Configuration: `providers/dealers.yaml` (lines 1-48)
- Mapping: `providers/web-rms.yaml`
- Test: `tests/test_b2b_integration.py::TestRMSIntegration`

---

*Last updated: 2026-01-18*
