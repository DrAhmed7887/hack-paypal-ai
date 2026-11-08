"""PayPal SANDBOX client for BillCheck: Orders v2 (the patient pays the suggested amount) and Invoicing v2
(the provider's corrected itemized invoice, with the captured payment recorded on it, so nobody pays twice).

Credentials come from PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET (kept in Keychain, exported at run time).
Only the sandbox API is allowed.
"""

import hashlib
import os
import re
import time
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

import requests

from .models import AuditReport

SANDBOX_URL = "https://api-m.sandbox.paypal.com"
SAFE_ID = re.compile(r"^[A-Z0-9-]{5,40}$")


class PayPalError(RuntimeError):
    pass


def _usd(x: float) -> Dict[str, str]:
    return {"currency_code": "USD", "value": f"{x:.2f}"}


class PayPalClient:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 base_url: str = SANDBOX_URL, session: Optional[Any] = None, timeout_s: float = 15.0):
        if base_url != SANDBOX_URL:
            raise PayPalError("BillCheck only talks to the PayPal sandbox")
        self.client_id = client_id or os.environ.get("PAYPAL_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("PAYPAL_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise PayPalError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")
        self.base_url, self.timeout_s = base_url, timeout_s
        self.session = session or requests.Session()
        self._token: Optional[str] = None
        self._token_expiry = 0.0

    # ---- plumbing ---------------------------------------------------------------
    def _call(self, method: str, path: str, **kw: Any) -> Dict[str, Any]:
        try:
            resp = self.session.request(method, self.base_url + path, timeout=self.timeout_s, **kw)
        except requests.RequestException as exc:
            raise PayPalError(f"PayPal unreachable ({type(exc).__name__})") from exc
        try:
            body = resp.json() if resp.status_code != 204 else {}
        except ValueError:
            body = {}
        if not resp.ok:
            issues = ",".join(str(d.get("issue", "")) for d in body.get("details", []) if isinstance(d, dict))
            raise PayPalError(f"PayPal {resp.status_code} {body.get('name', '')} {issues} (debug_id {body.get('debug_id', '-')})")
        return body

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token
        body = self._call("POST", "/v1/oauth2/token", auth=(self.client_id, self.client_secret),
                          data={"grant_type": "client_credentials"},
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
        self._token = body.get("access_token")
        if not self._token:
            raise PayPalError("PayPal returned no access token")
        self._token_expiry = time.time() + max(60, int(body.get("expires_in", 300)) - 60)
        return self._token

    def _api(self, method: str, path: str, json_body: Optional[dict] = None,
             request_id: Optional[str] = None) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        return self._call(method, path, json=json_body, headers=headers)

    @staticmethod
    def _check_id(value: str) -> str:
        if not SAFE_ID.match(value or ""):
            raise PayPalError("unexpected PayPal id format")
        return value

    # ---- Orders v2: the patient's payment -----------------------------------------
    def create_settlement_order(self, report: AuditReport) -> Dict[str, str]:
        amount = report.total_suggested
        if not 0 < amount <= report.line_sum:
            raise PayPalError("nothing to pay, or the amount is above the billed lines")
        body = {"intent": "CAPTURE", "purchase_units": [{
            "reference_id": report.bill_id[:256],
            "description": f"BillCheck payment for bill {report.bill_id}"[:127],
            "amount": _usd(amount),
        }]}
        order = self._api("POST", "/v2/checkout/orders", body, request_id=f"billcheck-order-{uuid.uuid4()}")
        approve = next((link["href"] for link in order.get("links", [])
                        if link.get("rel") in ("payer-action", "approve")), "")
        return {"id": order.get("id", ""), "status": order.get("status", ""), "approve_url": approve}

    def capture_order(self, order_id: str) -> Dict[str, str]:
        order = self._api("POST", f"/v2/checkout/orders/{self._check_id(order_id)}/capture", {},
                          request_id=f"billcheck-capture-{order_id}")
        try:
            cap = order["purchase_units"][0]["payments"]["captures"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise PayPalError("capture response had no capture") from exc
        if order.get("status") != "COMPLETED" or cap.get("status") != "COMPLETED":
            raise PayPalError(f"capture not completed (order {order.get('status')}, capture {cap.get('status')})")
        return {"status": "COMPLETED", "capture_id": self._check_id(cap.get("id", "")),
                "amount": cap.get("amount", {}).get("value", ""),
                "payer_email": (order.get("payer") or {}).get("email_address", "")}

    # ---- Invoicing v2: the provider's corrected invoice ------------------------------
    def create_corrected_invoice(self, report: AuditReport, recipient_email: str) -> str:
        items = []
        for f in report.findings:
            code = f" ({f.cpt_code})" if f.cpt_code else ""
            if f.flag_type == "ABOVE_REFERENCE":
                desc = (f"Billed ${f.billed_amount:,.2f}; adjusted to the negotiation reference "
                        f"(2026 Medicare ${f.benchmark_amount:,.2f} x RAND multiplier).")
            else:
                desc = f"Billed ${f.billed_amount:,.2f}; unchanged."
            items.append({"name": f"{f.description}{code}"[:200], "description": desc[:1000],
                          "quantity": "1", "unit_amount": _usd(f.suggested_amount)})
        line_total = sum(Decimal(i["unit_amount"]["value"]) for i in items)
        if line_total != Decimal(f"{report.total_suggested:.2f}"):
            raise PayPalError("invoice lines do not add up to the suggested total")
        body = {
            "detail": {
                "currency_code": "USD",
                "invoice_date": date.today().isoformat(),
                "reference": report.bill_id[:120],
                "note": ("Itemized invoice at suggested amounts, prepared with BillCheck. Adjusted lines use a negotiation "
                         "reference based on public 2026 Medicare prices and the average private health plans "
                         f"paid relative to Medicare (RAND, 2022). Originally billed: ${report.line_sum:,.2f}.")[:4000],
            },
            "primary_recipients": [{"billing_info": {"email_address": recipient_email}}],
            "items": items,
        }
        key = hashlib.sha256(f"{report.bill_id}|{recipient_email.lower()}".encode()).hexdigest()[:32]
        created = self._api("POST", "/v2/invoicing/invoices", body, request_id=f"billcheck-invoice-{key}")
        href = created.get("href", "")
        return self._check_id(href.rstrip("/").rsplit("/", 1)[-1])

    def send_invoice(self, invoice_id: str) -> None:
        self._api("POST", f"/v2/invoicing/invoices/{self._check_id(invoice_id)}/send",
                  {"send_to_recipient": True, "send_to_invoicer": False}, request_id=f"billcheck-send-{invoice_id}")

    def record_payment(self, invoice_id: str, capture_id: str, amount: str) -> None:
        """amount and capture_id must come from capture_order's result held on the server, never from a browser."""
        self._api("POST", f"/v2/invoicing/invoices/{self._check_id(invoice_id)}/payments", {
            "method": "PAYPAL", "payment_date": date.today().isoformat(),
            "amount": {"currency_code": "USD", "value": amount},
            "note": f"Paid through PayPal Orders, capture {self._check_id(capture_id)}",
        }, request_id=f"billcheck-record-{capture_id}")
