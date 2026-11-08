"""G1: measure the AI bill reader on the fixed test set (14 signed cases x 2 layouts), live on Fireworks.

Scores only the fields the audit uses (claim type, date, total, and per line: code, modifier, units, amount),
plus whether the AI explanation passed the grounding checks. Writes docs/G1.md and docs/g1_results.json.
Usage: FIREWORKS_API_KEY=... .venv/bin/python scripts/g1_eval.py
"""

import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from billcheck.auditor import BillAuditor
from billcheck.explainer import explain
from billcheck.extractor import ExtractionError, extract_bill
from billcheck.llm import DEFAULT_MODEL, FireworksLLM, LLMError, SpendCapReached, SpendGuard
from billcheck.models import MedicalBill
from billcheck.render import LAYOUTS

ROOT = Path(__file__).resolve().parents[1]


def audit_fields(b: MedicalBill) -> tuple:
    return (b.claim_type, b.date_of_service, round(b.total_billed, 2),
            tuple((i.cpt_code, (i.modifier or "").upper() or None, i.units, round(i.billed_amount, 2))
                  for i in b.line_items))


def score(expected: MedicalBill, got: MedicalBill) -> str:
    """PASS: every audit field equal. BORDERLINE: same lines and amounts, only header fields differ. FAIL: else."""
    e, g = audit_fields(expected), audit_fields(got)
    if e == g:
        return "PASS"
    if e[3] == g[3]:
        return "BORDERLINE"
    return "FAIL"


def main() -> int:
    cases = json.loads((ROOT / "data" / "cases.json").read_text())["cases"]
    llm, auditor = FireworksLLM(), BillAuditor()
    spent_before, rows = SpendGuard().spent_today(), []
    for case in cases:
        expected = MedicalBill(**case["bill"])
        for layout, render in LAYOUTS.items():
            t0 = time.time()
            row = {"case": case["id"], "layout": layout}
            try:
                got = extract_bill(render(expected), llm)
                row["result"] = score(expected, got)
                row["diff"] = "" if row["result"] == "PASS" else f"expected {audit_fields(expected)} got {audit_fields(got)}"
                ex = explain(auditor.audit(got), llm)
                row["explanation"] = ex.source
                row["explanation_reason"] = ex.reason
            except ExtractionError as exc:
                row.update(result="FAIL", diff=f"refused: {exc}", explanation="-", explanation_reason="")
            except (LLMError, SpendCapReached) as exc:
                row.update(result="ERROR", diff=type(exc).__name__, explanation="-", explanation_reason="")
            row["seconds"] = round(time.time() - t0, 1)
            rows.append(row)
            print(f"{row['case']} {layout:<6} {row['result']:<10} expl={row['explanation']:<8} {row['seconds']}s",
                  flush=True)
    spent = SpendGuard().spent_today() - spent_before
    write_report(rows, spent)
    return 0 if all(r["result"] == "PASS" for r in rows) else 1


def write_report(rows: list, spent: float, when: str = "") -> None:
    counts = Counter(r["result"] for r in rows)
    expl = Counter(r["explanation"] for r in rows if r["explanation"] != "-")
    when = when or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (ROOT / "docs" / "g1_results.json").write_text(json.dumps(
        {"run_at": when, "model": DEFAULT_MODEL, "spent_usd": round(spent, 5), "rows": rows}, indent=1))
    lines = [
        "# G1: AI bill reader on the fixed test set",
        "",
        f"Run {when} with `{DEFAULT_MODEL}` on Fireworks, {len(rows)} bills (14 signed cases x 2 layouts), "
        f"model spend ${spent:.4f}. Produced by `scripts/g1_eval.py`; raw rows in `docs/g1_results.json`.",
        "",
        "PASS = every field the audit uses matches the signed case. BORDERLINE = all lines match, a header field "
        "differs. FAIL = a line differs or the reader refused the bill. Explanation = the AI summary passed the "
        "grounding checks (ai) or the explainer returned the template text (template).",
        "",
        f"**Extraction:** PASS {counts['PASS']} / BORDERLINE {counts['BORDERLINE']} / FAIL {counts['FAIL']} / "
        f"ERROR {counts['ERROR']} of {len(rows)}.  ",
        f"**Explanation:** ai {expl['ai']} / template {expl['template']}.",
        "",
        (ROOT / "docs" / "G1_notes.md").read_text().strip(),
        "",
        "| Case | Layout | Extraction | Explanation | Seconds | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        detail = (r["diff"] or r["explanation_reason"]).replace("|", "/")[:160]
        lines.append(f"| {r['case']} | {r['layout']} | {r['result']} | {r['explanation']} | {r['seconds']} | {detail} |")
    (ROOT / "docs" / "G1.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
