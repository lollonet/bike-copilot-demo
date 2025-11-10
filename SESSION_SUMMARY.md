---
template: session_summary
project: <PROJECT_NAME>
session_date: <YYYY-MM-DD>
author: <YOUR_NAME or ROLE>
status: active
purpose: Resume and brief Copilot for next session
---

# SESSION SUMMARY — <PROJECT_NAME>

## 1. Context Recap
Briefly restate what this project is about and what phase we’re in.  
_Example:_ “We are building a local AI assistant for sourcing bike parts. MVP in progress, focusing on ingest and UI.”

## 2. Last Session Summary
- Main goals achieved ✅  
- Key decisions made 🧭  
- Pending tasks or open issues ⚙️  
- Any blockers or uncertainties 🧩  

## 3. Current Focus
State what the Copilot should prioritize *this session*.  
_Example:_ “Finalize ranking logic, test PDF generation, prepare packaging for Linux Mint demo.”

## 4. Next Steps / Action Queue
| ID | Task | Owner | Due | Status |
|----|------|--------|------|--------|
| T1 | ...  | Copilot | ... | todo  |
| T2 | ...  | You | ... | pending |

## 5. Reference Files
List which documents or artifacts define the current truth.  
_Example:_  
- `VISION.md` (v1.0 frozen)  
- `ARCH.md` (v1.0 frozen)  
- `TECH.md` (v1.0 review)  
- Latest `DIFF-YYYY-MM-DD.md`  

## 6. Briefing for Copilot
When this file is loaded at session start, Copilot must:
1. Read sections 1–5.
2. Summarize current context in ≤100 words.
3. Propose next logical step(s) or confirm alignment.
4. Maintain coherence with the referenced files.
5. Log new changes for next `DIFF-<date>.md`.

## 7. Session Closeout (auto-filled later)
- Summary of progress  
- Updated decisions  
- Timestamp of closure  
