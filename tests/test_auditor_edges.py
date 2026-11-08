"""Regression tests for code-review findings on the auditor (item 4 review)."""

import math

import pytest
from pydantic import ValidationError

from billcheck.auditor import BillAuditor
from billcheck.models import BillLineItem, MedicalBill


def _bill(claim_type: str, day: str, *lines: BillLineItem) -> MedicalBill:
    return MedicalBill(bill_id="T", provider_name="Test (Synthetic)", claim_type=claim_type, date_of_service=day,
                       line_items=list(lines), total_billed=sum(i.billed_amount for i in lines))


def _flags(bill: MedicalBill) -> list:
    return [f.flag_type for f in BillAuditor().audit(bill).findings]


@pytest.mark.parametrize("modifier", ["evidence", "global", "25", "XY"])
def test_unknown_modifier_is_not_available_not_a_crash(modifier: str) -> None:
    line = BillLineItem(line_id="L1", description="x", cpt_code="99284", modifier=modifier, billed_amount=850)
    finding = BillAuditor().audit(_bill("professional", "2026-10-15", line)).findings[0]
    assert finding.flag_type == "NOT_AVAILABLE" and modifier not in finding.explanation


def test_lowercase_component_modifier_is_accepted() -> None:
    line = BillLineItem(line_id="L1", description="CT read", cpt_code="70450", modifier="26", billed_amount=400)
    tc = BillLineItem(line_id="L2", description="CT tech", cpt_code="70450", modifier="tc", billed_amount=500)
    findings = BillAuditor().audit(_bill("professional", "2026-10-15", line, tc)).findings
    assert [f.benchmark_amount for f in findings] == [39.41, 67.14]


def test_packaged_lab_respects_october_release_date() -> None:
    visit = BillLineItem(line_id="L1", description="ED", cpt_code="99284", billed_amount=2000)
    lab = BillLineItem(line_id="L2", description="CMP", cpt_code="80053", billed_amount=180)
    assert _flags(_bill("facility", "2026-09-15", visit, lab)) == ["NOT_AVAILABLE", "NOT_AVAILABLE"]


def test_hospital_bill_with_only_labs_has_no_signed_rule() -> None:
    cmp_ = BillLineItem(line_id="L1", description="CMP", cpt_code="80053", billed_amount=180)
    cbc = BillLineItem(line_id="L2", description="CBC", cpt_code="85025", billed_amount=95)
    assert _flags(_bill("facility", "2026-10-15", cmp_, cbc)) == ["NOT_AVAILABLE", "NOT_AVAILABLE"]


def test_same_line_object_twice_is_two_ct_procedures() -> None:
    ct = BillLineItem(line_id="L1", description="CT", cpt_code="70450", billed_amount=1650)
    assert _flags(_bill("facility", "2026-10-15", ct, ct)) == ["NOT_AVAILABLE", "NOT_AVAILABLE"]


def test_ratio_printed_with_two_decimals() -> None:
    line = BillLineItem(line_id="L1", description="ED", cpt_code="99284", billed_amount=1182.40)
    text = BillAuditor().audit(_bill("professional", "2026-10-15", line)).findings[0].explanation
    assert "10.00x" in text


@pytest.mark.parametrize("amount", [math.inf, math.nan])
def test_infinite_or_nan_amounts_rejected(amount: float) -> None:
    with pytest.raises(ValidationError):
        BillLineItem(line_id="L1", description="x", cpt_code="99284", billed_amount=amount)
