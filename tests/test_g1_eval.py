"""G1 scoring boundaries and report counts (scripts/g1_eval.py)."""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
import g1_eval  # noqa: E402
from billcheck.models import MedicalBill  # noqa: E402
from test_ai import CASES  # noqa: E402

BILL = MedicalBill(**CASES["C08"]["bill"])


def _line(n: int, **changes) -> MedicalBill:
    items = [i.model_copy(update=changes) if k == n else i for k, i in enumerate(BILL.line_items)]
    return BILL.model_copy(update={"line_items": items})


def test_identical_bill_passes() -> None:
    assert g1_eval.score(BILL, BILL) == "PASS"


def test_unscored_fields_do_not_matter() -> None:
    other = BILL.model_copy(update={"provider_name": "X", "bill_id": "Y"})
    assert g1_eval.score(BILL, _line(0, description="other").model_copy(update={"provider_name": "X"})) == "PASS"
    assert g1_eval.score(BILL, other) == "PASS"


def test_header_difference_is_borderline() -> None:
    assert g1_eval.score(BILL, BILL.model_copy(update={"date_of_service": date(2026, 10, 16)})) == "BORDERLINE"
    assert g1_eval.score(BILL, BILL.model_copy(update={"total_billed": 1.0})) == "BORDERLINE"


def test_any_line_difference_fails() -> None:
    for change in ({"units": 2}, {"billed_amount": 1.0}, {"cpt_code": "99285"}, {"modifier": "26"}):
        assert g1_eval.score(BILL, _line(0, **change)) == "FAIL", change


def test_modifier_case_is_ignored() -> None:
    a, b = _line(0, modifier="tc"), _line(0, modifier="TC")
    assert g1_eval.score(a, b) == "PASS"


def test_report_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(g1_eval, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "G1_notes.md").write_text("notes")
    rows = [
        {"case": "C01", "layout": "table", "result": "PASS", "diff": "", "explanation": "ai", "explanation_reason": "", "seconds": 1},
        {"case": "C02", "layout": "table", "result": "FAIL", "diff": "x|y", "explanation": "-", "explanation_reason": "", "seconds": 1},
        {"case": "C03", "layout": "letter", "result": "PASS", "diff": "", "explanation": "template", "explanation_reason": "r", "seconds": 1},
    ]
    g1_eval.write_report(rows, 0.01, "2026-11-08 14:06 UTC")
    md = (tmp_path / "docs" / "G1.md").read_text()
    assert "PASS 2 / BORDERLINE 0 / FAIL 1 / ERROR 0 of 3" in md
    assert "ai 1 / template 1" in md and "x/y" in md and "notes" in md
    assert json.loads((tmp_path / "docs" / "g1_results.json").read_text())["run_at"] == "2026-11-08 14:06 UTC"
