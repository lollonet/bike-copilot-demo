---
id: ARCH-V2-07
domain: docs
status: draft
---

# 07 — UI Architecture & Auth Applicativo

> Architettura frontend, componenti, UX flow, modello auth single-user.

---

## Decisione: SSR + HTMX con Isole Alpine.js

### Approccio Ibrido

| Criterio | SSR + HTMX + Alpine.js | SPA React/Vue | Django Templates |
|----------|----------------------|---------------|-----------------|
| Build step JS | **Nessuno** | Webpack/Vite obbligatorio | Nessuno |
| Interattività | Buona (Alpine.js per slider, HTMX per aggiornamenti) | Eccellente | Limitata |
| Complessità | Bassa | Alta (state management, routing, API) | Bassa |
| SEO | Irrilevante (app privata) | Irrilevante | Irrilevante |
| Bundle size | ~15 KB (HTMX + Alpine.js) | 200+ KB (React + deps) | 0 |
| Learning curve | Bassa (HTML-first) | Media-Alta | Bassa |
| Real-time updates | HTMX polling / SSE | WebSocket / polling | Polling manuale |

**Decisione**: FastAPI con Jinja2 templates + HTMX per interazioni server + Alpine.js per interattività client-side (slider pesi, toggle, dropdown).

**SPA React/Vue scartata**: overengineering per un'app single-user. Richiede: build pipeline JS, state management (Redux/Pinia), API client, routing client-side. Il 90% dell'UI è rendering di tabelle e form — SSR è sufficiente. Lo slider pesi è l'unico componente che richiede interattività client, gestibile con Alpine.js (3 KB).

**Django Templates scartato**: richiede Django (già scartato in s03). Jinja2 è equivalente e integrato con FastAPI.

---

## Componenti UI

### 1. Search Bar Unificata
```
┌─────────────────────────────────────────────┐
│ 🔍 [Cerca ricambi...                      ] │
│    □ Ciclo Promo  □ RMS  □ Ciclodiffusione  │
└─────────────────────────────────────────────┘
```
- Input con autocomplete (HTMX `hx-trigger="keyup changed delay:300ms"`)
- Checkbox per filtrare per fornitore
- Ricerca per testo libero, SKU, o EAN

### 2. Tabella Risultati Comparativa
```
┌──────────────────┬──────────────┬──────────────┬──────────────┐
│ Prodotto         │ Ciclo Promo  │ RMS          │ Ciclodiffus. │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ Shimano XT M8100 │ €45.90 🟢    │ €47.20 🟢    │ €44.50 🟡    │
│ Catena HG701     │ €18.50 🟢    │ —            │ €19.80 🟢    │
│ Disco RT86       │ €32.00 🟡    │ €30.50 🟢    │ —            │
└──────────────────┴──────────────┴──────────────┴──────────────┘
  🟢 In stock   🟡 Low stock   🔴 Out of stock   — Non disponibile
```
- Confronto side-by-side per fornitore
- Indicatore freshness dati (da s06)
- Ordinamento per prezzo, disponibilità, nome
- Click su riga → dettaglio prodotto

### 3. Cart Composer Multi-Fornitore
```
┌─────────────────────────────────────────────┐
│ 🛒 Carrello Composizione (3 prodotti)       │
├─────────────────────────────────────────────┤
│ + Shimano XT M8100    Qty: [1]  [Rimuovi]   │
│ + Catena HG701        Qty: [2]  [Rimuovi]   │
│ + Disco RT86          Qty: [1]  [Rimuovi]   │
├─────────────────────────────────────────────┤
│ [Ottimizza Ordine]                          │
└─────────────────────────────────────────────┘
```
- Aggiunta prodotti dalla tabella risultati
- Quantità modificabile
- Pulsante "Ottimizza Ordine" → invoca solver

### 4. Slider Pesi Optimizer (Alpine.js)
```
┌─────────────────────────────────────────────┐
│ ⚙️ Pesi Ottimizzazione                      │
│                                             │
│ Costo totale    ████████░░ 50%              │
│ N. fornitori    ████░░░░░░ 20%              │
│ Tempo consegna  ██░░░░░░░░ 10%              │
│ Free shipping   ████░░░░░░ 20%              │
│                                             │
│ Preset: [Risparmio] [Veloce] [Semplice]     │
│                                             │
│ [Ricalcola]                                 │
└─────────────────────────────────────────────┘
```
- 4 slider collegati (somma = 100%), gestiti da Alpine.js
- Preset buttons per configurazioni comuni
- "Ricalcola" → POST HTMX al solver con nuovi pesi

### 5. Risultato Ottimizzazione
```
┌─────────────────────────────────────────────┐
│ ✅ Ordine Ottimizzato                        │
│                                             │
│ Fornitore 1: Ciclodiffusione (€62.30)       │
│   - Shimano XT M8100 × 1 — €44.50          │
│   - Catena HG701 × 1 — €17.80              │
│   🟢 Sopra soglia free-shipping (€50)       │
│                                             │
│ Fornitore 2: RMS (€30.50)                   │
│   - Disco RT86 × 1 — €30.50                │
│   🔴 Sotto soglia — spedizione: €6.90       │
│                                             │
│ Totale: €99.70 | 2 fornitori | Max 3 gg     │
│                                             │
│ [Apri carrello Ciclodiffusione ↗]           │
│ [Apri carrello RMS ↗]                       │
└─────────────────────────────────────────────┘
```
- Raggruppato per fornitore
- Indicatore soglia free-shipping
- Link diretti ai carrelli fornitori (apertura tab browser)

### 6. Dashboard Scraping
```
┌─────────────────────────────────────────────┐
│ 📊 Stato Sincronizzazione                   │
├──────────────┬──────────┬───────────────────┤
│ Fornitore    │ Ultimo   │ Stato             │
├──────────────┼──────────┼───────────────────┤
│ Ciclo Promo  │ 02:34    │ 🟢 45.230 prodotti│
│ RMS          │ 03:12    │ 🟢 62.180 prodotti│
│ Ciclodiffus. │ 01:58    │ 🟡 In corso (78%) │
├──────────────┴──────────┴───────────────────┤
│ [Refresh Ciclo Promo] [Refresh RMS] [All]   │
└─────────────────────────────────────────────┘
```
- Stato per fornitore con timestamp ultimo scraping
- Progress bar per job in corso (HTMX polling ogni 5s)
- Pulsanti refresh on-demand

---

## UX Flow Principale

```
Ricerca → Risultati comparativi → Selezione prodotti →
→ Carrello composizione → Configura pesi →
→ Ottimizzazione → Review ordine →
→ Link a carrelli fornitori (tab browser)
```

---

## Modello Auth Applicativo

### Decisione: accesso aperto su rete locale (decisione utente)

| Modalità | Quando | Implementazione |
|----------|--------|----------------|
| **Localhost trust** | `http://localhost:8000` | Nessuna auth, accesso diretto |
| **LAN trust** | `http://192.168.x.x:8000` | Nessuna auth (rete locale trusted per decisione utente) |
| **Tailscale/VPN** | Accesso remoto | Opzionale: Caddy reverse proxy con basic auth |

**OAuth/JWT scartato**: overengineering per single-user. Nessuna necessità di login, sessioni, token.

**Basic auth obbligatorio scartato**: l'utente ha deciso che la rete locale è trusted. Auth opzionale via Caddy per esposizione esterna.

### Session Model

- **Sessione webapp**: stateless (nessuna sessione server). Ogni richiesta è indipendente.
- **Sessioni scraping B2B**: completamente separate, gestite dai container scraper (s05). Non esposte all'UI.
- **Credential onboarding**: tramite first-run UI form o CLI command — meccanismo definito in s09.

---

## Alternative Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **SPA React** | Bundle 200+ KB, build pipeline, state management — overengineering per UI di tabelle e form |
| **SPA Vue** | Stesso problema di React, comunità più piccola |
| **HTMX puro (senza Alpine.js)** | Slider pesi richiede interattività client-side che HTMX non offre. Alpine.js (3 KB) risolve. |
| **Streamlit/Gradio** | Prototyping rapido ma non customizzabile, performance scarsa, non production-grade |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Complessità stato carrello multi-fornitore | Bug UI, stato inconsistente | Stato carrello server-side (session cookie), non client |
| UX mobile (tablet in officina) | Layout non responsive | CSS responsive base in fase 1, PWA in fase 2 |
| HTMX latenza percepita | Flicker tra richieste | Loading indicators, `hx-indicator` |
| Esposizione LAN senza auth | Chiunque sulla rete vede i dati | Decisione utente consapevole, upgrade path con Caddy |

---

## Open Questions

1. **PWA**: serve accesso offline per consultare catalogo in officina? → Fase 2
2. **Tablet layout**: quale risoluzione target per tablet? → Standard iPad (1024×768 min)
3. **Dark mode**: necessario? → Nice-to-have, non prioritario

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← s03** | Tech Stack | FastAPI + Jinja2 |
| **← s07** | Order Optimizer | API solver per pesi e risultato |
| **← s06** | Search & Indexing | API ricerca |
| **← s09** | Secrets & Security | Credential onboarding mechanism (s09 definisce, s08 consuma per UI) |
| **→ s11** | Deployment | Container webapp nel docker-compose |
