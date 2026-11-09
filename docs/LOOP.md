# BillCheck build queue (driven by `/loop`)

Deadline: Thu 12 Nov 2026, 12:00 PT. One item per loop iteration: the first unchecked **Build** item. 🔒 = stop the loop and wait for Ahmed. The three items under "Before the money and model steps" block only the steps that need them: model key → 5; PayPal sandbox → 7; repo history → 15.

## Before the money and model steps
- [x] 🔒 Repo history: the development repo was renamed (kept private); the published repo starts from one clean commit of main (9 Nov). Nothing deleted.
- [x] 🔒 PayPal sandbox app: existing Default Application; keys in Keychain (8 Nov); existing sandbox business + personal accounts (EG) accept USD orders and invoices (tested 8 Nov).
- [x] 🔒 Model key (Fireworks): existing key in the Keychain, $2/day cap in code (owner OK, 8 Nov).

## Build
- [x] 1. Loop files: CLAUDE.md, scripts/ship.sh + merge.sh, CI, LICENSE, packaging fix.
- [x] 2. Research pack (kept outside the repo): 2026 CMS PFS national rates for the 8 CPTs (facility vs non-facility), a source for the 3× flag and 2× fair multiplier, a source for README's "up to 80%" claim or delete it. Tools: PubMed connector, WebFetch on the CMS PFS lookup. Every number with its quote and date checked.
- [x] 3. 🔒 Ahmed signs the benchmark rules and thresholds (`docs/DECISIONS.md` v1.2, 8 Nov; v1.3 adds R3c).
- [x] 4. Data pack (signed at 2f69ed0, 8 Nov): `data/` seeded synthetic bills (10–20, incl. missing CPT, unit errors, duplicate lines), expected results written first, `DATA_CARD.md`. Rates move to `src/billcheck/benchmarks.json` with source IDs.
- [x] 5. AI extraction: bill text/PDF → `MedicalBill` (Fireworks, schema-validated); plain-language explanation built from audit numbers only, with a check that every $ figure in it matches the report.
- [x] 6. G1 table (docs/G1.md: final run 28/28 scored fields, AI summary accepted 27/28; QA PASS): extraction accuracy on the fixed set (pass / fail / borderline), scripted, re-run after any prompt change.
- [x] 7. (live end to end, docs/LIVE_CHECK.md: capture COMPLETED $1,882.38; corrected invoice MARKED_AS_PAID) PayPal real calls: Orders v2 create + capture (sandbox buyer approves via JS SDK); Invoicing v2 create + send the corrected itemized invoice from the provider sandbox merchant. Tests on recorded responses.
- [x] 8. UI (built; G2 screenshots pending Ahmed): FastAPI + one phone-first page: upload → line-by-line findings with reasons → "Pay fair amount" → corrected invoice link. Screenshots at phone and laptop width. Server-side rules from the item-7 security review: the browser never sends amounts; the server holds each audit and its order (order_id → bill, amount, invoice, state created → captured → recorded) and captures only orders it created; the paid amount and capture id come from the capture result; one corrected invoice per bill, sent only to the payer email PayPal returns on capture; rate limit per IP; double click safe.
- [x] 9. 🔒 G2: Ahmed approved the screens (seen live in Chrome, 8 Nov).
- [x] 10. (docs/STRESS.md: 22/22 after fixing forged X-Forwarded-For; live capture blocked by the EG sandbox merchant) Stress round (hackathon stress checklist) + independent review (code-reviewer, python-reviewer, Copilot Lite, Gemini via `agy` once).
- [x] 11. (claims audit QA PASS in round 5) Workflow diagram `docs/workflow.svg` / `.png` / `_4x5.png` from the code; README claims audit against EVIDENCE + G1 numbers.
- [x] 12. Judges can test until 15 Dec: run-locally instructions in the README (hosted Space built, not deployed); model daily cap on ($2/day).
- [x] 13. (HyperFrames film "One bill, one number", 94 s, ElevenLabs voice, catalog music; video/film) Video: video-director plan → Playwright capture → render, ~2:00, no trademarks.
- [x] 14. 🔒 G4: Ahmed watched the preview with sound and asked for the render (9 Nov).
- [x] 15. Pre-publish scan: secret patterns and private notes, full history of the development repo and the published snapshot: clean (9 Nov).
- [x] 16. 🔒 G5: repo public, YouTube upload (https://youtu.be/LjjzFM5r5VU), Devpost submitted (https://devpost.com/software/billcheck-7vlo29), 9 Nov.
