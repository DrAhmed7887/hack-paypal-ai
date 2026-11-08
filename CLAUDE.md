# CLAUDE.md: BillCheck

PayPal AI Hackathon entry (Devpost, deadline Thu 12 Nov 2026, 12:00 PT). AI reads a synthetic medical bill, checks each line against public CMS price benchmarks, explains the gaps in plain language, and PayPal (sandbox) moves the money: Orders v2 for the patient's fair payment, Invoicing v2 for the corrected itemized invoice. Synthetic data only. The rules owner is the physician who signs the benchmark criteria.

## Team (who does what)
| Role | Who | Owns |
|---|---|---|
| Product owner | Ahmed | Signs the benchmark rules, approves the flow (G2), watches the video (G4), submits (G5) |
| Product manager + conductor | Claude Code (Opus, the `/loop` session) | `docs/LOOP.md` scope and order, the user flow, README as the one source of claims, cutting scope to hit the deadline. Builds the code |
| Product critique (G2 only) | Gemini 4 Argon via `agy` | One outside read of the flow against the 5 judging criteria |
| Code reviewers | GitHub Copilot (Lite) on every PR; `code-reviewer` / `python-reviewer` agents (Sonnet) on every code PR; `security-reviewer` on PayPal and key-handling PRs; Gemini via `agy` once on items 5, 7, 8 | Bugs in the diff. Every finding is checked against the code before acting |
| Quality manager | GPT-6 Sol via `codex-rwth` (a different model family from the builder) | Independent PASS/BLOCK at each quality point: research numbers vs their sources (item 2), expected results of the test set (4), the G1 accuracy table (6), the stress round (10), the claims audit (11). Writes its verdicts to `docs/QA.md`. A BLOCK stops the loop until fixed or Ahmed overrides |

## The build runs as a self-paced `/loop`
Task queue: `docs/LOOP.md` (🔒 = gate). Each iteration does one item:
1. Branch `build/<short-name>` from `origin/main`.
2. Code + tests. Write the expected result of each test case before running it. Never push a red build.
3. `scripts/ship.sh "title"`: local checks → push → PR → Copilot (Lite) review requested.
4. Bind the PR in the desktop app (ccd_pr `bind_pr`); CI and review events wake the loop. Don't poll CI.
5. Read reviews (Copilot, plus the `code-reviewer` / `python-reviewer` agents for code changes). Check every finding against the code; fix the real ones on the same branch.
6. `scripts/merge.sh <pr>` when CI is green. Tick the box in `docs/LOOP.md` in the same PR or the next one.
7. Report in 3 lines: what merged, measured numbers, what's next.

## Hard gates (stop the loop and ask Ahmed)
- Any benchmark rate, threshold, settlement rule or test-data expectation (`data/`, `src/billcheck/benchmarks.json`, EVIDENCE). `ship.sh` exits 4 on these.
- Making the repo public, recording or publishing the video, posting, submitting.
- Spending money or credits beyond this project's daily model cap.
- Signing in, creating accounts, entering any credential (PayPal developer site, Fireworks).
- Force-pushing `main`, rewriting published history, deleting repos or data.

## Never in this repo
Real patient data, secrets (keys live in Keychain / an untracked `.env`), personal notes, private links (Notion, Drive), real hospital names or logos. Every public number traces to a script output or a sourced EVIDENCE row.
