---
id: ARC-020
domain: architecture
status: draft
source_of_truth: false
related: [ARC-010, REQ-004, REQ-005, REQ-006]
---

# ARC-020 — Wireframe UX PN‑first (low‑fi, testo)

Nota: commenti nel codice saranno in inglese; qui tutto in italiano.

Obiettivo
- Visualizzare in modo chiaro il flusso PN‑first: inserimento PN → confronto offerte per dealer → carrello → ottimizzatore → preventivo.

Layout (desktop, griglia principale)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ PN Produttore [ CN-HG601 |________________________ ] (Aggiungi) (Incolla…)  │
│ Dealer [ ▢ Tutti  ▢ DealerA ▢ DealerB ]  Solo in stock [▢]  Budget € [  0 ] │
│                                                                              │
│ ┌───────────────────────────────┐  ┌───────────────────────────────────────┐ │
│ │ Risultati per PN              │  │ Carrello / Preventivo                │ │
│ │                               │  │                                       │ │
│ │ [PN] CN-HG601  Shimano Catena │  │ Righe:                               │ │
│ │  ┌──────────────┬─────┬────┬──┴┐ │  PN        Dealer   Prezzo  Qtà  Sub  │ │
│ │  │ Dealer       │ €   │Stock│Lead│ │  CN-HG601  DealerA  24,90   2   49,8 │ │
│ │  ├──────────────┼─────┼────┼────┤ │  …                                   │ │
│ │  │ DealerA      │24,9 │ ✓  │ 1g │ │                                       │ │
│ │  │ DealerB      │23,5 │ ✗  │ 3g │ │ Totali: Subtotale / IVA / Sped / Tot. │ │
│ │  │ DealerC      │26,0 │ ✓  │ 2g │ │                                       │ │
│ │  └──────────────┴─────┴────┴────┘ │ Ottimizzatore:                        │ │
│ │ [Aggiungi al carrello]             │  • Miglior prezzo (multi‑dealer)      │ │
│ │ [Blocca dealer: (A|B|C)]           │  • Un solo dealer                     │ │
│ │                                     │  • Al massimo N dealer [ 2 ]          │ │
│ │ [PN] PG‑1230  SRAM Cassetta 12v    │  • Più veloce (lead min)              │ │
│ │  … (stessa tabella per ogni PN)    │  [Ricalcola] [Crea preventivo]        │ │
│ └───────────────────────────────┘  └───────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

Azioni chiave
- Aggiungi PN singolo: inserisci PN e premi “Aggiungi”.
- Incolla lista PN: modale con textarea (uno per riga) → batch di richieste.
- Aggiungi al carrello: dalla tabella offerte per PN/dealer.
- Blocca dealer per riga: impedisce che l’ottimizzatore cambi il dealer di quella riga.
- Ottimizzatore: produce soluzioni; l’operatore può accettare/rigenerare.
- Crea preventivo: modale con logo (da Impostazioni), cliente, validità, note → HTML/PDF.

Stati/feedback
- Badge “Miglior prezzo”, “24h” nella tabella offerte.
- Avviso se policy spedizione mancante per un dealer; campo override rapido nelle Impostazioni.
- PN non mappato: appare un chip “Da mappare” con link a runbook/azione di ingest mirata.

Mobile/Responsivo (indicazioni)
- Stack verticale; carrello come pagina dedicata o drawer; azioni principali sempre visibili (Aggiungi, Crea preventivo).

Collegamenti
- REQ‑004 (interfaccia PN‑first), REQ‑005 (ottimizzatore), REQ‑006 (branding preventivi).

