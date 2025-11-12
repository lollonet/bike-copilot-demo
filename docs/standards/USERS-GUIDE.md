---
title: Guida Utente — PR e Autocheck
---

PR e trigger Codex
- Per ogni PR che modifica codice, aggiungi un commento: `@codex review`.
- Una Action garantisce il commento se manca quando la PR (non draft) include file in `app/ src/ scripts/ providers/ tests/` con estensioni `py sh yaml yml`.
- Per disabilitare il trigger in casi particolari, aggiungi l’etichetta `skip-codex-review` alla PR.

Dettagli
- L’Action non commenta se l’ultimo commit modifica solo `docs/` o `.github/`.
- La ricerca del commento è idempotente: se qualunque utente ha già commentato con `@codex review`, non verrà aggiunto un duplicato.
- I log della Action elencano i file visti e la decisione (posted/skip).

Nota
- I commenti operativi dell’assistente seguono anche `@mycodex instructions …` (se presente), da usare con cautela.
