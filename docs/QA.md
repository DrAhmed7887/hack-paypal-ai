# Quality manager verdicts

Quality manager: GPT-6 Sol via RWTHgpt (`rwth-ask -m gpt-6-sol`), a different model family from the builder. E-row IDs refer to the evidence pack (kept with the project's research notes, outside this repo; public sources only).

## Item 2: evidence pack vs app rules (8 Nov 2026)

Conductor cross-check before QA: re-streamed the CMS 2026 PFS file `indicators2026-09-01.csv` (pfs.data.cms.gov); RVU cells for all 8 codes match E4–E15, and total RVU × $33.4009 reproduces every PFS dollar amount.

VERDICT: BLOCK

FINDINGS:
1. **BLOCK — `DEFAULT_CMS_BENCHMARKS`, E4–E13:** All six hard-coded PFS rates are contradicted by the pack. Replace 99283/99284/99285 with **$69.47/$118.24/$171.35**; 70450/71045 global with **$106.55/$25.38**; and 96372 with **$15.36**, subject to claim-component matching. Conductor verified the pack’s RVU arithmetic. The 99283 and 99284 descriptions also misstate the documented MDM levels; use low and moderate (E4–E5).
2. **BLOCK — `80053`, `85025`, E14–E15:** $14.50 and $10.75 have no supporting CLFS values. These codes have zero PFS RVUs, not PFS prices. Remove both rates until the applicable CLFS file is read.
3. **BLOCK — `audit()`, E4–E21:** A matching CPT alone does not establish a comparable payment. ED physician PFS rates are not hospital ED facility rates; imaging must match professional, technical, or global components. OPPS payments and lab limits remain unknown. Require schedule, billing entity, service setting, and component before comparing; otherwise show “benchmark unavailable.”
4. **BLOCK — `markup_threshold`, `rec`, `expl`, E22–E23, E31–E34:** Neither the flat **>3×** flag nor **2× “fair settlement”** is established by these sources. RAND reports 2022 *average commercial payments*, not fair prices or thresholds. The chargemaster studies compare charges with **cost**, not Medicare payment. Remove “fair,” “standard,” and any claim that a flagged charge is an error.
5. **FIX — `VERIFIED_REASONABLE`, `NO_BENCHMARK_FOUND`:** A charge at or below a threshold is not verified reasonable. A missing benchmark is not a measured 1.0× ratio. Use “not flagged by this comparison”; show ratio and benchmark as unavailable when unmatched.
6. **FIX — report totals:** No sample bill permits a numeric total check. `total_disputed_amount` uses `bill.total_billed`, while recommendations sum line items; a mismatch makes the displayed difference misleading. Validate equality or label the discrepancy, and call the difference a **potential negotiation difference**, not a proven disputed amount.

RULES TO SIGN:
- **Benchmark:** Use the dated, national, locality-unadjusted PFS non-qualifying-APM amounts in E4–E13 **only for matched professional claims and imaging components**. Use CLFS for labs only after obtaining E14–E15 values; OPPS for facility claims only after obtaining E20–E21 payment rows. Until then, no comparison or proposal.
- **Flag threshold:** For a valid match, flag **charge >1.0× the applicable Medicare reference** (E4–E13) solely as “above Medicare negotiation reference.” This is a descriptive comparison, **not** an evidence-based excessive-price cutoff.
- **Settlement multiplier:** Offer **1.0× that matched reference** (E4–E13), capped at the billed amount, only as an optional **negotiation starting point**. No source establishes a fair settlement multiplier. Never label an unflagged line “reasonable” or a flagged line an “error.”

Conductor note on finding 6: the test bill in `tests/test_auditor.py` does reconcile ($850 + $1,650 + $350 = $2,850 billed), so that part of the finding is wrong; the rule to show any line-sum mismatch stays (DECISIONS wording rules).

**Status:** BLOCK on the current `auditor.py` rules. Not fixed yet: the replacement rules are the owner's to sign (LOOP item 3), then item 4 moves the rates to `src/billcheck/benchmarks.json` with E-row IDs.

## Item 3: signed rules (8 Nov 2026)

Rounds with the quality manager on `docs/DECISIONS.md`:
1. **BLOCK** on v1: CT/X-ray are OPPS status Q3 (only conditionally separate); packaging wording unsourced; R2 label too broad; October OPPS rates applied to all of 2026.
2. Conductor read the CY 2026 OPPS/ASC final rule (E50–E53) and narrowed the rules (v1.1, owner-signed). **BLOCK**: lab wording ignored the molecular/ADLT/preventive exceptions; R6 dates. Both fixed.
3. **BLOCK**: "no observation line" is not a complete J2 test. Conductor added the C-APC 8011 criteria (E55) and the closed-world rule R3b; checked that none of the 8 known codes is J1, T or G0378 (E43–E49).
4. R3b signed by the owner. **VERDICT: PASS** — "Code may implement exactly the signed R1–R6, R2a–R4a, R3b, and wording rules."

**Status:** item 2 BLOCK on the old `auditor.py` rules is resolved by item 4, which replaces the hard-coded rates with `src/billcheck/benchmarks.json` built from these signed rules.

## Item 4: test-set expectations (8 Nov 2026)

Independent recomputation of all 14 cases (C01–C14) and the price table:

VERDICT: BLOCK

- **C10/L2:** It is the only CT/CTA line on the date. Two units do not make it two lines, so the expected flag and benchmark are wrong. Correct: **ABOVE_REFERENCE**, benchmark **$213.62** (2 × $106.81), suggested **$596.00**.
- **C10 totals:** Correct line sum **$4,200.00**, total suggested **$1,674.10**, potential negotiation difference **$2,525.90**; totals_match remains **true**.
- **C14/L1:** R5’s CLFS information-only rule is limited to independent-lab bills; no signed rule supplies that benchmark for this hospital-only lab bill. Correct: **NOT_AVAILABLE**, benchmark **null**, suggested **$60.00**.

The price table copies every specified E-row value exactly.

**Conductor response:** C14 accepted (R5 covers independent-lab bills only); the code and the expected result now say NOT_AVAILABLE. C10/L2 disputed: E51 makes two CT procedures on one date a single combined payment, and 2 units are two procedures; the wording of R3a is clarified as R3c, pending the owner's signature. The price table was confirmed to match every E-row.

**Item 4 re-check after R3c was signed:**

VERDICT: PASS
R3c makes L2 unavailable; R3a makes L3 unavailable. L1 remains comparable under R3b, and the suggested amounts and totals are correct.

**Status:** item 4 PASS (C14 fixed in code and data; C10 confirmed under signed R3c; price table matches every E-row).

## Item 6: G1 accuracy table (8 Nov 2026)

VERDICT: BLOCK

1. **NOTE — Scoring:** The script compares claim type, service date, total, and each line’s code, modifier, units, and amount in order. PASS means those fields match; BORDERLINE means only a scored header field differs; FAIL covers a scored line difference or extraction refusal. These are not checks of every bill field.

2. **BLOCK — Run history:** Run 1 reports nine failures but attributes them to seven table refusals plus three letter quantity errors—ten distinct bills. It also describes “x2,” while the supplied letter renderer writes “Qty 2.” Reconcile the history before publication.

3. **BLOCK — Reproducibility:** `g1_eval.py` overwrites `docs/G1.md` without the displayed run-history and limits sections. The supplied script therefore cannot reproduce the document as shown; preserve those sections in generation or identify them as manually added.

4. **FIX — Wording:** The script records explanation source and fallback reason; it does not establish that a template was *shown to a patient*. Keep the real-bill limitation prominent.

**Safe README sentence:** “After tuning on the same synthetic test set, the final run matched the scored extraction fields on all 28 bills rendered in our two layouts; this does not estimate accuracy on real bills.”

**Conductor response:** run-1 counts corrected (6 table refusals + 3 letter unit errors = 9); run history and limits moved into docs/G1_notes.md, which scripts/g1_eval.py includes; wording changed to 'the explainer returns the template'.

VERDICT: PASS

Run 1 now reconciles: six table refusals plus three letter quantity errors match the nine FAIL rows. The notes identify “x2” as the old rendering and “Qty 2” as the fix. The script now includes the notes, and the wording no longer claims a template was shown to a patient.

## Item 11: claims audit of README and workflow diagrams (8 Nov 2026)

Round 1:

**VERDICT: BLOCK**

The C08 figures, 1.84×/2.79× multipliers, G1 result, 22/22 stress result, 147 passing tests, and live PayPal statuses are traceable. The following wording must change before publication.

1. **BLOCK** — “checks every line against public 2026 Medicare prices” (README). Packaged and unavailable lines have no separate price comparison. **Replace:** “compares eligible lines with applicable 2026 Medicare rates and explains when a benchmark is unavailable.”

2. **BLOCK** — “negotiated, paid invoice” (diagram); “provider’s corrected itemized invoice” (README). The evidence shows BillCheck issued an invoice, not that the provider negotiated, approved or issued it. **Replace:** “BillCheck-generated itemized invoice reflecting the suggested amounts and recorded sandbox payment.”

3. **BLOCK** — “cannot be paid twice” and “a retry or a double click cannot charge or invoice twice” (README); “one invoice per payment” (diagram). One live transaction and the stress checks do not establish these universal guarantees. **Replace:** “State checks and idempotency keys are designed to prevent duplicate actions; the tested nine-click race produced one order.”

4. **FIX** — “the labs are bundled” (README); “bundled or unclear lines are never flagged” (diagram). Signed R4a uses qualified lab-packaging wording, and “never” overstates the rule. **Replace:** “The routine labs would usually be included in other payments on this bill; the injection has no confirmed separate benchmark. Neither is flagged in C08.”

5. **FIX** — “prompt injection in the bill ignored” (README). The stress result establishes a successful response and unchanged C08 total, not that every injected instruction was ignored. **Replace:** “The prompt-injection test returned 200 and the expected $1,882.38 total.”

6. **FIX** — “13 hostile inputs” (README). The 13 checks include ordinary unknown routes, wrong methods and disabled docs. **Replace:** “13 invalid-input and route checks returned the expected 4xx responses.”

7. **FIX** — “147 tests run in CI”; “expected results written before the code” (README). Supplied evidence establishes `147 passed`, not CI execution or when expectations were written. **Replace:** “147 tests passed; G1 used 14 signed synthetic cases.”

8. **FIX** — “uninsured and out-of-network patients are the ones asked to pay full charges” (README). E33 says uninsured patients are *commonly* asked for full charges; out-of-network patients are *often* expected to pay a large portion. **Replace with that qualified distinction.**

9. **FIX** — “which lines are far above what insurers usually pay” (README). RAND supplies aggregate 2022 ratios, not usual payments for each line. **Replace:** “which eligible lines exceed a negotiation reference based on RAND’s aggregate payment ratios.”

10. **FIX** — The literal banned words in the README’s parenthetical list and the diagram’s “finding of error” breach the signed public-wording rule, even though used negatively. **Replace both with:** “not proof that a charge is incorrect.”

11. **NOTE** — “five synthetic sample bills,” the `$2` cap “in code,” Keychain behavior, and claims about who reviewed *each* pull request lack verification in the supplied evidence. **Replace with narrower, repository-confirmed wording or attach supporting evidence.**

Round 2:

VERDICT: BLOCK
BLOCK 1 remains: the audit description and diagram still say each line has a 2026 Medicare price; some lines have no separate benchmark.
BLOCK 2 remains: “corrected invoice” can imply provider correction or approval. Say “BillCheck-generated invoice reflecting suggested amounts.”
BLOCK 3 is substantially resolved; describe the diagram’s steps as *using idempotency keys*, rather than simply “idempotent.”
FIX 9/10 remain: the diagram treats RAND’s aggregate ratios as line-level averages, and the README repeats excluded wording in its parenthetical.
The other FIX items are handled or supported by the conductor notes.

Round 3:

VERDICT: BLOCK
The earlier BLOCKs and FIX 10 are resolved.
FIX 9 remains: both diagrams present RAND ratios as line-level comparators. Label them aggregate category ratios applied to Medicare benchmarks.
The 4×5 diagram should also say unconfirmed-benchmark lines are not flagged.

Round 4:

VERDICT: BLOCK
The 4×5 diagram still needs “RAND aggregate category ratios” and should specify that lines with unconfirmed Medicare benchmarks are not flagged.

**Conductor response:** all wording findings applied to README.md, docs/workflow.svg and docs/workflow_4x5.svg; kept, with evidence: CI runs the tests on every PR (.github/workflows/ci.yml), 5 sample bills (web/app.py DEMO_CASES), the $2/day cap (llm.py).

Round 5 (after the 4:5 fixes):

VERDICT: PASS
Both requested fixes are now in the 4×5 diagram.

**Status:** item 11 claims audit PASS (round 5).
