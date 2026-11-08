"""Every rendered test bill must pass the reader's own grounding checks when the model answers perfectly."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from billcheck.extractor import extract_bill  # noqa: E402
from billcheck.models import MedicalBill  # noqa: E402
from billcheck.render import LAYOUTS  # noqa: E402
from test_ai import CASES, FakeLLM  # noqa: E402


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
@pytest.mark.parametrize("case_id", sorted(CASES))
def test_rendered_bill_is_groundable(case_id: str, layout: str) -> None:
    bill = MedicalBill(**CASES[case_id]["bill"])
    text = LAYOUTS[layout](bill)
    assert extract_bill(text, FakeLLM(json.dumps(CASES[case_id]["bill"]))) == bill
