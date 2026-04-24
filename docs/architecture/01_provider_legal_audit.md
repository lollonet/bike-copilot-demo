---
id: ARCH-V2-01
domain: docs
status: draft
---

# 01 — Audit Legale Fornitori & Gate Go/No-Go

> Prerequisito etico e pratico per l'architettura di scraping.
> Questa sezione è un **PREREQUISITO BLOCCANTE** per s05 (Scraping Architecture).

---

## Tabella Fornitori

| Fornitore | URL Portale B2B | URL ToS | Permesso Scraping Autenticato | Procedura Autorizzazione |
|-----------|----------------|---------|-------------------------------|--------------------------|
| Ciclo Promo Components SpA | `ciclopromo-b2b.com` | **Da identificare** — cercare link "Termini e Condizioni" / "Condizioni d'Uso" nel footer del portale B2B | **Da chiarire** | 1. Leggere ToS, 2. Inviare email con template sotto, 3. Attendere risposta |
| RMS | `rms.it` (area B2B da identificare) | **Da identificare** — verificare se esiste area riservata con ToS separati dal sito pubblico | **Da chiarire** | 1. Identificare portale B2B esatto, 2. Leggere ToS, 3. Inviare email |
| Ciclodiffusione SRL | `ciclodiffusione.com` (login: `/login`) | **Da identificare** — verificare pagina "Termini e Condizioni" o link nel footer | **Da chiarire** | 1. Leggere ToS, 2. Inviare email con template sotto, 3. Attendere risposta |

> **Nota**: Tutti e tre i fornitori partono come "da chiarire" perché i ToS non sono ancora stati verificati. La verifica è un deliverable di questa sezione, non un'assunzione.

---

## Template Lettera Richiesta Autorizzazione

```
Oggetto: Richiesta autorizzazione accesso automatizzato al portale B2B

Spettabile [Nome Fornitore],

sono [Nome], titolare del negozio [Nome Negozio] (P.IVA [XXX]), Vostro cliente
con account B2B attivo (codice cliente: [XXX]).

Vi scrivo per richiedere formalmente l'autorizzazione a utilizzare strumenti
di automazione per accedere al Vostro portale B2B con le mie credenziali.

Lo scopo è esclusivamente personale: velocizzare la consultazione del Vostro
catalogo per confrontare prezzi e disponibilità con altri fornitori, nell'ambito
della gestione quotidiana del mio negozio.

L'accesso automatizzato:
- utilizza le MIE credenziali B2B esistenti
- rispetta le stesse limitazioni del mio account
- non effettua ordini automatici (solo consultazione)
- opera con frequenza contenuta (1 aggiornamento catalogo/giorno, tipicamente notturno)
- non condivide né redistribuisce i dati consultati

Resto a disposizione per qualsiasi chiarimento o per concordare modalità tecniche
(es. whitelist IP, limiti di frequenza) che riteniate opportune.

Cordiali saluti,
[Nome Cognome]
[Telefono]
[Email]
```

---

## Matrice Rischio Legale

| Fornitore | Rischio Divieto Esplicito | Rischio Enforcement | Rischio Tecnico (Anti-bot) | Rischio Complessivo |
|-----------|--------------------------|--------------------|-----------------------------|---------------------|
| Ciclo Promo | Medio — portale nuovo 2026, ToS potenzialmente aggiornati | Basso — uso personale, singolo utente | Medio — da verificare stack frontend | **MEDIO** |
| RMS | Medio — portale enterprise, ToS probabilmente restrittivi | Medio — azienda strutturata | Alto — "cutting-edge" suggerisce protezioni moderne | **MEDIO-ALTO** |
| Ciclodiffusione | Basso — portale legacy, ToS probabilmente generici | Basso — realtà più piccola | Basso — stack legacy più semplice | **BASSO-MEDIO** |

---

## Gate Go/No-Go

### Soglia (Moderata — decisione utente)

Il progetto procede se **almeno 2 fornitori su 3** soddisfano TUTTE le seguenti condizioni:

| Criterio | Misurabilità |
|----------|-------------|
| ToS letti e analizzati | Documento con citazioni clausole rilevanti |
| Nessun divieto esplicito di automazione nei ToS | Analisi testuale documentata |
| Procedura autorizzazione avviata (email inviata) | Copia email con data invio |
| Nessuna risposta negativa esplicita ricevuta | Tracking risposte in questa tabella |

### Scenari di Esito

| Esito | Azione |
|-------|--------|
| **3/3 fornitori OK** | Procedi con architettura completa |
| **2/3 fornitori OK** | Procedi con 2 fornitori, fornitore escluso documentato come candidato fase 2 |
| **1/3 fornitori OK** | **STOP** — valore dell'aggregatore insufficiente con un solo fornitore. Rivalutare approccio (partnership formale? API?). |
| **0/3 fornitori OK** | **STOP** — progetto non praticabile con approccio scraping. Considerare pivot completo. |

---

## Fallback: Esclusione Fornitore

Se un fornitore viene escluso (divieto esplicito o impraticabilità operativa):

1. **Documentare** il motivo di esclusione nel registro fornitori
2. **Rimuovere** il connettore dalla configurazione attiva
3. **Valutare sostituti** dalla lista fase 2: BRN Bike Parts, ICAR, Roadrun B2B, Hartje
4. **Ridimensionare aspettative**: con 2 fornitori l'optimizer ha meno scelta, soglie free-shipping meno ottimizzabili

Se si scende a **1 solo fornitore** il sistema perde il valore di aggregazione. In quel caso:
- Il sistema resta utile come cache locale / consultazione rapida
- L'ottimizzazione multi-fornitore è disabilitata
- Priorità massima all'onboarding di un secondo fornitore

---

## Considerazioni GDPR

| Aspetto | Analisi |
|---------|---------|
| **Dati trattati** | Credenziali B2B (username/password) di terzi (i fornitori) |
| **Base giuridica** | Legittimo interesse (art. 6.1.f GDPR): l'utente usa le proprie credenziali per proprio uso professionale |
| **Titolare** | L'utente stesso (singolo negoziante) |
| **Conservazione** | Credenziali cifrate (age/sops o Docker secrets). Retention: finché l'account B2B è attivo |
| **Cancellazione** | Procedura documentata in s09 per rimozione sicura credenziali |
| **Rischio** | Basso — dati personali minimi, uso in ambito professionale proprio, nessuna condivisione con terzi |

> **Nota**: il GDPR si applica al trattamento di dati personali. Le credenziali B2B sono dati dell'utente stesso, non di terzi. Il rischio GDPR è minimo ma la gestione sicura resta obbligatoria per proteggere l'accesso ai portali fornitori.

---

## Alternative Scartate

| Alternativa | Motivazione dello Scarto |
|-------------|-------------------------|
| **Reverse-engineering API non documentate** | Più fragile dello scraping UI (endpoint possono cambiare senza preavviso), potenzialmente più problematico legalmente (accesso a interfacce non destinate al pubblico) |
| **Partnership formale con fornitore** | Richiede negoziazione commerciale, tempi lunghi (mesi), probabilmente non disponibile per singolo negoziante. Opzione fase 2 se il volume giustifica l'investimento. |
| **Acquisto dati catalogo** | Nessun fornitore pilota offre feed dati strutturati. Servizi terzi di aggregazione dati non coprono il B2B ciclistico italiano. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| **Cambio ToS unilaterale** | Un fornitore aggiunge divieto esplicito dopo l'autorizzazione | Monitoraggio periodico ToS (trimestrale), procedura di disattivazione connettore |
| **Enforcement selettivo** | Un fornitore blocca l'account senza preavviso | Backup credenziali, account separato per scraping se disponibile |
| **Mancata risposta** | Fornitore non risponde all'email di autorizzazione | Dopo 30 giorni senza risposta: procedere (assenza di divieto esplicito), documentare |

---

## Open Questions

1. **Tempi di risposta fornitori**: quanto tempo concedere prima di considerare "nessuna risposta = assenza di divieto"? → Proposta: 30 giorni
2. **Rinnovo autorizzazione**: l'autorizzazione va rinnovata periodicamente? → Proposta: verifica annuale
3. **Account dedicato**: è possibile/consigliabile creare un account B2B dedicato all'automazione? → Da valutare per fornitore

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **→ s05** | Scraping Architecture | **s02 è PREREQUISITO BLOCCANTE per s05.** L'architettura di scraping non può essere finalizzata finché il legal audit non ha esito positivo (almeno 2/3 fornitori OK). |
| **← s01** | Overview | Contesto di sistema e lista fornitori |
| **→ s09** | Secrets & Security | GDPR e gestione credenziali |
