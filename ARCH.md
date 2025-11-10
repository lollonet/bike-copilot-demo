---
project: Bike Sourcing Copilot
version: 1.0
status: frozen
owners: [ "IT Partner" ]
updated: 2025-11-10
---

# ARCH — Architettura Logica & Operativa

## 1. Vista d’insieme
```

[CSV Fornitori] -> [Ingest] -> [SQLite Metacatalogo]
|
v
[Ricerca + Ranking]
|
v
[Streamlit Mini-GUI -> PDF]

```

## 2. Componenti
- **Ingest**: parsing CSV, normalizzazione, dedup (EAN > brand+MPN).
- **Metacatalogo (SQLite)**: `Product`, `Supplier`, `Offer` (+ indici).
- **Compatibilità**: regole deterministiche + sinonimi YAML.
- **Ranking**: disponibilità > compatibilità > lead-time > prezzo.
- **GUI**: Streamlit, form + tabella + PDF.
- **PDF**: reportlab (no dipendenze OS extra).
- **Ops**: venv, log base, systemd service, backup DB giornaliero.

## 3. Schema dati (essenziale)
- `Product(id, brand, mpn, ean, name, attributes_json)`
- `Supplier(id, name, code)`
- `Offer(id, supplier_id, product_id, price, in_stock, lead_time_days, updated_at)`

## 4. Interfacce
- **Input**: CSV unico consolidato `supplier,brand,mpn,ean,name,price,in_stock,lead_time_days,speed,freehub,brake,rotor_mount,axle`.
- **Output**: PDF preventivo in `storage/quotes/`.

## 5. Prestazioni & qualità
- Budget query: < 200 ms su 5k offerte (SQLite + indici).
- Coerenza: ingest idempotente, log contatori (nuovi/aggiornati/scartati).

## 6. Sicurezza (demo)
- Locale, senza PII persistente. Backup .tar.gz del DB e dei PDF.

## 7. Evoluzione (post‑MVP)
- Postgres, API FastAPI, alert restock, integrazione ERP, caching Redis.
```

