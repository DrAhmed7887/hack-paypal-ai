"""The packaged demo bills must be exact copies of signed test cases (no drift)."""

import json
from importlib import resources
from pathlib import Path


def test_demo_bills_match_signed_cases() -> None:
    signed = {c["id"]: c["bill"] for c in json.loads((Path(__file__).parents[1] / "data" / "cases.json").read_text())["cases"]}
    demo = json.loads(resources.files("billcheck").joinpath("demo_cases.json").read_text())
    assert demo and all(d["bill"] == signed[d["id"]] for d in demo)
