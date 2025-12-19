# REQUISITI FUNZIONALI (REQ)

## REQ-100: Ingestion & Normalization
- **REQ-101 (Daily Sync):** Il sistema deve eseguire un'ingestion programmata (morning) dei cataloghi via Playwright o CSV Adapter.
- **REQ-102 (Image Archiving):** Le immagini devono essere scaricate localmente e associate al `SupplierProduct`.
- **REQ-103 (Data Integrity):** I prezzi devono essere salvati come `Decimal` (non float) per precisione finanziaria.

## REQ-200: Smart Matching
- **REQ-201 (Auto-Match):** Prodotti con stesso EAN devono essere fusi sotto un unico `MasterProduct`.
- **REQ-202 (Fuzzy Match):** Se l'EAN manca, suggerire l'unione basata su Brand + Levenshtein Distance (>85%) sul nome.
- **REQ-203 (Manual Persistence):** Un match confermato o creato manualmente dall'utente deve essere ricordato permanentemente.

## REQ-300: UI & Business Logic
- **REQ-301 (Unified Search):** Ricerca full-text su `MasterProduct` e `SupplierProduct`.
- **REQ-302 (Interactive Quote):** Permettere l'inserimento manuale del prezzo di vendita finale per ogni riga del preventivo.
- **REQ-303 (Headless Cart):** Automatizzare il login e l'aggiunta a carrello sul fornitore selezionato senza confermare l'acquisto.
