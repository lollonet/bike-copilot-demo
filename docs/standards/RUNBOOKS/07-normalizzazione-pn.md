# Runbook 07 — Normalizzazione PN e alias

Obiettivo
- Definire e validare le regole di normalizzazione dei codici produttore (PN) e mantenere un dizionario di alias.

Passi
- Regole base: uppercase, trim, rimozione separatori (spazio, -, /), soppressione suffissi noti.
- Alias: aggiungi varianti osservate (per brand o dealer) in un file YAML dedicato.
- Test: prepara piccoli casi “raw→norm” e verifica che PNMapping.confidence resti ≥ soglia.

Esempi
- `AB-123 / 45` → `AB12345`
- `CN-HG601` e `CNHG601` → alias allo stesso PN normalizzato.

Esiti
- Documenta le regole nel TECH.md; aggiorna alias quando emergono nuovi pattern.
