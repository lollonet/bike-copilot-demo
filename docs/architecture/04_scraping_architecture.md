---
id: ARCH-V2-04
domain: docs
status: draft
---

# 04 — Architettura di Scraping

> Sistema di scraping autenticato per distributori B2B ciclismo.
> **PREREQUISITO**: s02 (Audit Legale) deve avere esito positivo.

---

## 1. Tecnologia Stealth

### Decisione: Playwright + playwright-stealth

Libreria `playwright` per Python con plugin stealth (`playwright-stealth` o `camoufox`) per ridurre il fingerprinting del browser headless.

| Criterio | Playwright + stealth | Selenium | HTTP-only (requests/httpx) | Patchright |
|----------|---------------------|----------|---------------------------|-----------|
| JavaScript rendering | Completo | Completo | Nessuno | Completo |
| Stealth capabilities | Buone (plugin stealth) | Limitate | N/A | Ottime (fork Playwright) |
| API moderna | Sì (async, auto-wait) | Legacy | N/A | Sì |
| Docker arm64 | Supportato | Supportato | N/A | Da verificare |
| Ecosistema Python | Maturo | Maturo | Maturo | Immaturo |
| Session management | Browser context isolati | Profile Chrome | Cookie jar | Browser context |

**Selenium scartato**: API legacy, stealth inferiore, webdriver più facilmente rilevabile da anti-bot moderni. Playwright offre auto-wait, network interception, e API async nativi.

**HTTP-only scartato**: i portali B2B pilota sono probabilmente SPA o heavy-JS. Un approccio HTTP-only non può renderizzare JavaScript, navigare form dinamiche, o gestire redirect client-side. Insufficiente per portali moderni come Ciclo Promo 2026.

**Patchright scartato**: fork di Playwright con patch anti-detection integrate. Promettente ma ecosistema immaturo, community piccola, rischio di abbandono. Il plugin stealth standard è sufficiente per fase 1 — Patchright è un upgrade path se necessario.

---

## 2. Container Isolation

Un container Docker per fornitore con separazione completa:

```
┌──────────────────────────────────────────────┐
│  docker-compose                               │
│                                               │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐│
│  │ scraper-     │  │ scraper- │  │ scraper- ││
│  │ ciclopromo   │  │ rms      │  │ ciclodif ││
│  │              │  │          │  │          ││
│  │ Playwright   │  │Playwright│  │Playwright││
│  │ Browser ctx  │  │Browser   │  │Browser   ││
│  │ Cookie vol   │  │Cookie vol│  │Cookie vol││
│  └─────────────┘  └──────────┘  └──────────┘│
│       │                │             │        │
│       └────────────────┼─────────────┘        │
│                        │                      │
│                   ┌────▼────┐                 │
│                   │  Redis  │                 │
│                   │  (RQ)   │                 │
│                   └─────────┘                 │
└──────────────────────────────────────────────┘
```

| Aspetto | Configurazione |
|---------|---------------|
| Sessione/Cookie | Volume Docker dedicato per fornitore (`vol-cookies-{supplier}`) |
| Browser profile | `user-data-dir` separato per fornitore |
| CPU limit | 1 core per container scraper |
| Memory limit | 2 GB per container scraper |
| Network | Accesso internet diretto (no proxy in fase 1) |

**Motivazione isolamento**: evitare cross-contamination di sessioni. Se un fornitore blocca il browser, gli altri non sono impattati. Upgrade path: proxy per fornitore in fase 2.

---

## 3. Session Management

### Login Flow

| Fase | Azione | Dettaglio |
|------|--------|-----------|
| 1 | **Check sessione** | Navigare a pagina protetta, verificare se redirect a login |
| 2 | **Login** | Compilare form username/password, submit |
| 3 | **Verifica successo** | Controllare presenza elemento post-login (es. "Benvenuto", carrello) |
| 4 | **Salva cookie** | Persistere cookie in storage context del browser |
| 5 | **Heartbeat** | Prima di ogni batch, ri-verificare sessione valida |

### Gestione Scadenza Cookie

```
                    ┌──────────────┐
                    │ Start batch  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Check session│
                    │   valid?     │
                    └──────┬───────┘
                     yes   │   no
                    ┌──────┘   └──────┐
                    │                  │
             ┌──────▼──┐        ┌─────▼──────┐
             │ Procedi  │        │ Auto re-   │
             │ scraping │        │ login      │
             └──────────┘        └─────┬──────┘
                                       │
                                ┌──────▼───────┐
                                │  Successo?   │
                                └──────┬───────┘
                                 yes   │   no
                                ┌──────┘   └──────┐
                                │                  │
                         ┌──────▼──┐        ┌─────▼──────┐
                         │ Procedi  │        │ Retry ×3   │
                         │ scraping │        │ poi notifica│
                         └──────────┘        │ utente     │
                                             └────────────┘
```

- **Re-login automatico**: fino a 3 tentativi con delay crescente (5s, 15s, 30s)
- **Notifica utente**: dopo 3 fallimenti consecutivi → alert (email/Telegram, vedi s10)
- **Safety**: re-login forzato prima di ogni batch notturno come misura preventiva

---

## 4. Supplier Reconnaissance

Template per ciascun fornitore. **Da compilare durante Phase 1.5 spike.**

### Ciclo Promo Components SpA (`ciclopromo-b2b.com`)

| Campo | Valore |
|-------|--------|
| URL login | **TBD** |
| Tipo form login | **TBD** (standard form / OAuth / 2FA?) |
| Anti-bot rilevato | **TBD** (Cloudflare / reCAPTCHA / custom / nessuno) |
| Stack frontend | **TBD** (SPA React/Vue / server-rendered / ibrido) |
| Pattern ricerca | **TBD** (search bar, filtri, categorie) |
| Paginazione | **TBD** (infinite scroll / pagine numerate / load more) |
| Campi dati esposti | **TBD** (nome, SKU, prezzo, disponibilità, EAN, immagini) |
| Rate limit osservato | **TBD** |

### RMS (`rms.it`)

| Campo | Valore |
|-------|--------|
| URL portale B2B | **TBD** (rms.it/area-riservata? sottodominio?) |
| URL login | **TBD** |
| Filtro categoria ciclo | **TBD** (come isolare prodotti ciclo da moto/scooter) |
| Anti-bot rilevato | **TBD** |
| Stack frontend | **TBD** |
| Campi dati esposti | **TBD** |

### Ciclodiffusione SRL (`ciclodiffusione.com`)

| Campo | Valore |
|-------|--------|
| URL login | `ciclodiffusione.com/login` |
| Tipo form login | **TBD** (probabilmente form standard PHP) |
| Anti-bot rilevato | **TBD** (probabile: nessuno, stack legacy) |
| Stack frontend | **TBD** (probabile PHP/Magento/Prestashop) |
| Paginazione | **TBD** (probabilmente pagine numerate) |
| Campi dati esposti | **TBD** |

---

## 5. Strategia Captcha

| Priorità | Strategia | Quando |
|----------|-----------|--------|
| 1 | **Stealth** — evitare di triggerare captcha | Sempre (plugin stealth, timing umano, jitter) |
| 2 | **Whitelist IP** — contattare fornitore per esclusione | Se captcha persistente, nell'email di autorizzazione (s02) |
| 3 | **Solve manuale via UI** — notifica utente, pausa scraping | Se stealth insufficiente e whitelist non ottenuta |
| 4 | **Ridurre aggressività** — meno pagine/batch, delay maggiori | Se tutto il resto fallisce |

> **Nota**: servizi di solving automatico (2Captcha, Anti-Captcha) esclusi per fase 1 — costo ricorrente, problemi etici, non necessario per 3 fornitori con basso volume.

---

## 6. Scheduling

| Tipo | Trigger | Frequenza | Scope |
|------|---------|-----------|-------|
| **Batch notturno** | Cron (rq-scheduler) | 1×/notte, default 02:00 | Catalogo completo per fornitore |
| **On-demand** | Ricerca utente | Ad ogni ricerca se dati stale (>24h) | Singolo prodotto/query |
| **Retry falliti** | Automatico | 15 min dopo fallimento, max 3 retry | Items falliti del batch |

Ordine batch notturno: **sequenziale** per fornitore (non parallelo) per ridurre carico risorse e rischio anti-bot.

Sequenza: Ciclodiffusione (legacy, più veloce) → Ciclo Promo → RMS (più complesso).

---

## 7. Rate Limiting

| Parametro | Default | Configurabile |
|-----------|---------|--------------|
| Delay tra richieste | 2–5s random (uniform) | Sì, per fornitore |
| Backoff su errore | Esponenziale, base 2s, max 60s, con jitter ±20% | Sì |
| Browser per fornitore | 1 (singola istanza) | No (vincolato da isolamento container) |
| Pagine per sessione | Max 500 prima di pausa 5 min | Sì, per fornitore |
| robots.txt | Rispettato se presente crawl-delay | Sempre |

---

## 8. Connector Pattern (interfaccia pluggable)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RawProduct:
    supplier_sku: str
    name: str
    brand: str | None
    price: float | None
    currency: str
    availability: str  # "in_stock" | "low_stock" | "out_of_stock" | "unknown"
    delivery_days: int | None
    ean: str | None
    url: str
    raw_data: dict  # dati grezzi completi dal portale

class SupplierConnector(ABC):
    """Interfaccia per connettori fornitore. Ogni fornitore implementa questa ABC."""

    @abstractmethod
    async def login(self, username: str, password: str) -> bool:
        """Autentica sul portale B2B. Ritorna True se login riuscito."""
        ...

    @abstractmethod
    async def check_session_valid(self) -> bool:
        """Verifica se la sessione corrente è ancora valida."""
        ...

    @abstractmethod
    async def search(self, query: str) -> list[RawProduct]:
        """Cerca prodotti per testo libero."""
        ...

    @abstractmethod
    async def get_product(self, supplier_sku: str) -> RawProduct | None:
        """Recupera dettaglio singolo prodotto per SKU fornitore."""
        ...

    @abstractmethod
    async def get_catalog_page(self, page: int) -> list[RawProduct]:
        """Recupera una pagina del catalogo completo. Ritorna lista vuota se pagina oltre il totale."""
        ...

    @abstractmethod
    async def get_total_pages(self) -> int:
        """Ritorna il numero totale di pagine del catalogo."""
        ...
```

Nuovi fornitori si aggiungono implementando `SupplierConnector`. Il sistema li registra via configurazione (`supplier.scraping_config`).

---

## 9. Strategia Initial Data Backfilling

Per il primo import completo del catalogo:

| Aspetto | Strategia |
|---------|-----------|
| **Resumability** | Tracciare `last_page_scraped` in `scraping_job`. Su failure, riprendere dalla pagina successiva. |
| **Error budget** | Max 5% items falliti per batch. Se superato, interrompere e loggare. |
| **Durata stimata** | **TBD** per fornitore (open question per Phase 1.5 spike). Stima grezza: 50k prodotti × 3s/prodotto = ~42 ore per fornitore. Con paginazione (50 prodotti/pagina, 2s/pagina): ~33 minuti. |
| **Parallelismo** | Nessuno in fase 1 (sequenziale per pagina). |
| **Validazione** | Post-import: conteggio items, % con EAN, % con prezzo, anomalie. |

---

## 10. Feasibility Checkpoint

Dopo la supplier reconnaissance, per ciascun fornitore valutare:

| Criterio | GO | NO-GO |
|----------|----|----|
| Login automatico | Funziona in headless | Richiede 2FA o CAPTCHA non bypassabile |
| Anti-bot | Stealth sufficiente O whitelist ottenuta | Blocco persistente dopo tentativi |
| Dati estraibili | Nome, prezzo, disponibilità presenti | Dati critici non accessibili |
| Rate limit | Accettabile per batch notturno | Troppo restrittivo (ban dopo poche pagine) |
| Stabilità DOM | Struttura prevedibile, selettori CSS affidabili | DOM random/obfuscato |

---

## Alternative Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **Selenium** | API legacy, webdriver facilmente rilevabile, stealth inferiore. Playwright è il successore naturale. |
| **HTTP-only (requests/httpx)** | Portali B2B pilota probabilmente JS-heavy (SPA). Non può renderizzare JavaScript. |
| **Patchright** | Fork Playwright con patch anti-detection. Promettente ma immatura. Upgrade path per fase 2. |
| **Browser reale con user-data-dir** | Più difficile da containerizzare, gestione sessioni più complessa. Playwright context isolati sono equivalenti. |
| **Scrapy framework** | Orientato a HTTP crawling, non a browser automation. Non adatto per SPA con login. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Evoluzione anti-bot | Stealth diventa insufficiente | Upgrade a Patchright, contatto fornitore, riduzione frequenza |
| Fragilità DOM | Redesign portale rompe selettori | Test di regressione per connettore, alert su scraping failure |
| Race condition scadenza sessione | Scraping fallisce a metà batch | Check sessione pre-pagina, re-login automatico |
| Performance Playwright arm64 | Scraping più lento del previsto | Benchmark in Phase 1.5, ottimizzazione timing |

---

## Open Questions

1. **Latenza scraping per fornitore**: quanto tempo per un catalogo completo? → Phase 1.5 spike
2. **Stealth vs stack specifici**: Playwright stealth funziona contro i 3 portali? → Phase 1.5 spike
3. **Durata initial backfill**: stimata 30-60 min/fornitore ma da verificare → Phase 1.5 spike
4. **Proxy per fornitore**: necessario in fase 1? → Probabilmente no, upgrade path fase 2

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← s02** | Legal Audit | **PREREQUISITO BLOCCANTE** — s05 non procede senza esito positivo s02 |
| **← s03** | Tech Stack | Python + Playwright definiscono il runtime |
| **→ s04** | Data Model | Gli scraper scrivono `supplier_listing` e `scraping_job` |
| **→ s11** | Deployment | Container scraper definiti nel docker-compose |
| **→ s10** | Observability | `correlation_id` per ogni scraping job |
