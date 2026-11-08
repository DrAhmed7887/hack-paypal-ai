"""AI layer: spend cap, bill extraction and grounded explanations, with a fake model (no network)."""

import json
from datetime import date
from pathlib import Path
from typing import List

import pytest

from billcheck.auditor import BillAuditor
from billcheck.explainer import explain
from billcheck.extractor import ExtractionError, extract_bill
from billcheck.llm import LLMReply, SpendCapReached, SpendGuard
from billcheck.models import MedicalBill

CASES = {c["id"]: c for c in json.loads((Path(__file__).parents[1] / "data" / "cases.json").read_text())["cases"]}
BILL_TEXT = """RIVERSIDE COMMUNITY HOSPITAL (SYNTHETIC) - HOSPITAL OUTPATIENT STATEMENT
Statement: C08   Date of service: 10/15/2026
L1  99284  ED visit level 4      1  $2,400.00
L2  70450  CT head               1  $1,650.00
L3  80053  Metabolic panel       1    $180.00
L4  85025  CBC                   1     $95.00
L5  96372  Injection             1    $120.00
TOTAL CHARGES                       $4,445.00
"""


class FakeLLM:
    """Returns canned replies in order and records the prompts it was given."""

    def __init__(self, *replies: str):
        self.replies: List[str] = list(replies)
        self.prompts: List[list] = []

    def chat(self, messages: list, json_mode: bool = False, schema=None) -> LLMReply:
        self.prompts.append(messages)
        return LLMReply(text=self.replies.pop(0), cost_usd=0.0)


# ---- spend guard -------------------------------------------------------------
def test_spend_guard_blocks_at_daily_cap(tmp_path: Path) -> None:
    guard = SpendGuard(cap_usd=0.01, ledger_dir=tmp_path, today=lambda: date(2026, 11, 9))
    guard.check()
    guard.record(0.006)
    guard.check()
    guard.record(0.006)
    with pytest.raises(SpendCapReached):
        guard.check()
    assert guard.spent_today() == pytest.approx(0.012)


def test_spend_guard_resets_next_day(tmp_path: Path) -> None:
    day = {"d": date(2026, 11, 9)}
    guard = SpendGuard(cap_usd=0.01, ledger_dir=tmp_path, today=lambda: day["d"])
    guard.record(0.02)
    day["d"] = date(2026, 11, 10)
    guard.check()


# ---- extraction --------------------------------------------------------------
def _c08_json() -> str:
    return json.dumps(CASES["C08"]["bill"])


def test_extracts_bill_matching_the_case() -> None:
    bill = extract_bill(BILL_TEXT, FakeLLM(_c08_json()))
    assert bill == MedicalBill(**CASES["C08"]["bill"])


def test_rejects_amount_not_written_on_the_bill() -> None:
    data = CASES["C08"]["bill"] | {"line_items": [dict(CASES["C08"]["bill"]["line_items"][0], billed_amount=2500.00)]}
    with pytest.raises(ExtractionError, match="not found in the bill text"):
        extract_bill(BILL_TEXT, FakeLLM(json.dumps(data)))


def test_rejects_code_not_written_on_the_bill() -> None:
    items = [dict(i) for i in CASES["C08"]["bill"]["line_items"]]
    items[4]["cpt_code"] = "96374"
    with pytest.raises(ExtractionError, match="not found in the bill text"):
        extract_bill(BILL_TEXT, FakeLLM(json.dumps(CASES["C08"]["bill"] | {"line_items": items})))


@pytest.mark.parametrize("reply", ["not json", '{"bill_id": "x"}', "[]"])
def test_rejects_invalid_model_output(reply: str) -> None:
    with pytest.raises(ExtractionError):
        extract_bill(BILL_TEXT, FakeLLM(reply))


def test_empty_text_is_rejected_without_a_model_call() -> None:
    llm = FakeLLM()
    with pytest.raises(ExtractionError):
        extract_bill("   ", llm)
    assert llm.prompts == []


# ---- explanation -------------------------------------------------------------
def _report():
    return BillAuditor().audit(MedicalBill(**CASES["C08"]["bill"]))


def test_grounded_ai_explanation_is_used() -> None:
    text = ("Two charges are above the negotiation reference: the ED visit ($2,400.00 billed, suggested $1,189.38) "
            "and the CT scan ($1,650.00 billed, suggested $298.00). The potential negotiation difference is $2,562.62.")
    out = explain(_report(), FakeLLM(text))
    assert out.source == "ai" and out.text == text


@pytest.mark.parametrize("bad, reason", [
    ("The ED visit should cost $1,000.00.", "amount not in the report: $1,000.00"),
    ("The hospital made an error on the ED visit ($2,400.00).", "banned word: error"),
    ("", "empty"),
])
def test_ungrounded_explanation_falls_back_to_template(bad: str, reason: str) -> None:
    out = explain(_report(), FakeLLM(bad))
    assert out.source == "template" and out.reason == reason
    assert "$2,562.62" in out.text and "negotiation reference" in out.text


def test_model_failure_falls_back_to_template() -> None:
    class Broken:
        def chat(self, messages: list, json_mode: bool = False) -> LLMReply:
            raise SpendCapReached("cap")

    out = explain(_report(), Broken())
    assert out.source == "template"
