# Signed rules

The rules owner (the physician) signs every benchmark, threshold and settlement rule. E-row IDs refer to the evidence pack (public sources only, kept with the project's research notes). Code must not use a rule that is not listed here as signed.

## R1–R5, signed 8 Nov 2026 (v1)

| ID | Rule | Evidence |
|---|---|---|
| R1 | **Benchmark, professional lines** (physician / radiologist claims): 2026 Medicare Physician Fee Schedule, national, locality-unadjusted, conversion factor $33.4009. Imaging is matched by component: global, `-26` (professional) or `-TC` (technical). | E1, E4–E13 |
| R2 | **Professional flag and suggestion:** flag a line when the charge is above **1.84×** its R1 amount; suggest paying **1.84×**, capped at the billed amount. Label: "what private health plans paid on average for professional services in 2022 (RAND)". | E23 |
| R3 | **Benchmark and rule, hospital facility lines that Medicare pays separately** (ED visit levels 99283–99285, CT 70450, X-ray 71045): 2026 OPPS national payment rate. Flag above **2.79×**, suggest **2.79×**, capped at the billed amount. Label: "what private health plans paid on average for outpatient hospital services in 2022 (RAND)". | E16, E23, E43–E47 |
| R4 | **Packaged facility lines** (OPPS status Q1 or Q4, e.g. 96372 injection, 80053 CMP, 85025 CBC, on a hospital bill with an ED visit): no flag and no separate benchmark. Wording: "Medicare includes this in the visit payment." | E48, E49 |
| R5 | **Lab-only bills** (independent lab, CLFS): show the 2026 CLFS rate for information only. No flag, no suggestion. | E41, E42 |

## v1.1 refinements after QA, signed 8 Nov 2026 (they only narrow when R2–R4 apply; no new numbers; R2a replaces the R2 label)

| ID | Refinement | Evidence |
|---|---|---|
| R2a | R2 label scope: "what private health plans paid on average in 2022 for professional services linked to hospital care (RAND), compared with 2026 Medicare rates". | E23 |
| R3a | R3 applies to an ED visit line (J2) only when the bill has no observation-hours line; to 70450 only when it is the only CT/CTA line on that date. 71045 facility lines: "benchmark not available" until its imaging family is confirmed. | E51–E54 |
| R4a | Routine labs 80053 and 85025 (not molecular pathology, ADLT or preventive tests) on a hospital bill with other services: "Medicare pays lab tests separately only when they are the only services on the claim, so on this bill they would usually be included in other payments." 96372 facility line: "benchmark not available" until Addendum D1 is read. | E50, E54 |
| R6 | Rates are the 2026 releases named in E2, E41–E49 (PFS file 2026-09-01, CLFS Q4, OPPS October). Apply each only to dates of service it covers: OPPS October release → 1 Oct–31 Dec 2026; PFS and CLFS 2026 files → 2026 dates (CLFS rows say effective 20260101). Other dates: "benchmark not available". Demo bills use Oct–Nov 2026 dates. | E2, E14, E20 |

## v1.2, signed 8 Nov 2026 (narrows R3a further)

| ID | Refinement | Evidence |
|---|---|---|
| R3b | Closed-world test for an ED facility visit line: compare it only when every other facility line on the bill is a code in the app's benchmark table and none is G0378 (observation hours). Any unknown facility code could be a J1 or T service, or observation, that changes how Medicare pays the visit, so the visit shows "benchmark not available". | E53, E55 |

## v1.3, signed 8 Nov 2026

| ID | Clarification | Evidence |
|---|---|---|
| R3c | "Only CT/CTA line on that date" (R3a) means one CT procedure: one line with one unit. Two units of 70450 are two scans, which Medicare pays as one combined payment, so the line shows "benchmark not available". | E51 |

## Wording rules (all lines)
- The comparison is a **negotiation reference**, never proof of an error, overcharge or fraud. Don't call a price "fair", "standard" or "verified reasonable".
- An unflagged line is "not flagged by this comparison". A line with no matching benchmark shows "benchmark not available" with no ratio.
- The bill-level difference is a "potential negotiation difference", computed only from line items. A mismatch between the line sum and the stated bill total is shown, not hidden.
- No billing-error prevalence statistic in public material (E35–E40: no peer-reviewed source).
