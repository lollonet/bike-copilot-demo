---
id: ARCH-V2-02
domain: docs
status: draft
---

# 02 — Decisione Tech Stack

> Scelta motivata dello stack tecnologico su 6 aree decisionali.
> Vincolo architetturale: schema versionato con migration tool è **non negoziabile**.

---

## Riepilogo Decisioni

| Area | Scelta | Alternative Scartate |
|------|--------|---------------------|
| Linguaggio | **Python 3.12+** | Node.js, Go |
| Framework Web | **FastAPI** | Django, Flask |
| ORM | **SQLAlchemy 2.0** | Django ORM, Peewee |
| Database | **PostgreSQL 16** | SQLite |
| Job Queue | **Redis + RQ** | Celery, Dramatiq |
| Migration Tool | **Alembic** | Django migrations, SQL manuale |

---

## 1. Linguaggio: Python 3.12+

| Criterio | Python | Node.js | Go |
|----------|--------|---------|-----|
| Playwright support | Nativo (`playwright` PyPI) | Nativo (`playwright` npm) | Non ufficiale (community wrapper) |
| Librerie ottimizzazione | **OR-Tools, PuLP, scipy** — ecosistema maturo | Limitato (glpk.js immaturo) | Limitato |
| Scraping ecosystem | BeautifulSoup, lxml, Scrapy patterns | Cheerio, Puppeteer | Colly (HTTP-only) |
| ORM maturo | SQLAlchemy 2.0 (async) | Prisma (buono) | GORM (meno maturo) |
| Docker arm64 | Immagini ufficiali python:3.12-slim arm64 | Immagini ufficiali | Immagini ufficiali |
| Structured logging | structlog, loguru | pino | zap, zerolog |
| Typing | mypy/pyright, graduale | TypeScript (forte) | Nativo (forte) |

**Decisione**: Python. Motivazione: unico linguaggio con supporto nativo sia per Playwright sia per OR-Tools/PuLP. L'ecosistema di scraping è il più maturo. SQLAlchemy 2.0 offre async e type hints.

**Node.js scartato**: librerie di ottimizzazione LP/ILP immature. Avrebbe richiesto binding C++ custom o wrapper per OR-Tools.

**Go scartato**: nessun supporto Playwright ufficiale. Librerie ORM meno mature. Ecosistema scraping limitato a HTTP-only (Colly), insufficiente per SPA JavaScript-heavy.

---

## 2. Framework Web: FastAPI

| Criterio | FastAPI | Django | Flask |
|----------|---------|-------|-------|
| Async nativo | Sì (ASGI) | Parziale (Django 4.1+) | No (WSGI) |
| Auto OpenAPI docs | Sì (built-in) | No (drf-spectacular add-on) | No (flask-restx add-on) |
| ORM integrato | No (usa SQLAlchemy) | Sì (Django ORM) | No |
| Footprint | Leggero | Pesante (admin, auth, templates) | Leggero |
| Pydantic validation | Nativo | Serializers DRF | Manuale |

**Decisione**: FastAPI. Motivazione: async nativo (essenziale per non bloccare UI durante scraping), auto-generazione OpenAPI, validazione Pydantic, lightweight.

**Django scartato**: troppo opinionato per un'app single-user. Admin panel, auth system, template engine sono overhead non necessario. Django ORM vincolerebbe a Django migrations invece di Alembic.

**Flask scartato**: non async nativo. Richiederebbe estensioni per ogni funzionalità (validation, OpenAPI, async). FastAPI offre tutto built-in.

---

## 3. ORM: SQLAlchemy 2.0

| Criterio | SQLAlchemy 2.0 | Django ORM | Peewee |
|----------|---------------|-----------|--------|
| Async support | Sì (asyncio extension) | Parziale | No |
| Raw SQL access | Completo | Limitato | Completo |
| Migration tool | Alembic (maturo) | Built-in | Peewee-migrate (base) |
| Flessibilità query | Alta (Core + ORM) | Media | Media |
| Community | Grande | Grande (Django-specific) | Piccola |
| Type hints | Mapped columns (2.0) | Limitato | Limitato |

**Decisione**: SQLAlchemy 2.0. Motivazione: massima flessibilità per query complesse (join cross-fornitore per optimizer), async support, Alembic come migration tool best-in-class.

**Django ORM scartato**: richiederebbe Django come framework (già scartato). Non usabile standalone con FastAPI senza hack.

**Peewee scartato**: community piccola, nessun async support, migration tool limitato. Per un progetto con schema complesso e query di ottimizzazione, serve un ORM più potente.

---

## 4. Database: PostgreSQL 16

| Criterio | PostgreSQL 16 | SQLite |
|----------|--------------|--------|
| FTS | tsvector + ts_query + pg_trgm (**eccellente**) | FTS5 (buono ma meno flessibile) |
| Concurrent writes | Sì (MVCC) | Lock a livello file |
| JSONB | Sì (indicizzabile) | JSON (non indicizzabile) |
| Docker arm64 | `postgres:16-alpine` arm64 ufficiale | Embedded, no container |
| Backup | pg_dump, pg_basebackup, WAL archiving | Copia file |
| Volumi 50k-100k rows | Nessun problema | Nessun problema |

**Decisione**: PostgreSQL 16. Motivazione: FTS superiore (pg_trgm per fuzzy matching è essenziale), scritture concorrenti da scraping job paralleli, JSONB per raw_data flessibile, backup robusto.

**SQLite scartato**: lock a livello file problematico con scraping job concorrenti che scrivono. pg_trgm non disponibile. Per un'app single-user sarebbe sufficiente in lettura ma il pattern di scrittura (N scraper + webapp) richiede concorrenza vera.

---

## 5. Job Queue: Redis + RQ

| Criterio | Redis + RQ | Celery | Dramatiq |
|----------|-----------|--------|----------|
| Semplicità | **Alta** (poche righe di config) | Bassa (broker + backend + config) | Media |
| Monitoring | rq-dashboard (web) | Flower (web) | django-dramatiq |
| Affidabilità | Buona (Redis persistent) | Alta (ack, retry, result backend) | Buona |
| Docker footprint | Redis (1 container) | Redis + worker + beat (3+) | Redis + worker |
| Retry/scheduling | rq-scheduler (add-on) | Built-in (beat) | Built-in |

**Decisione**: Redis + RQ. Motivazione: semplicità. Per un sistema single-user con 3 scraping job/notte, la complessità di Celery non è giustificata. RQ + rq-scheduler copre cron notturno e job on-demand.

**Celery scartato**: overengineered per il volume. Richiede worker separato, beat scheduler, result backend. Configuration-heavy. Giustificato per sistemi distribuiti, non per single-user.

**Dramatiq scartato**: community più piccola, dipendenza django-dramatiq per monitoring. RQ è più semplice e ha rq-dashboard come monitoring built-in.

---

## 6. Migration Tool: Alembic

| Criterio | Alembic | Django Migrations | SQL Manuale |
|----------|---------|------------------|-------------|
| Compatibilità | SQLAlchemy nativo | Django ORM only | Qualsiasi |
| Auto-generate | Sì (da modelli SQLAlchemy) | Sì (da modelli Django) | No |
| Rollback | Sì (downgrade) | Sì (migrate reverse) | Manuale |
| Version control | Sì (migration files in repo) | Sì | Manuale |

**Decisione**: Alembic. **Vincolo non negoziabile**: schema versionato da giorno zero. Alembic è la scelta naturale con SQLAlchemy — auto-genera migrations dai modelli, supporta upgrade/downgrade, file di migration versionati in git.

**Django Migrations scartato**: richiede Django (già scartato).

**SQL Manuale scartato**: error-prone, nessun auto-generate, nessun rollback automatico. Inaccettabile per uno schema con 7+ entità e relazioni complesse.

---

## Checklist Compatibilità arm64 (Apple Silicon)

| Componente | Immagine Docker arm64 | Verificato |
|------------|----------------------|------------|
| Python 3.12 | `python:3.12-slim` — **ufficiale arm64** | ✅ |
| PostgreSQL 16 | `postgres:16-alpine` — **ufficiale arm64** | ✅ |
| Redis 7 | `redis:7-alpine` — **ufficiale arm64** | ✅ |
| Playwright | `mcr.microsoft.com/playwright/python` — **arm64 support** | ✅ (da verificare versione specifica) |
| OR-Tools | PyPI wheel `ortools` — **arm64 wheel disponibile** | ⚠️ Verificare versione corrente |
| rq-dashboard | Pure Python, nessun binding nativo | ✅ |

> **Open question**: verificare che OR-Tools abbia wheel arm64 aggiornato per la versione corrente. Se non disponibile, fallback a PuLP (pure Python, usa GLPK/CBC come solver esterno).

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Lock-in SQLAlchemy | Cambio ORM costoso | Improbabile: SQLAlchemy è lo standard Python. Pattern Repository mitiga. |
| Playwright arm64 performance | Scraping più lento | Benchmark in Phase 1.5 spike |
| OR-Tools arm64 compatibilità | Solver non funzionante | Fallback a PuLP + CBC (arm64 nativo) |
| RQ limiti concorrenza | Job queue satura | Con 3 job/notte + on-demand sporadici, non ragionevole. Celery come upgrade path. |

---

## Open Questions

1. **Playwright arm64 benchmark**: quanto è più lento (se lo è) rispetto a x86_64? → Phase 1.5 spike
2. **OR-Tools arm64 wheel**: è disponibile per la versione corrente? → Verificare prima dell'implementazione
3. **SQLAlchemy 2.0 async maturity**: ci sono gotcha noti con asyncpg? → Verificare in PoC

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **→ s04** | Data Model | ORM (SQLAlchemy) e DB (PostgreSQL) determinano lo schema |
| **→ s05** | Scraping Architecture | Python + Playwright determina il runtime dei connettori |
| **→ s07** | Order Optimizer | Python + OR-Tools/PuLP determina il solver |
| **→ s10** | Observability | Python → structlog per logging strutturato |
| **→ s11** | Deployment | Immagini Docker arm64 per ogni componente |
| **← s01** | Overview | Vincoli architetturali non negoziabili |
