# Runbook 10 — Estrazione policy di spedizione/soglie dai siti dealer

Obiettivo
- Estrarre in modo deterministico (e testabile) i costi/spedizioni standard e soglie “gratis oltre X €”.

Passi
- Individua le pagine “Spedizioni/Condizioni/FAQ”.
- Applica parser regolistici (regex su importi, parole chiave) per base_cost/free_threshold/lead_days_std.
- Salva in DealerPolicy con `source=rules` e `confidence`.
- (Opz.) Probing carrello per validare (CAP standard); LLM batch solo se necessario, con guardrail e flag “da verificare”.

Esiti
- L’ottimizzatore usa le policy; l’operatore può fare override manuale.
