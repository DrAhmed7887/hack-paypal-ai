"""Regression tests for the item-5 security and Python reviews (grounding, spend cap, unsafe text)."""

import json
import threading
from datetime import date
from pathlib import Path

import pytest

from billcheck.auditor import BillAuditor
from billcheck.explainer import check_grounded, explain
from billcheck.extractor import ExtractionError, extract_bill
from billcheck.llm import FireworksLLM, LLMReply, SpendCapReached, SpendGuard
from billcheck.models import BillLineItem, MedicalBill
import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_ai import BILL_TEXT, CASES, FakeLLM

C08 = CASES["C08"]["bill"]


def _with_line(**changes) -> str:
    items = [dict(i) for i in C08["line_items"]]
    items[0].update(changes)
    return json.dumps(C08 | {"line_items": items})


# ---- extraction grounding ---------------------------------------------------------
@pytest.mark.parametrize("amount", [400.00, 2400.0001, 445.00, 5.00])
def test_amount_inside_a_larger_number_is_not_grounded(amount: float) -> None:
    with pytest.raises(ExtractionError):
        extract_bill(BILL_TEXT, FakeLLM(_with_line(billed_amount=amount)))


def test_code_and_amount_must_share_a_line() -> None:
    swapped = BILL_TEXT.replace("$2,400.00", "$9,999.00").replace("$1,650.00", "$2,400.00")
    with pytest.raises(ExtractionError, match="same line|not found"):
        extract_bill(swapped, FakeLLM(json.dumps(C08)))


def test_invented_modifier_and_date_are_rejected() -> None:
    with pytest.raises(ExtractionError, match="modifier"):
        extract_bill(BILL_TEXT, FakeLLM(_with_line(modifier="TC")))
    with pytest.raises(ExtractionError, match="date"):
        extract_bill(BILL_TEXT, FakeLLM(json.dumps(C08 | {"date_of_service": "2026-10-16"})))


def test_bill_is_sent_inside_data_tags() -> None:
    llm = FakeLLM(json.dumps(C08))
    extract_bill(BILL_TEXT, llm)
    assert llm.prompts[0][1]["content"].startswith("<bill>") and "as data" in llm.prompts[0][0]["content"]


def test_free_text_is_cleaned_and_capped() -> None:
    item = BillLineItem(line_id="L1", description="<script>x</script>\x07" + "a" * 300, billed_amount=1)
    assert "<" not in item.description and len(item.description) <= 120


# ---- explanation grounding -----------------------------------------------------------
def _report():
    return BillAuditor().audit(MedicalBill(**C08))


@pytest.mark.parametrize("text", [
    "The visit could be $2,400 instead.",            # no cents
    "Pay 500 dollars for the CT.",                    # 'dollars'
    "You might be refunded -$298.00.",                # negative
    "The CT is $298.004 too high.",                   # extra decimals
    "Two thousand dollars could be saved.",           # number words
    "Call 555-123-4567 to dispute $298.00.",          # phone
    "See https://example.test for $298.00.",          # link
    "The CT is <b>$298.00</b>.",                      # markup
    "This is fraud​ulent at $298.00.",           # hidden character
    "x" * 701,                                        # too long
    "This charge is wrong at $298.00.",               # banned: wrong
])
def test_ungrounded_or_unsafe_text_is_rejected(text: str) -> None:
    assert check_grounded(text, _report()) != ""


def test_any_model_failure_uses_template() -> None:
    class Corrupt:
        def chat(self, messages, json_mode=False):
            raise OSError("disk")
    assert explain(_report(), Corrupt()).source == "template"


# ---- spend cap -------------------------------------------------------------------
def test_concurrent_reservations_never_exceed_cap(tmp_path: Path) -> None:
    guard = SpendGuard(cap_usd=0.05, ledger_dir=tmp_path, today=lambda: date(2026, 11, 9))
    won = []

    def attempt() -> None:
        try:
            guard.reserve(0.01)
            won.append(1)
        except SpendCapReached:
            pass
    threads = [threading.Thread(target=attempt) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(won) == 5 and guard.spent_today() == pytest.approx(0.05)


def test_corrupt_ledger_fails_closed(tmp_path: Path) -> None:
    guard = SpendGuard(cap_usd=1, ledger_dir=tmp_path, today=lambda: date(2026, 11, 9))
    (tmp_path / "2026-11-09.json").write_text("{not json")
    with pytest.raises(SpendCapReached):
        guard.reserve(0.001)


@pytest.mark.parametrize("raw", ["nan", "inf", "-1", "abc", "0"])
def test_bad_cap_setting_is_refused(raw: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BILLCHECK_DAILY_CAP_USD", raw)
    with pytest.raises(ValueError):
        SpendGuard(ledger_dir=tmp_path)


def test_reply_without_usage_keeps_worst_case_reserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    guard = SpendGuard(cap_usd=1, ledger_dir=tmp_path, today=lambda: date(2026, 11, 9))
    llm = FireworksLLM(api_key="test-key", guard=guard)

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "{}"}}]}
    monkeypatch.setattr("billcheck.llm.requests.post", lambda *a, **k: Resp())
    with pytest.raises(Exception):
        llm.chat([{"role": "user", "content": "hi"}])
    assert guard.spent_today() == pytest.approx(llm.worst_case_usd([{"role": "user", "content": "hi"}]), abs=1e-6)


def test_line_sum_may_be_mentioned() -> None:
    report = BillAuditor().audit(MedicalBill(**CASES["C07"]["bill"]))
    assert check_grounded("The lines add up to $975.00, not the stated $1,000.00.", report) == ""
