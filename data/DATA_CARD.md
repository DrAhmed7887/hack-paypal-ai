# Data card: BillCheck test set

**Synthetic only.** No real patients, no real bills, no real providers. Provider names are invented and marked "(Synthetic)". No names, dates of birth or identifiers of any person.

## Files
- `data/cases.json`: 14 fixed bills (C01–C14), each with its purpose and the expected result for every line and for the totals. The expected results were written by hand from the signed rules in `docs/DECISIONS.md` (v1.3, incl. R3c) **before** the auditor code existed, and are checked by `tests/test_auditor.py`.
- `src/billcheck/benchmarks.json`: the public 2026 Medicare prices the rules use. Each price cites an evidence row (E-id) holding the exact CMS cell it came from.

## Fields
| Field | Meaning |
|---|---|
| `claim_type` | `professional` (physician or radiologist claim, priced on the Physician Fee Schedule), `facility` (hospital outpatient claim, OPPS) or `lab` (independent lab, CLFS) |
| `date_of_service` | Decides which price release applies (R6). Demo bills use Oct–Nov 2026 |
| `cpt_code`, `modifier`, `units` | Procedure code; imaging component `26` or `TC`; units multiply the Medicare price |
| `billed_amount`, `total_billed` | Synthetic charges. `total_billed` may differ from the line sum on purpose (C07) |
| expected `flag` | `ABOVE_REFERENCE`, `NOT_FLAGGED`, `PACKAGED`, `INFO_ONLY` or `NOT_AVAILABLE` |
| expected `benchmark` | Medicare price × units, or `null` when not available or packaged |
| expected `suggested` | The suggested negotiation amount: the RAND multiplier × Medicare price when flagged, else the billed amount |

## Where the numbers come from
- Charges: chosen by hand to test each rule. They are not drawn from any real price distribution, and no statistic about real bills is derived from them.
- Medicare prices: CMS 2026 files (E4–E13 Physician Fee Schedule, E41–E42 lab fee schedule, E43–E49 OPPS Addendum B).
- Multipliers: RAND Round 5.1 (E23): 1.84× for professional lines, 2.79× for hospital outpatient lines.

## Coverage
Each signed rule has at least one case: R1/R2 (C01–C07), the threshold edge (C03), imaging components (C04, C05), units (C06), a missing code and a total mismatch (C07), R3/R3b/R4a (C08), the closed-world test with observation hours (C09), R3a multiple CT and facility X-ray (C10), R5 lab-only (C11), a hospital lab-only bill with no signed rule (C14), R6 dates (C12, C13).

Not covered yet: duplicate lines (no signed rule exists for them; they are audited as separate lines).
