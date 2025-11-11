# Runbook 11 — Demo PN‑first (script)

Scopo
- Mostrare il flusso: inserisci PN → confronta dealer → ottimizza → genera preventivo.

Script
- Avvia API (`make api`) e UI (`make ui`).
- Inserisci PN singolo (es. `CN-HG601`) e poi una lista (incolla).
- Aggiungi al carrello la soluzione proposta (“miglior prezzo”).
- Prova scenario “un solo dealer” e confronta totali.
- “Crea preventivo”: inserisci cliente e genera PDF.

Note
- Se alcune policy non sono estratte, UI mostrerà avviso e permetterà override.
