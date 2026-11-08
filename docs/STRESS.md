# Stress round

Run 2026-11-08 14:39 UTC against a local server by `scripts/stress.py`: **22/22 checks passed.** Paid part: 8 AI calls; PayPal calls are sandbox only.

| Phase | Check | Result | Detail |
|---|---|---|---|
| B | 6 AI audits at once | PASS | 6/6 ok, p95 4.9s, max 4.9s |
| B | audit totals match the signed cases | PASS | 6/6 |
| A | 200 free requests, 50 at once | PASS | 200/200 ok, p95 0.046s |
| P | 6 sandbox orders at once | PASS | 6/6 ok, max 1.7s |
| P | 9 simultaneous clicks on one bill give one order | PASS | 1 distinct order id(s), 0 refused |
| P | capture before buyer approval is refused cleanly | PASS | 502 |
| C | oversized body | PASS | got 413, want [413] |
| C | fake PDF | PASS | got 400, want [400] |
| C | binary .txt | PASS | got 400, want [400] |
| C | text over 20,000 chars | PASS | got 422, want [422] |
| C | empty form | PASS | got 422, want [422] |
| C | broken JSON body | PASS | got 422, want [422] |
| C | forged audit id (order) | PASS | got 404, want [404] |
| C | forged audit id (capture) | PASS | got 404, want [404] |
| C | path traversal in static | PASS | got 404, want [404] |
| C | unknown sample | PASS | got 404, want [404] |
| C | unknown route | PASS | got 404, want [404] |
| C | wrong method | PASS | got 405, want [405] |
| C | docs disabled | PASS | got 404, want [404] |
| C | prompt injection in the bill text | PASS | 200, total 1882.38 |
| L | burst of 25 from one IP hits 429 | PASS | first 429 at request 8 |
| L | forged X-Forwarded-For does not reset the limit | PASS | [429, 429, 429, 429, 429] |

## Afterwards (checked by hand after the run)
- Server log since start: 0 tracebacks; 1 error line, the expected `ORDER_NOT_APPROVED` from the capture-before-approval check.
- Server memory after the run: 40 MB. Model spend today (all runs, incl. G1 and stress): $0.0818 of the $2.00 daily cap.

## Fixed during this round
- **Forged `X-Forwarded-For` reset the rate limit** (run 1): uvicorn trusts that header from localhost by default. `scripts/serve.sh` now starts uvicorn with `--no-proxy-headers`; behind a tunnel, set `BILLCHECK_CLIENT_IP_HEADER` to the header the tunnel sets.
- Run 1's double-click and capture checks failed because of the test itself (it reused a bill already at its payment-attempt cap); the race now runs on a fresh bill and counts only real order ids.
- Run 2: 1 of 200 load requests failed once and did not reproduce in 600 further requests; the script now records the reason for any failure.

## Not covered here
- The live capture: PayPal refuses it with `COMPLIANCE_VIOLATION` because the sandbox merchant account is registered in Egypt. Needs a US sandbox business account (owner action).
