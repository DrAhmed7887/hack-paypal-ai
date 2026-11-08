"""BillCheck auditor against the fixed synthetic test set (data/cases.json).

Expected results in data/cases.json were written by hand from docs/DECISIONS.md v1.3 (incl. R3c)
before the auditor was implemented.
"""

import json
import re
from pathlib import Path

import pytest

from billcheck.auditor import BANNED_WORDS, BillAuditor
from billcheck.models import MedicalBill

CASES = json.loads((Path(__file__).parents[1] / "data" / "cases.json").read_text())["cases"]


@pytest.fixture(scope="module")
def auditor() -> BillAuditor:
    return BillAuditor()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_matches_expected(auditor: BillAuditor, case: dict) -> None:
    report = auditor.audit(MedicalBill(**case["bill"]))
    found = {f.line_id: f for f in report.findings}
    assert set(found) == set(case["expected"]["lines"])
    for line_id, exp in case["expected"]["lines"].items():
        f = found[line_id]
        assert f.flag_type == exp["flag"], line_id
        assert f.benchmark_amount == exp["benchmark"], line_id
        assert f.suggested_amount == pytest.approx(exp["suggested"], abs=0.005), line_id
    t = case["expected"]["totals"]
    assert report.line_sum == pytest.approx(t["line_sum"], abs=0.005)
    assert report.total_suggested == pytest.approx(t["total_suggested"], abs=0.005)
    assert report.potential_negotiation_difference == pytest.approx(t["difference"], abs=0.005)
    assert report.totals_match is t["totals_match"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_wording_rules(auditor: BillAuditor, case: dict) -> None:
    report = auditor.audit(MedicalBill(**case["bill"]))
    for f in report.findings:
        assert not BANNED_WORDS.search(f.explanation), f.explanation
        if f.flag_type == "NOT_AVAILABLE":
            assert f.markup_ratio is None and "benchmark not available" in f.explanation.lower()
        if f.flag_type == "NOT_FLAGGED":
            assert "not flagged by this comparison" in f.explanation.lower()
        if f.flag_type == "ABOVE_REFERENCE":
            assert f.evidence and "RAND" in f.explanation
        assert f.suggested_amount <= f.billed_amount


def test_every_benchmark_cites_evidence(auditor: BillAuditor) -> None:
    for code, entry in auditor.table["codes"].items():
        for schedule in ("pfs", "clfs", "opps"):
            if schedule in entry:
                assert re.fullmatch(r"E\d+(-E\d+)?", entry[schedule]["evidence"]), (code, schedule)
