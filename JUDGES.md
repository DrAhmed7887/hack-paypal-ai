# For judges: each criterion and where its evidence is

**What it does in one line:** BillCheck reads a US medical bill and compares each eligible line with its 2026 Medicare price. The patient can then pay a suggested amount through PayPal, and BillCheck issues an itemized, paid invoice at those amounts.

**Headline example (synthetic bill C08):** **$4,445.00 billed → $1,882.38 suggested**. PayPal sandbox reports the capture COMPLETED for $1,882.38 and the BillCheck-generated invoice MARKED_AS_PAID for $1,882.38 (`docs/LIVE_CHECK.md`).

**Demo film (under 3 minutes):** https://youtu.be/LjjzFM5r5VU · **Run it:** README "Run it" (Python 3.11+, a PayPal sandbox REST app and a Fireworks key). Synthetic bills and sandbox money only.

Every number here comes from a script or a file in this repo. The README is the single source for claims; this page only points to them.

| Criterion (Devpost, equally weighted) | Evidence | Where |
|---|---|---|
| **Technological implementation** | Three PayPal APIs work together: JS SDK buttons; Orders v2 for an amount the server holds (the browser never sends it), checked against the audit at capture; Invoicing v2 for an invoice recorded as paid with the same payment. Idempotency keys on capture, invoice and payment record. The AI output is held to a fixed schema, and every code, amount and date must appear on the bill. 155 tests pass, and CI runs them on every pull request. | README "How PayPal is used", "What it does"; `src/billcheck/paypal_client.py`, `extractor.py`, `auditor.py`; `.github/workflows/ci.yml`; `tests/` |
| **Design** | One flow: bill in → line-by-line comparison → plain-language summary → pay. A line with no confirmed benchmark says so instead of being flagged. Audit history in AG Grid: sort, filter, search, CSV export, and a totals row that follows the filter. | README "What it does" (steps 1–6); `src/billcheck/web/`; `docs/workflow.svg` |
| **Potential impact** | Hospital list prices can sit far above what hospitals are paid: an average charge-to-cost ratio of 3.4 in a national study (Bai & Anderson, *Health Affairs* 2015, PMID 26056196). Uninsured patients are commonly asked to pay full charges. BillCheck gives a patient a public reference per line and a paper trail for what they paid. | README "Why"; `data/DATA_CARD.md` |
| **Innovation / idea** | Payment is tied to the audit: PayPal moves the suggested amount, and the provider-side invoice is generated at those amounts and marked paid with the same capture. The rules (Medicare schedule per line type; RAND Round 5.1 reference multipliers 1.84× professional, 2.79× outpatient hospital) were signed by a physician. | `docs/DECISIONS.md`; `src/billcheck/benchmarks.json`; README "What it does" step 3 |
| **Presentation** | Demo film; workflow diagram; measured results with limits stated; an independent model-family quality check of rules and results. | https://youtu.be/LjjzFM5r5VU; `docs/workflow.png`; README "Measured results"; `docs/QA.md` |

## Safety and robustness

- **Stress:** 22/22 checks (`docs/STRESS.md`). These include 6 AI audits at once, 200 requests at 50-way concurrency, a 9-way double click giving one order, and a prompt-injection test that returned the expected $1,882.38 total. They also check that rate limits can't be bypassed with a forged `X-Forwarded-For`.
- **The AI summary** is shown only if every dollar figure in it appears in the audit and it contains no link, contact detail or markup. Otherwise a fixed template is shown.
- **Spend cap:** model spend is capped at $2 per day in code (`BILLCHECK_DAILY_CAP_USD`).

## Limits (from the README)

- The AI reader matched all 28 synthetic bills in two layouts after tuning on that same set. This does not estimate accuracy on real bills (`docs/G1.md`).
- Prices are national and not adjusted for locality. Not medical, legal or financial advice.
- Synthetic bills and PayPal sandbox money only. No real patients, providers or bills.

## Quick check without keys

```bash
pip install -e '.[dev]' && python -m pytest -q
```
