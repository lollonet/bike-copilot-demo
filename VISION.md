# Visione (PN‑first, mercato Italia)

Perché
- Offrire ai negozi di biciclette un’esperienza rapidissima e affidabile di preparazione preventivi a partire dal codice produttore (PN), aggregando offerte aggiornate da più dealer e generando PDF/HTML brandizzati. Dati locali (CSV/PDF/web) su una macchina Linux, con percorso chiaro verso connettori/API reali.

Utenti e Scenari
- Operatore/Meccanico: inserisce uno o più PN, confronta offerte per dealer, aggiunge al carrello, genera preventivo.
- Amministratore: aggiunge un nuovo dealer (mapping + credenziali opzionali), pianifica il crawling, controlla freschezza e KPI.
- Integratore: in fasi successive collega ERP/API fornitori senza rompere i flussi.

Obiettivi e Metriche
- Tempo al preventivo: P50 ≤ 30s, P95 ≤ 60s (dati già in DB locale).
- Copertura PN: ≥ 80% dei PN target con almeno un’offerta.
- Freschezza offerte: ≥ 85% aggiornate ≤ 24h (configurabile per dealer).
- Accuratezza match PN: ≥ 99,5% (quasi zero falsi positivi; alias e normalizzazione forti, fuzzy solo come ultima ratio).
- Latenza ricerca locale: < 300 ms; verifica on‑demand (fase 2+) < 5 s.

Perimetro v1
- Ricerca PN‑first (campo singolo e incolla lista) e ranking prezzo/disponibilità/tempi.
- Crawler/configurazione per 2–3 piattaforme (es. WooCommerce, Storeden) + import CSV/PDF quando disponibili.
- UI: risultati per PN/dealer; carrello multi‑riga; preventivo con logo negozio e intestazione cliente; ottimizzazione ordine (un dealer / max N / miglior prezzo) con stima spedizioni.
- API allineate a PN‑first con contratti tipizzati.

Non‑Obiettivi v1
- Integrazione ERP completa, garanzia real‑time, headless browser universale.
- Multi‑tenant SaaS.

Rischi e Mitigazioni
- Anti‑bot/rate‑limit: politeness (delay/jitter), caching, scheduling scaglionato; credenziali ove disponibili.
- Variabilità PN: tabella alias e normalizzazione (uppercase, trim, rimozione separatori/suffissi); fuzzy ancorato e con soglie conservative.
- Compliance/ToS: preferire feed ufficiali; rispettare robots/condizioni; chiedere consenso dove necessario.

Fasi
- P0 Documenti e piano (questa Visione, ARCH, TECH, CONTROL, Runbook).
- P1 Fondazione PN‑first: modello dati centrato su PN, contratti API, migrazione UI minima.
- P2 Motore crawling baseline + estrazione “Spedizioni/Soglie” deterministica; (opz.) probing carrello; LLM assistivo con guardrail dove serve.
- P3 Ottimizzatore ordine (scenari) e Impostazioni dealer/branding.
- P4 Switch percorso PN‑first come predefinito; archiviazione parti legacy non più usate.
