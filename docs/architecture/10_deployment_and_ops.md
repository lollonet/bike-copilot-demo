---
id: ARCH-V2-10
domain: docs
status: draft
---

# 10 — Deployment & Operations

> Docker Compose, backup, upgrade, rollback, arm64 compatibility.

---

## docker-compose.yml Illustrativo

```yaml
version: "3.9"

services:
  # ── Web Application ──────────────────────────────
  webapp:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://bike:bike@db:5432/bikeparts
      - REDIS_URL=redis://redis:6379/0
      - SOPS_AGE_KEY_FILE=/run/secrets/age-key
    volumes:
      - ./secrets.enc.yaml:/app/secrets.enc.yaml:ro
      - app-logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G
    secrets:
      - age-key

  # ── Database ─────────────────────────────────────
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: bikeparts
      POSTGRES_USER: bike
      POSTGRES_PASSWORD_FILE: /run/secrets/db-password
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bike -d bikeparts"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
    secrets:
      - db-password

  # ── Redis (Job Queue + Cache) ────────────────────
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M

  # ── RQ Worker ────────────────────────────────────
  rq-worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: rq worker --with-scheduler
    environment:
      - DATABASE_URL=postgresql+asyncpg://bike:bike@db:5432/bikeparts
      - REDIS_URL=redis://redis:6379/0
      - SOPS_AGE_KEY_FILE=/run/secrets/age-key
    volumes:
      - ./secrets.enc.yaml:/app/secrets.enc.yaml:ro
      - scraper-cookies:/app/cookies
      - app-logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G  # Playwright browser instances
    secrets:
      - age-key

  # ── RQ Dashboard (monitoring) ────────────────────
  rq-dashboard:
    image: eoranged/rq-dashboard
    ports:
      - "9181:9181"
    environment:
      - RQ_DASHBOARD_REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 128M

  # ── Caddy (opzionale, reverse proxy + auth) ──────
  # Decommentare per esposizione LAN/Tailscale con basic auth
  # caddy:
  #   image: caddy:2-alpine
  #   ports:
  #     - "443:443"
  #     - "80:80"
  #   volumes:
  #     - ./Caddyfile:/etc/caddy/Caddyfile:ro
  #     - caddy-data:/data
  #   depends_on:
  #     - webapp

volumes:
  pgdata:
    driver: local
  redisdata:
    driver: local
  scraper-cookies:
    driver: local
  app-logs:
    driver: local
  # caddy-data:
  #   driver: local

secrets:
  age-key:
    file: ~/.config/sops/age/keys.txt
  db-password:
    file: ./secrets/db-password.txt
```

> **Nota**: i container scraper per fornitore (`scraper-ciclopromo`, `scraper-rms`, `scraper-ciclodiffusione`) sono gestiti come RQ job eseguiti dal `rq-worker`. In fase 1 un singolo worker gestisce tutti i fornitori sequenzialmente. In fase 2, worker dedicati per fornitore con container separati.

---

## Checklist arm64 (Apple Silicon)

| Componente | Immagine | arm64 | Note |
|-----------|----------|-------|------|
| Python 3.12 | `python:3.12-slim` | ✅ Multi-arch ufficiale | |
| PostgreSQL 16 | `postgres:16-alpine` | ✅ Multi-arch ufficiale | |
| Redis 7 | `redis:7-alpine` | ✅ Multi-arch ufficiale | |
| Playwright | Chromium via `playwright install` | ✅ arm64 Chromium disponibile | Verificare versione specifica |
| Caddy 2 | `caddy:2-alpine` | ✅ Multi-arch ufficiale | |
| rq-dashboard | `eoranged/rq-dashboard` | ⚠️ Verificare | Potrebbe richiedere build locale |
| OR-Tools / PuLP | PyPI wheel | ⚠️ CBC arm64 via Homebrew | PuLP usa CBC come subprocess |

---

## Backup Strategy

### Database

| Metodo | Frequenza | Destinazione | Retention |
|--------|-----------|-------------|-----------|
| `pg_dump` | Giornaliero (post-scraping, ~04:00) | NAS locale o volume esterno | 30 giorni |
| WAL archiving | Continuo (se configurato) | NAS | 7 giorni |

```bash
# Cron script backup
docker compose exec -T db pg_dump -U bike -Fc bikeparts > \
  /mnt/nas/backup/bikeparts_$(date +%Y%m%d_%H%M%S).dump

# Cleanup backup vecchi
find /mnt/nas/backup/ -name "bikeparts_*.dump" -mtime +30 -delete
```

### Volumi Docker

| Volume | Backup | Frequenza |
|--------|--------|-----------|
| `pgdata` | Via pg_dump (sopra) | Giornaliero |
| `redisdata` | Non necessario (cache ricostruibile) | Mai |
| `scraper-cookies` | Non necessario (re-login automatico) | Mai |
| `app-logs` | Opzionale (copia su NAS) | Settimanale |

### File Secrets

| File | Backup | Dove |
|------|--------|------|
| `secrets.enc.yaml` | In git (cifrato) | Repository |
| `~/.config/sops/age/keys.txt` | **CRITICO** — backup manuale | USB cifrata + NAS |

---

## Upgrade Procedure

```
1. git pull                              # Aggiorna codice
2. docker compose pull                   # Pull nuove immagini base
3. docker compose exec -T db pg_dump ... # Backup DB pre-upgrade
4. docker compose run --rm webapp alembic upgrade head  # Migrate DB
5. docker compose up -d --build          # Rebuild e restart
6. docker compose exec webapp curl -f http://localhost:8000/health  # Verify
```

### Rollback

```
1. docker compose down
2. docker compose run --rm webapp alembic downgrade -1  # Rollback migration
3. git checkout <previous-tag>
4. docker compose up -d --build
5. # Se DB corrotto: restore da backup
   docker compose exec -T db pg_restore -U bike -d bikeparts < backup.dump
```

---

## Health Checks

| Servizio | Endpoint / Comando | Intervallo |
|----------|-------------------|------------|
| Webapp | `GET /health` → 200 | 30s |
| PostgreSQL | `pg_isready -U bike` | 10s |
| Redis | `redis-cli ping` | 10s |
| RQ Worker | `rq info` (via script) | 60s |

---

## Resource Budget (Mac Studio M4 Max, 128GB)

| Servizio | CPU | RAM | Totale |
|----------|-----|-----|--------|
| Webapp | 2 core | 1 GB | |
| PostgreSQL | 2 core | 2 GB | |
| Redis | 0.5 core | 512 MB | |
| RQ Worker (+ Playwright) | 2 core | 4 GB | |
| RQ Dashboard | 0.25 core | 128 MB | |
| **Totale** | **6.75 core** | **~7.6 GB** | |
| **Disponibile** | 14 core | 128 GB | **headroom enorme** |

> Il Mac Studio M4 Max ha risorse largamente sovrabbondanti. Nessun rischio di contention. In fase 2 con worker dedicati per fornitore, il totale salirebbe a ~15 GB — ancora confortevole.

---

## Alternative Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **Kubernetes** | Orchestrazione per cluster multi-nodo. Single-node con Docker Compose è ordini di grandezza più semplice. K8s aggiungerebbe: etcd, control plane, ingress controller, PVC — complessità ingiustificata. |
| **Podman** | Alternativa Docker daemon-less. Compatibilità compose ancora inferiore, community più piccola su macOS. Docker Desktop con Apple Silicon funziona bene. |
| **Docker Swarm** | Multi-node orchestration. Non necessario per single-node. |
| **systemd services** | Nativo Linux, non disponibile su macOS. Docker Compose è cross-platform. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Single-point-of-failure (Mac Studio) | Downtime totale | Backup su NAS, recovery procedure documentata |
| Corruzione DB senza backup | Perdita dati catalogo | pg_dump giornaliero, test restore mensile |
| Docker Desktop update breaking | Container non partono | Pin Docker Desktop version, test pre-update |
| Disco pieno (log + DB) | Servizi crashano | Monitoring disk space (s10), retention policy |

---

## Open Questions

1. **Frequenza backup**: giornaliero sufficiente o serve WAL archiving continuo? → Giornaliero per fase 1
2. **Disaster recovery target**: quanto tempo per ripristinare da zero? → Proposta: max 1 ora (include restore DB + rebuild container)
3. **NAS specifico**: quale NAS o S3-compatibile per backup? → Da decidere (utente)

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← tutte** | s03–s10 | Ogni servizio nel docker-compose è definito nelle sezioni precedenti |
| **← s09** | Secrets | Volume mount per secrets, age key |
| **← s10** | Observability | Volume log, metriche |
| **← s05** | Scraping | Worker configuration, cookie volumes |
