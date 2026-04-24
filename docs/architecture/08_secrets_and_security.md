---
id: ARCH-V2-08
domain: docs
status: draft
---

# 08 — Secrets & Security

> Gestione credenziali B2B, threat model, credential onboarding.

---

## Decisione: age/sops per Secrets Management

| Criterio | age/sops | Docker Secrets | HashiCorp Vault |
|----------|---------|----------------|-----------------|
| Complessità | Bassa (file cifrato in repo) | Bassa (compose-native) | Alta (server dedicato) |
| Versionamento | Sì (file cifrato committabile) | No (runtime only) | Sì (backend) |
| Rotation | Manuale (re-encrypt) | Manuale (recreate) | Automatica |
| Audit trail | Git history del file cifrato | Nessuno | Completo |
| Footprint | Zero (CLI tool) | Zero (Docker native) | Container dedicato |
| Key management | age key file locale | Docker swarm (overkill) | Unsealing, HA |

**Decisione**: `sops` con backend `age` per cifrare un file YAML/JSON contenente le credenziali B2B. Il file cifrato è committabile in git (solo il contenuto è cifrato, la struttura è leggibile). La chiave age risiede sul Mac Studio in `~/.config/sops/age/keys.txt`.

**Docker Secrets scartato**: richiede Docker Swarm mode per funzionare nativamente. In Docker Compose standalone, i "secrets" sono semplici file montati — nessuna cifratura reale. Sarebbe un falso senso di sicurezza.

**HashiCorp Vault scartato**: overkill per single-user. Richiede container dedicato, unsealing, HA configuration. Progettato per team/organizzazioni con centinaia di secrets. Complessità operativa non giustificata.

### Struttura File Secrets

```yaml
# secrets.enc.yaml (cifrato con sops + age)
suppliers:
  ciclopromo:
    username: "mario.rossi@negozio.it"
    password: "***"
    login_url: "https://ciclopromo-b2b.com/login"
  rms:
    username: "mario.rossi@negozio.it"
    password: "***"
    login_url: "https://rms.it/b2b/login"
  ciclodiffusione:
    username: "mario.rossi@negozio.it"
    password: "***"
    login_url: "https://www.ciclodiffusione.com/login"
```

```bash
# Cifrare
sops --encrypt --age $(cat ~/.config/sops/age/keys.txt | grep "public key" | cut -d: -f2 | tr -d ' ') \
  secrets.yaml > secrets.enc.yaml

# Decifrare (runtime, in memoria)
sops --decrypt secrets.enc.yaml
```

---

## Rotation Strategy

### Procedura Manuale con Checklist

| Step | Azione | Frequenza |
|------|--------|-----------|
| 1 | Cambiare password sul portale B2B del fornitore | Ogni 6 mesi o su sospetto compromissione |
| 2 | Aggiornare `secrets.enc.yaml` con nuova password | Immediato dopo step 1 |
| 3 | Re-cifrare con `sops` | Automatico (sops modifica in-place) |
| 4 | Restart container scraper del fornitore interessato | Immediato |
| 5 | Verificare login automatico funzionante | Test manuale post-rotation |
| 6 | Committare file cifrato aggiornato | Git commit con messaggio "rotate: [supplier]" |

### Alert Scadenza

- Reminder configurabile (default: ogni 180 giorni) via cron job locale
- Notifica su canale alerting (Telegram/email, vedi s10)
- **Nessuna scadenza automatica**: l'utente decide quando ruotare

---

## Credential Onboarding

### Meccanismo: CLI command (first-run)

```bash
# Prima configurazione
./manage.py add-supplier \
  --name ciclopromo \
  --username mario.rossi@negozio.it \
  --password  # prompt interattivo, no echo

# Il comando:
# 1. Valida i campi
# 2. Aggiunge al file secrets.yaml
# 3. Re-cifra con sops
# 4. Crea record supplier nel DB
# 5. Testa il login sul portale B2B
```

**Alternativa fase 2**: form UI per gestione credenziali (aggiunta, modifica, test login).

**UI form immediata scartata**: per fase 1 la CLI è sufficiente (setup one-time per 3 fornitori). Una UI per credenziali aggiunge superficie di attacco (form con password in HTML, CSRF, etc.).

---

## Threat Model Single-User

### Superfici di Attacco

| Superficie | Rischio | Severità | Mitigazione |
|-----------|---------|----------|-------------|
| **Host compromesso** | Accesso a tutto (DB, secrets, sessioni) | Critico | Fuori scope — se il Mac Studio è compromesso, tutto è compromesso. Mitigazione: OS updates, firewall macOS, FileVault. |
| **LAN exposure** | Chiunque sulla rete vede l'app | Basso | Decisione utente: rete trusted. Upgrade path: Caddy basic auth. |
| **Credenziali in memoria** | Container scraper ha password in RAM | Medio | Docker memory limits, no swap, container isolati. Le credenziali sono in memoria solo durante il login. |
| **File secrets non cifrato** | Password in chiaro su disco | Alto | `sops` + `age` — file sempre cifrato at rest. Key age protetta da permessi filesystem. |
| **Backup non cifrato** | DB dump contiene dati commerciali (prezzi, stock) | Medio | Backup su NAS/volume cifrato. DB non contiene password (sono in sops). |
| **Tailscale/VPN exposure** | Accesso da remoto senza auth | Medio | Tailscale ha propria autenticazione. Opzionale: Caddy basic auth davanti. |

### Trust Boundaries

```
┌─────────────────────────────────────┐
│  TRUSTED ZONE (Mac Studio)          │
│                                     │
│  ┌──────────┐  ┌────────────────┐  │
│  │ Webapp   │  │ Scraper        │  │
│  │ (no auth)│  │ containers     │  │
│  └──────────┘  └────────────────┘  │
│  ┌──────────┐  ┌────────────────┐  │
│  │ PostgreSQL│  │ Redis          │  │
│  └──────────┘  └────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │ secrets.enc.yaml (age/sops)  │  │
│  └──────────────────────────────┘  │
│                                     │
├─────────── TRUST BOUNDARY ──────────┤
│                                     │
│  LAN (trusted per decisione utente) │
│  Tailscale (opz. Caddy basic auth)  │
│                                     │
├─────────── TRUST BOUNDARY ──────────┤
│                                     │
│  Internet (portali B2B fornitori)   │
│                                     │
└─────────────────────────────────────┘
```

---

## HTTPS Locale

| Opzione | Quando | Come |
|---------|--------|------|
| **No HTTPS** | Localhost only | Default — HTTP su localhost è sicuro |
| **mkcert** | LAN access | Certificato self-signed locale, browser trust via CA locale |
| **Caddy auto-HTTPS** | Tailscale/dominio | Caddy ottiene certificato Let's Encrypt automaticamente |

**Fase 1**: no HTTPS (localhost). **Fase 2**: Caddy se esposto via Tailscale.

---

## Alternative Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **Plain .env** | Vietato da costituzione architetturale. Password in chiaro, committabile per errore, nessuna cifratura. |
| **HashiCorp Vault** | Container dedicato, unsealing, HA — overengineering per 3 password. |
| **AWS Secrets Manager / GCP Secret Manager** | Cloud-only, viola vincolo self-hosted. |
| **Keyring OS (macOS Keychain)** | Non accessibile da container Docker senza bridge complesso. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Compromissione host = compromissione totale | Critico | Fuori scope per single-user self-hosted. OS hardening base. |
| Key age persa = secrets irrecuperabili | Alto | Backup key age su supporto separato (USB, NAS) |
| Rotation dimenticata | Medio | Alert scadenza configurabile |
| sops/age breaking change | Basso | Pin versione, backup file decifrato offline |

---

## Open Questions

1. **Frequenza rotation**: ogni 6 mesi è sufficiente per credenziali B2B? → Dipende da policy fornitori
2. **Impatto rotation su sessioni attive**: un cambio password invalida immediatamente la sessione scraping? → Testare per fornitore
3. **Backup key age**: dove conservare in modo sicuro? → Proposta: USB cifrata + NAS

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **→ s05** | Scraping Architecture | Scraper legge credenziali decifrate al login |
| **→ s08** | UI Architecture | Credential onboarding (CLI in fase 1, UI in fase 2) |
| **→ s11** | Deployment | Volume mount per secrets.enc.yaml, age key |
| **← s02** | Legal Audit | GDPR su conservazione credenziali |
