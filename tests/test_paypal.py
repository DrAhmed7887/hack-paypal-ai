"""PayPal sandbox client: orders, corrected invoice, recorded payment. Uses a fake HTTP session (no network)."""

import json
from pathlib import Path
from typing import List

import pytest

from billcheck.auditor import BillAuditor
from billcheck.models import MedicalBill
from billcheck.paypal_client import PayPalClient, PayPalError

CASES = {c["id"]: c for c in json.loads((Path(__file__).parents[1] / "data" / "cases.json").read_text())["cases"]}
REPORT = BillAuditor().audit(MedicalBill(**CASES["C08"]["bill"]))


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code, self._body = status, body
        self.ok = 200 <= status < 300

    def json(self) -> dict:
        return self._body


class FakeSession:
    """Answers by (method, path suffix); records every call."""

    def __init__(self, routes: dict):
        self.routes, self.calls = routes, []  # type: dict, List[dict]

    def request(self, method: str, url: str, **kw) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kw})
        for (m, suffix), resp in self.routes.items():
            if m == method and url.endswith(suffix):
                return resp
        return FakeResponse(404, {"name": "RESOURCE_NOT_FOUND", "debug_id": "x"})


TOKEN = {("POST", "/v1/oauth2/token"): FakeResponse(200, {"access_token": "tok", "expires_in": 3600})}


def _client(routes: dict) -> PayPalClient:
    return PayPalClient("id", "secret", session=FakeSession({**TOKEN, **routes}))


def test_live_api_is_refused() -> None:
    with pytest.raises(PayPalError, match="sandbox"):
        PayPalClient("id", "secret", base_url="https://api-m.paypal.com")


def test_missing_credentials_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    with pytest.raises(PayPalError):
        PayPalClient()


def test_token_is_cached() -> None:
    client = _client({("POST", "/v2/checkout/orders"): FakeResponse(201, {"id": "5O190127TN364715T", "status": "CREATED", "links": []})})
    client.create_settlement_order(REPORT)
    client.create_settlement_order(REPORT)
    assert sum(c["url"].endswith("/oauth2/token") for c in client.session.calls) == 1


def test_order_is_for_the_suggested_total_with_idempotency_key() -> None:
    created = {"id": "5O190127TN364715T", "status": "CREATED",
               "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow/5O190127TN364715T"}]}
    client = _client({("POST", "/v2/checkout/orders"): FakeResponse(201, created)})
    order = client.create_settlement_order(REPORT)
    call = client.session.calls[-1]
    unit = call["json"]["purchase_units"][0]
    assert unit["amount"] == {"currency_code": "USD", "value": "1882.38"}
    assert unit["reference_id"] == "C08" and call["headers"]["PayPal-Request-Id"]
    assert order == {"id": "5O190127TN364715T", "status": "CREATED", "approve_url": "https://www.sandbox.paypal.com/checkoutnow/5O190127TN364715T"}


def test_capture_returns_capture_id_and_amount() -> None:
    captured = {"id": "5O190127TN364715T", "status": "COMPLETED", "payer": {"email_address": "buyer@personal.example.com"}, "purchase_units": [{"payments": {"captures": [
        {"id": "3C679366HH908993F", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "1882.38"}}]}}]}
    client = _client({("POST", "/v2/checkout/orders/5O190127TN364715T/capture"): FakeResponse(201, captured)})
    assert client.capture_order("5O190127TN364715T") == {"status": "COMPLETED", "capture_id": "3C679366HH908993F", "amount": "1882.38",
                                                  "payer_email": "buyer@personal.example.com"}


def test_capture_rejects_odd_order_ids() -> None:
    with pytest.raises(PayPalError):
        _client({}).capture_order("../v1/oauth2/token")


def test_corrected_invoice_lines_sum_to_the_suggested_total() -> None:
    client = _client({("POST", "/v2/invoicing/invoices"): FakeResponse(
        201, {"href": "https://api-m.sandbox.paypal.com/v2/invoicing/invoices/INV2-AAAA"})})
    invoice_id = client.create_corrected_invoice(REPORT, "patient@personal.example.com")
    body = client.session.calls[-1]["json"]
    total = sum(float(i["unit_amount"]["value"]) * float(i["quantity"]) for i in body["items"])
    assert invoice_id == "INV2-AAAA" and round(total, 2) == REPORT.total_suggested
    assert body["primary_recipients"][0]["billing_info"]["email_address"] == "patient@personal.example.com"
    ed = body["items"][0]
    assert ed["unit_amount"]["value"] == "1189.38" and "$2,400.00" in ed["description"]
    assert all(len(i["name"]) <= 200 and len(i.get("description", "")) <= 1000 for i in body["items"])
    assert "negotiation reference" in body["detail"]["note"]


def test_send_and_record_payment() -> None:
    client = _client({("POST", "/v2/invoicing/invoices/INV2-AAAA/send"): FakeResponse(200, {}),
                      ("POST", "/v2/invoicing/invoices/INV2-AAAA/payments"): FakeResponse(200, {"payment_id": "P1"})})
    client.send_invoice("INV2-AAAA")
    client.record_payment("INV2-AAAA", "3C679366HH908993F", "1882.38")
    pay = client.session.calls[-1]["json"]
    assert pay["method"] == "PAYPAL" and pay["amount"] == {"currency_code": "USD", "value": "1882.38"}
    assert "3C679366HH908993F" in pay["note"]


def test_api_error_is_reported_without_secrets() -> None:
    client = _client({("POST", "/v2/checkout/orders"): FakeResponse(
        422, {"name": "UNPROCESSABLE_ENTITY", "debug_id": "abc123", "message": "bad"})})
    with pytest.raises(PayPalError) as err:
        client.create_settlement_order(REPORT)
    text = str(err.value)
    assert "UNPROCESSABLE_ENTITY" in text and "abc123" in text and "secret" not in text and "tok" not in text


def test_nothing_to_pay_is_refused() -> None:
    zero = REPORT.model_copy(update={"total_suggested": 0.0})
    with pytest.raises(PayPalError):
        _client({}).create_settlement_order(zero)


def test_incomplete_capture_is_an_error() -> None:
    pending = {"id": "5O190127TN364715T", "status": "PAYER_ACTION_REQUIRED", "purchase_units": [{"payments": {
        "captures": [{"id": "3C679366HH908993F", "status": "PENDING", "amount": {"value": "1882.38"}}]}}]}
    client = _client({("POST", "/v2/checkout/orders/5O190127TN364715T/capture"): FakeResponse(201, pending)})
    with pytest.raises(PayPalError, match="not completed"):
        client.capture_order("5O190127TN364715T")


def test_invoice_retry_reuses_the_same_request_id() -> None:
    client = _client({("POST", "/v2/invoicing/invoices"): FakeResponse(
        201, {"href": "https://api-m.sandbox.paypal.com/v2/invoicing/invoices/INV2-AAAA"})})
    client.create_corrected_invoice(REPORT, "a@personal.example.com")
    client.create_corrected_invoice(REPORT, "A@personal.example.com")
    keys = [c["headers"]["PayPal-Request-Id"] for c in client.session.calls if c["url"].endswith("/invoices")]
    assert keys[0] == keys[1]


def test_record_payment_is_idempotent_per_capture() -> None:
    client = _client({("POST", "/v2/invoicing/invoices/INV2-AAAA/payments"): FakeResponse(200, {})})
    client.record_payment("INV2-AAAA", "3C679366HH908993F", "1882.38")
    assert client.session.calls[-1]["headers"]["PayPal-Request-Id"] == "billcheck-record-3C679366HH908993F"
