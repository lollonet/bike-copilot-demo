# ARCHITETTURA DEL SISTEMA

## 1. Modello Dati (ER)
- **Supplier:** (id, name, credentials, adapter_type)
- **MasterProduct:** (id, canonical_name, category, main_image_path)
- **SupplierProduct:** (id, supplier_id, master_id, sku, ean, name, price_net, availability, last_updated)
- **ProductMatchRule:** (id, prod_a_id, prod_b_id, is_match)
- **QuoteItem:** (id, supplier_prod_id, quantity, user_price)

## 2. Componenti Software
- **Ingestor Engine:** Gestisce i vari `Adapters` (uno per fornitore). Usa Playwright per estrarre dati dai siti.
- **Matcher Service:** Applica la logica di deduplicazione e gestisce i match manuali.
- **API Layer (FastAPI):** Espone i dati al frontend e gestisce le azioni (es. `start_cart_automation`).
- **Frontend (HTMX):** Interfaccia reattiva basata su template Jinja2.

## 3. Flusso Dati (Ingestion)
1. Trigger Ingestion -> 2. Adapter Scarica Dati -> 3. Matcher Normalizza -> 4. Salvataggio su SQLite.