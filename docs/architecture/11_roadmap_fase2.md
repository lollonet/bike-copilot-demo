---
id: ARCH-V2-11
domain: docs
status: draft
---

# 11 — Roadmap Fase 2

> Milestone post-discovery, prioritizzazione MoSCoW, validation spikes.

---

## Phase 1.5: Validation Spikes

Prima dell'implementazione completa, PoC mirati per validare le decisioni ad alto rischio:

| Spike | Obiettivo | Durata Stimata | Sezione Validata |
|-------|-----------|---------------|-----------------|
| **Stealth vs Anti-bot** | Verificare che Playwright stealth funzioni contro i 3 portali B2B | 2–3 giorni | s05 |
| **FTS Benchmark** | Caricare 10k prodotti sample, misurare qualità/performance ricerca PostgreSQL FTS | 1 giorno | s06 |
| **Solver Performance** | Testare PuLP+CBC con carrello 20 items × 3 fornitori, misurare tempo | 0.5 giorni | s07 |
| **arm64 Compatibility** | Verificare tutti i componenti su Mac Studio reale (OR-Tools, Playwright, images) | 1 giorno | s03, s11 |
| **Login Automation** | Script Playwright per login + navigazione base su ciascun fornitore | 2 giorni | s05 |

**Totale Phase 1.5**: ~7 giorni di lavoro.

> Questi spike producono **dati reali** che validano o invalidano le assunzioni architetturali. Se uno spike fallisce (es. anti-bot bloccante), l'architettura va rivista PRIMA di implementare.

---

## Feature Fase 2 — Prioritizzazione MoSCoW

### Must Have (M)

| Feature | Descrizione | Dipendenza Fase 1 |
|---------|-------------|-------------------|
| **Fornitori aggiuntivi (5-8)** | BRN Bike Parts, ICAR, Roadrun B2B, Hartje | Connector pattern (s05) funzionante |
| **Matching semantico** | Embedding per descrizioni prodotto quando fuzzy trigram non basta | Data model stabile (s04) |
| **Alert prezzo** | Notifica quando un prodotto scende sotto soglia configurata | Scraping + metriche funzionanti |

### Should Have (S)

| Feature | Descrizione | Dipendenza Fase 1 |
|---------|-------------|-------------------|
| **Click-to-order** | Compilazione automatica carrello sul sito fornitore (Playwright) | Scraping architecture + legal audit OK |
| **Storico prezzi** | Dashboard con trend prezzi per prodotto nel tempo | DB con dati storici (non eliminare vecchi listing) |
| **Dizionario sinonimi** | Mappatura abbreviazioni/sinonimi ciclismo per FTS | FTS funzionante, feedback utente |
| **Worker dedicati** | Un container RQ worker per fornitore (parallelismo) | Docker Compose stabile |

### Could Have (C)

| Feature | Descrizione | Note |
|---------|-------------|------|
| **PWA / Mobile** | Accesso da tablet in officina, installabile come app | Responsive CSS + service worker |
| **Caddy + auth** | Reverse proxy con basic auth per esposizione LAN/Tailscale | Già previsto in s11 (commentato) |
| **Grafana dashboard** | Monitoring avanzato con Prometheus + Grafana | Sostituisce SQLite metrics |
| **Import/export CSV** | Importare lista ricambi da file, esportare ordine | UI feature |
| **Multi-lingua** | Supporto inglese per interfaccia | Internazionalizzazione Jinja2 |

### Won't Have (W) — fuori scope

| Feature | Motivazione |
|---------|-------------|
| **Multi-tenancy** | Vincolo architetturale: single-user. Mai per questo progetto. |
| **Marketplace** | L'obiettivo è acquistare, non vendere. |
| **App nativa iOS/Android** | PWA copre il caso d'uso tablet. App nativa non giustificata per 1 utente. |
| **AI/LLM per matching** | Overkill per fase 2. Embedding sono sufficienti. LLM per interpretazione query è fase 3+. |
| **Ordine automatico completo** | Troppo rischioso: errori di ordine non reversibili. Click-to-order con supervisione è il massimo. |

---

## Milestone Post-Discovery

| Milestone | Contenuto | Stima |
|-----------|-----------|-------|
| **M1: Foundation** | Project scaffolding, Docker Compose base, DB + migrations, modelli SQLAlchemy, health endpoint | 1 settimana |
| **M2: Connectors** | Primo connettore (Ciclodiffusione — più semplice), ABC interface, login + catalog scraping | 1-2 settimane |
| **M3: Search** | Importazione dati in DB, indici FTS, API ricerca, UI ricerca base | 1 settimana |
| **M4: Matching** | EAN normalization, fuzzy matching, UI review manuale | 1 settimana |
| **M5: Optimizer** | PuLP + CBC solver, API ottimizzazione, UI slider pesi + risultato | 1-2 settimane |
| **M6: Connectors ×3** | Secondo e terzo connettore (Ciclo Promo, RMS) | 2 settimane |
| **M7: Polish** | Observability, alerting, backup, documentazione uso, UX refinement | 1 settimana |

**Totale stimato fase 1**: 8-10 settimane di implementazione (dopo Phase 1.5 spikes).

---

## Candidati Fornitori Fase 2

| Fornitore | Tipo | Note | Priorità |
|-----------|------|------|----------|
| **BRN Bike Parts** | Distributore nazionale | Ampio catalogo, probabile portale B2B moderno | Alta |
| **ICAR** | Distributore | Da verificare portale B2B | Media |
| **Roadrun B2B** | Distributore | Da verificare portale B2B | Media |
| **Hartje** | Distributore tedesco/europeo | Catalogo internazionale, possibilmente in tedesco/inglese | Bassa (complessità lingua) |

L'aggiunta di ciascun fornitore segue il pattern:
1. Legal audit (s02 template)
2. Supplier reconnaissance (s05 template)
3. Implementazione `SupplierConnector` ABC
4. Test e validazione dati

---

## Alternative di Prioritizzazione Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **Mobile-first (fase 2 immediata)** | Il workflow primario è desktop. Il tablet in officina è un nice-to-have, non il driver. PWA è sufficiente. |
| **Click-to-order prima di più fornitori** | Valore dell'aggregatore cresce con il numero di fornitori. Più fornitori = più opzioni di ottimizzazione. |
| **AI/LLM matching subito** | Embedding per matching sono sufficienti. LLM costosi e complessi per un beneficio marginale rispetto a embedding. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Scope creep | Timeline fase 1 si allunga | MoSCoW rigoroso, freeze scope dopo M1 |
| Dipendenze fase 1 non completate | Feature fase 2 bloccate | Phase 1.5 spikes per de-risking |
| Costi nascosti | Tempo effettivo > stima | Buffer 20% su ogni milestone |
| Fornitori fase 2 non compatibili | Connector pattern non generalizzabile | ABC interface validata con 3 fornitori diversi in fase 1 |

---

## Open Questions

1. **Timeline fase 2**: quando iniziare? → Dopo fase 1 stabile e in uso da almeno 1 mese
2. **Budget tempo**: quante ore/settimana dedicate al progetto? → Da definire (utente)
3. **Priorità fornitori fase 2**: quale aggiungere per primo? → BRN (catalogo ampio, alta priorità)

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← s01–s10** | Tutte le sezioni fase 1 | Prerequisiti per fase 2 |
| **← s05** | Scraping Architecture | ABC interface è il fondamento per nuovi connettori |
| **← s02** | Legal Audit | Template riutilizzabile per nuovi fornitori |
