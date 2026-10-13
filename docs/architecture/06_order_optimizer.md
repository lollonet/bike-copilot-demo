---
id: ARCH-V2-06
domain: docs
status: draft
---

# 06 — Order Optimizer (Multi-Obiettivo)

> Formulazione del problema di ottimizzazione e scelta del solver.

---

## Formulazione del Problema

### Variabili Decisionali

```
x[i][j] ∈ {0, 1, ..., d[i][j]}

dove:
  i = indice prodotto richiesto (1..N)
  j = indice fornitore (1..M)
  d[i][j] = disponibilità del prodotto i presso il fornitore j
  x[i][j] = quantità del prodotto i ordinata dal fornitore j
```

### Vincoli

```
1. Soddisfazione domanda:
   ∀i: Σ_j x[i][j] = q[i]
   (la quantità totale ordinata per ogni prodotto = quantità richiesta)

2. Disponibilità:
   ∀i,j: x[i][j] ≤ d[i][j]
   (non ordinare più di quanto disponibile)

3. Non-negatività:
   ∀i,j: x[i][j] ≥ 0, intero

4. Fornitore attivo (variabile ausiliaria):
   y[j] ∈ {0, 1}
   y[j] = 1  ⟺  ∃i: x[i][j] > 0
   (y[j] indica se almeno un prodotto è ordinato dal fornitore j)

   Linearizzazione: y[j] ≥ x[i][j] / M  ∀i  (big-M)
                     y[j] ≤ Σ_i x[i][j]
```

### Funzione Obiettivo

```
Minimize:
  w1 * C_costo + w2 * C_fornitori + w3 * C_consegna + w4 * C_spedizione

dove:
  C_costo     = Σ_i Σ_j (p[i][j] * x[i][j])
                (costo totale acquisto)

  C_fornitori = Σ_j y[j]
                (numero di fornitori usati)

  C_consegna  = max_j { t[j] * y[j] }
                (tempo di consegna massimo tra i fornitori usati)

  C_spedizione = Σ_j penalty[j]
                 dove penalty[j] = shipping_cost[j] se Σ_i(p[i][j] * x[i][j]) < threshold[j]
                                   0 altrimenti
                 (penalità per mancato raggiungimento soglia free-shipping)

  w1 + w2 + w3 + w4 = 1.0  (pesi normalizzati, configurabili dall'utente)
```

### Normalizzazione Obiettivi

Ogni componente è normalizzato al range [0, 1] prima della pesatura per renderli confrontabili:

```
C_norm = (C - C_min) / (C_max - C_min)

C_min, C_max calcolati dai bound:
  C_costo_min  = Σ_i min_j(p[i][j] * q[i])  (tutto dal più economico)
  C_costo_max  = Σ_i max_j(p[i][j] * q[i])  (tutto dal più caro)
  C_fornitori_min = 1
  C_fornitori_max = M
  ...
```

---

## Decisione Solver: PuLP + CBC

| Criterio | PuLP + CBC | OR-Tools CP-SAT | Greedy Heuristic |
|----------|-----------|-----------------|-----------------|
| Optimalità | **Esatta** (ILP) | Esatta (CP) | Approssimata |
| Complessità setup | Bassa (pure Python) | Media (bindings C++) | Bassa |
| arm64 support | CBC: sì (Homebrew) | Da verificare (wheel arm64) | N/A |
| Performance 20 items × 3 suppliers | < 1s | < 1s | < 0.01s |
| Performance 100 items × 8 suppliers | ~ 1-5s | ~ 1-5s | < 0.1s |
| Gestione soglie free-ship | Con big-M linearization | Con constraint native | Euristica |
| Manutenibilità | Alta (API dichiarativa) | Media (API più verbosa) | Alta |

**Decisione**: PuLP con solver CBC. PuLP offre API Python dichiarativa per modellare problemi LP/ILP. CBC (COIN-OR Branch and Cut) è un solver open-source maturo con supporto arm64 nativo.

**OR-Tools CP-SAT scartato**: API più complessa, wheel arm64 da verificare, overkill per il volume di variabili previsto. OR-Tools è un upgrade path se la complessità del problema cresce in fase 2.

**Greedy heuristic scartato**: non garantisce ottimalità. Per un carrello di 10-20 items con soglie free-shipping, un greedy può perdere combinazioni significativamente migliori. L'ILP è computazionalmente fattibile per il volume previsto.

---

## Pesi Configurabili

Defaults e range per l'interfaccia utente (slider):

| Peso | Default | Range | Descrizione |
|------|---------|-------|-------------|
| `w1` (costo) | 0.5 | 0.0–1.0 | Minimizzare costo totale |
| `w2` (fornitori) | 0.2 | 0.0–1.0 | Minimizzare numero ordini separati |
| `w3` (consegna) | 0.1 | 0.0–1.0 | Minimizzare tempo consegna massimo |
| `w4` (spedizione) | 0.2 | 0.0–1.0 | Evitare costi spedizione (raggiungere soglie free-ship) |

I pesi vengono normalizzati a somma 1.0 dall'UI prima di invocare il solver.

### Presets

| Preset | w1 | w2 | w3 | w4 | Use Case |
|--------|----|----|----|----|----------|
| **Risparmio** | 0.7 | 0.1 | 0.0 | 0.2 | Minimizzare costo a tutti i costi |
| **Velocità** | 0.2 | 0.1 | 0.6 | 0.1 | Ricambio urgente, consegna rapida |
| **Semplicità** | 0.1 | 0.6 | 0.1 | 0.2 | Meno ordini possibili |
| **Bilanciato** | 0.4 | 0.2 | 0.1 | 0.3 | Default equilibrato |

---

## Gestione Dati Stale

L'optimizer opera su dati di disponibilità e prezzo che possono essere non aggiornati:

| Età Dati | Comportamento |
|----------|--------------|
| < 24h | Ottimizzazione normale |
| 24h–48h | Warning "prezzi/disponibilità potrebbero non essere aggiornati" |
| > 48h | Warning forte + suggerimento refresh on-demand prima di ordinare |

L'optimizer **non rifiuta** mai dati stale — la decisione è dell'utente. Ma mostra chiaramente la "freshness" dei dati usati nel risultato.

---

## Pseudo-codice Solver

```python
import pulp

def optimize_order(
    items: list[RequestedItem],      # prodotti richiesti con quantità
    suppliers: list[SupplierData],    # fornitori con listings
    weights: OptimizerWeights,       # w1, w2, w3, w4
) -> OrderBundle:

    prob = pulp.LpProblem("order_optimization", pulp.LpMinimize)

    # Variabili: x[i][j] = quantità prodotto i da fornitore j
    x = {(i, j): pulp.LpVariable(f"x_{i}_{j}", 0, avail[i][j], cat="Integer")
         for i in items for j in suppliers if avail[i][j] > 0}

    # Variabili ausiliarie: y[j] = 1 se fornitore j usato
    y = {j: pulp.LpVariable(f"y_{j}", cat="Binary") for j in suppliers}

    # Vincolo: soddisfare domanda
    for i in items:
        prob += pulp.lpSum(x[i, j] for j in suppliers if (i, j) in x) == i.quantity

    # Vincolo: attivazione fornitore (big-M)
    M = sum(i.quantity for i in items)
    for j in suppliers:
        prob += y[j] >= pulp.lpSum(x[i, j] for i in items if (i, j) in x) / M
        prob += y[j] <= pulp.lpSum(x[i, j] for i in items if (i, j) in x)

    # Funzione obiettivo (normalizzata e pesata)
    cost = pulp.lpSum(price[i][j] * x[i, j] for (i, j) in x)
    n_suppliers = pulp.lpSum(y[j] for j in suppliers)
    # ... (delivery e shipping analogamente)

    prob += weights.w1 * cost_norm + weights.w2 * suppliers_norm + ...

    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))

    return build_order_bundle(x, y, prob.status)
```

---

## Alternative Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **Greedy heuristic** | Non garantisce ottimalità. Un greedy "prendi il più economico" non considera soglie free-shipping e può produrre soluzioni significativamente peggiori. |
| **OR-Tools CP-SAT** | Overkill. API più complessa di PuLP, arm64 da verificare. Upgrade path per fase 2 se il problema cresce. |
| **Scipy minimize** | Per problemi continui, non interi. ILP richiede solver dedicato. |
| **Ottimizzazione manuale (no solver)** | Troppi combinazioni con 20 items × 3 fornitori × soglie. L'utente non può calcolare mentalmente la combinazione ottimale — è il pain point originale. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| NP-hardness per carrelli grandi | Solver timeout (>30s) | Time limit CBC a 30s, soluzione sub-ottimale accettata |
| Sensibilità ai pesi | Risultati controintuitivi con pesi estremi | Presets ragionevoli, preview risultato |
| Dati disponibilità stale | Ordine basato su stock non più reale | Freshness warning, refresh on-demand |
| Linearizzazione soglie free-ship | Big-M introduce debolezza nel rilassamento LP | CBC gestisce bene con branching, performance accettabile per volume |

---

## Open Questions

1. **Tempo risoluzione per carrello tipico**: 10-20 items × 3 fornitori con CBC? → PoC in Phase 1.5
2. **MOQ (Minimum Order Quantity)**: i fornitori hanno MOQ? → Verificare durante supplier recon
3. **Soglie free-shipping per fornitore**: quali sono? → Da configurare manualmente dall'utente
4. **Sconto volume**: i fornitori applicano sconti per quantità? → Fase 2 (non lineare, complica il modello)

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← s04** | Data Model | `supplier_listing` fornisce prezzi, disponibilità, delivery_days |
| **← s03** | Tech Stack | Python + PuLP + CBC |
| **→ s08** | UI Architecture | Slider pesi, preview risultato, composizione carrello |
| **← s06** | Search & Indexing | Risultati ricerca come input per selezione prodotti |
