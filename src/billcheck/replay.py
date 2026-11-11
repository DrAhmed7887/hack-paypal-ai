"""Replay mode (BILLCHECK_REPLAY=1): lets anyone click through the whole app with no keys and no network.

The AI step returns recorded/fixture outputs for the sample bills, and the PayPal client returns recorded sandbox
responses. Everything else runs for real: extraction grounding checks, the auditor and its rules, rendering, the
summary check, and the server-held amount, capture and invoice rules in the web app.
Nothing here calls the network: ReplayPayPal reuses the real PayPalClient request building and parsing, but its
transport is replaced by recorded responses.
"""

import hashlib
import json
import itertools
import os
import threading
from importlib import resources
from typing import Any, Dict, Optional

from .llm import LLMError, LLMReply
from .models import MedicalBill
from .paypal_client import PayPalClient, PayPalError
from .render import render_table

BANNER = ("Replay mode: no AI model and no PayPal are called. The bill reading, the PayPal responses and the "
          "payment below are recorded or simulated for the five sample bills. The audit itself (prices, rules, "
          "totals) runs live on this machine. Uploads and pasted bills other than the samples are not supported here.")
SIMULATE_LABEL = "Simulate sandbox payment (replay)"
RECEIPT_NOTE = ("Replay: the capture and invoice ids are recorded from the 11 Nov 2026 sandbox run of sample C08; "
                "the amount is computed for this bill. No payment was made.")


def enabled() -> bool:
    return os.environ.get("BILLCHECK_REPLAY", "").strip().lower() in ("1", "true", "yes")


class ReplayMiss(LLMError):
    """The text is not one of the recorded sample bills."""


def _read(name: str) -> Any:
    return json.loads(resources.files("billcheck").joinpath(name).read_text(encoding="utf-8"))


def _key(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").strip().encode()).hexdigest()  # browsers send CRLF


class ReplayLLM:
    """Same chat() interface as FireworksLLM. Extraction replies come from the demo cases; summaries from the recording."""

    def __init__(self) -> None:
        self.bills: Dict[str, str] = {}
        for case in _read("demo_cases.json"):
            bill = MedicalBill(**case["bill"])
            self.bills[_key(render_table(bill))] = bill.model_dump_json()
        self.summaries: Dict[str, str] = _read("replay_fixtures.json")["summaries"]

    def chat(self, messages: list, json_mode: bool = False, schema: Optional[dict] = None) -> LLMReply:
        if json_mode:
            content = str(messages[-1]["content"])
            text = content.removeprefix("<bill>\n").removesuffix("\n</bill>")
            if _key(text) not in self.bills:
                raise ReplayMiss("not a recorded sample bill")
            return LLMReply(text=self.bills[_key(text)], cost_usd=0.0)
        audit = json.loads(str(messages[-1]["content"]).split("Audit JSON:\n", 1)[-1])
        if audit.get("bill_id") not in self.summaries:
            raise ReplayMiss("no recorded summary for this bill")  # explain() falls back to the fixed template
        return LLMReply(text=self.summaries[audit["bill_id"]], cost_usd=0.0)


class ReplayPayPal(PayPalClient):
    """The real PayPalClient with its transport replaced by recorded sandbox responses (never touches the network).
    Holds the amount of each order it created, so use one shared instance per app."""

    def __init__(self) -> None:  # no credentials needed
        self.fx = _read("replay_fixtures.json")["paypal"]
        self.amounts: Dict[str, str] = {}
        self._lock, self._counter = threading.Lock(), itertools.count(1)  # the web app calls from several threads

    def _call(self, method: str, path: str, **kw: Any) -> Dict[str, Any]:
        raise PayPalError("replay mode never uses the network")

    def _api(self, method: str, path: str, json_body: Optional[dict] = None,
             request_id: Optional[str] = None) -> Dict[str, Any]:
        fx = self.fx
        if (method, path) == ("POST", "/v2/checkout/orders"):
            amount = json_body["purchase_units"][0]["amount"]["value"]
            with self._lock:
                order_id = f"REPLAY-ORDER-{next(self._counter)}"
                self.amounts[order_id] = amount
            return {"id": order_id, **fx["order"]}
        if method == "POST" and path.startswith("/v2/checkout/orders/") and path.endswith("/capture"):
            order_id = path.split("/")[4]
            if order_id not in self.amounts:
                raise PayPalError("unknown order in replay")
            return {"status": "COMPLETED", "payer": {"email_address": fx["payer_email"]},
                    "purchase_units": [{"payments": {"captures": [{
                        "id": fx["capture_id"], "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": self.amounts[order_id]}}]}}]}
        if (method, path) == ("POST", "/v2/invoicing/invoices"):
            return {"href": f"https://api-m.sandbox.paypal.com/v2/invoicing/invoices/{fx['invoice_id']}"}
        if method == "POST" and path.startswith("/v2/invoicing/invoices/"):
            return {}  # send and record-payment: recorded as accepted
        raise PayPalError(f"no recorded response for {method} {path}")
