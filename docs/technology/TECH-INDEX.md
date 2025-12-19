---
id: TECH-MAIN
domain: technology
status: approved
version: 1.0
---
# TECH STACK & CODING STANDARDS

## Core Stack
- **Backend:** Python 3.12, FastAPI.
- **Database:** SQLite (WAL mode abilitato per performance).
- **ORM:** SQLAlchemy (Async).
- **Automation:** Playwright (Headless mode).
- **Frontend:** Jinja2, HTMX, Tailwind CSS.

## Coding Rules (AI Constraints)
1. **Type Hinting:** Obbligatorio su ogni funzione (`def name(p: int) -> str`).
2. **Error Handling:** Eccezioni custom definite in `app/exceptions.py`. Non usare catch-all `except Exception`.
3. **Paths:** Usare sempre `pathlib.Path`.
4. **Environment:** Configurazione tramite file `.env` e Pydantic `BaseSettings`.
5. **Naming:** Progetto: `bike-copilot`. Moduli in snake_case, Classi in PascalCase.
