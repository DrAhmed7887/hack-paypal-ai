"""Web app flow with a fake model and a fake PayPal: audit → order → capture → corrected invoice."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from billcheck.paypal_client import PayPalError  # noqa: E402
from billcheck.web import app as web  # noqa: E402
from test_ai import CASES  # noqa: E402
from test_ai import FakeLLM as _FakeLLM  # noqa: E402

C08 = CASES["C08"]["bill"]
EXPLANATION = "Two lines are above the negotiation reference; the potential negotiation difference is $2,562.62."


class FakeLLM(_FakeLLM):
    def __init__(self):
        super().__init__(json.dumps(C08), EXPLANATION)


class FakePayPal:
    calls: list = []
    capture_amount = "1882.38"

    def create_settlement_order(self, report):
        FakePayPal.calls.append(("order", report.total_suggested))
        return {"id": "5O190127TN364715T", "status": "CREATED", "approve_url": "u"}

    def capture_order(self, order_id):
        FakePayPal.calls.append(("capture", order_id))
        return {"status": "COMPLETED", "capture_id": "3C679366HH908993F", "amount": FakePayPal.capture_amount,
                "payer_email": "buyer@personal.example.com"}

    def create_corrected_invoice(self, report, email):
        FakePayPal.calls.append(("invoice", email))
        return "INV2-X5XP-5VZX-VN62-QYR8"

    def send_invoice(self, invoice_id):
        FakePayPal.calls.append(("send", invoice_id))

    def record_payment(self, invoice_id, capture_id, amount):
        FakePayPal.calls.append(("record", capture_id, amount))


@pytest.fixture()
def client() -> TestClient:
    FakePayPal.calls, FakePayPal.capture_amount = [], "1882.38"
    return TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=FakePayPal))


def _audit(client: TestClient) -> dict:
    sample = client.get("/api/samples/C08").json()["text"]
    resp = client.post("/api/audit", data={"text": sample})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_page_and_config(client: TestClient) -> None:
    assert "BillCheck" in client.get("/").text
    cfg = client.get("/api/config").json()
    assert [s["id"] for s in cfg["samples"]] == ["C08", "C01", "C04", "C10", "C11"]


def test_full_flow_pays_the_server_held_amount(client: TestClient) -> None:
    r = _audit(client)
    assert r["total_suggested"] == 1882.38 and r["summary"]["source"] == "ai"
    assert client.post(f"/api/audits/{r['audit_id']}/order").json()["order_id"] == "5O190127TN364715T"
    rec = client.post(f"/api/audits/{r['audit_id']}/capture").json()
    assert rec["status"] == "paid" and rec["amount"] == "1882.38" and rec["invoice_id"] == "INV2-X5XP-5VZX-VN62-QYR8"
    assert ("invoice", "buyer@personal.example.com") in FakePayPal.calls
    assert ("record", "3C679366HH908993F", "1882.38") in FakePayPal.calls


def test_double_clicks_do_not_double_charge(client: TestClient) -> None:
    r = _audit(client)
    a = client.post(f"/api/audits/{r['audit_id']}/order").json()
    b = client.post(f"/api/audits/{r['audit_id']}/order").json()
    client.post(f"/api/audits/{r['audit_id']}/capture")
    client.post(f"/api/audits/{r['audit_id']}/capture")
    assert a == b
    assert [c[0] for c in FakePayPal.calls].count("order") == 1
    assert [c[0] for c in FakePayPal.calls].count("capture") == 1
    assert [c[0] for c in FakePayPal.calls].count("record") == 1


def test_browser_cannot_set_amounts(client: TestClient) -> None:
    r = _audit(client)
    client.post(f"/api/audits/{r['audit_id']}/order", json={"amount": 1.0})
    assert ("order", 1882.38) in FakePayPal.calls


def test_capture_amount_mismatch_is_refused(client: TestClient) -> None:
    FakePayPal.capture_amount = "1.00"
    r = _audit(client)
    client.post(f"/api/audits/{r['audit_id']}/order")
    resp = client.post(f"/api/audits/{r['audit_id']}/capture")
    assert resp.status_code == 502 and "does not match" in resp.json()["error"]
    assert not any(c[0] == "invoice" for c in FakePayPal.calls)


def test_capture_before_order_and_unknown_audit(client: TestClient) -> None:
    r = _audit(client)
    assert client.post(f"/api/audits/{r['audit_id']}/capture").status_code == 409
    assert client.post("/api/audits/nope/order").status_code == 404


def test_unreadable_bill_is_a_clear_error(client: TestClient) -> None:
    resp = client.post("/api/audit", data={"text": "hello"})
    assert resp.status_code == 422 and "could not read this bill" in resp.json()["error"]


def test_upload_size_limit(client: TestClient) -> None:
    big = b"x" * (web.MAX_UPLOAD_BYTES + 1)
    resp = client.post("/api/audit", files={"file": ("bill.txt", big, "text/plain")})
    assert resp.status_code == 413


def test_rate_limit_per_ip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "AUDITS_PER_IP_PER_HOUR", 2)
    limited = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=FakePayPal))
    text = limited.get("/api/samples/C08").json()["text"]
    codes = [limited.post("/api/audit", data={"text": text}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_paypal_failure_is_reported(client: TestClient) -> None:
    class Down(FakePayPal):
        def create_settlement_order(self, report):
            raise PayPalError("PayPal 503 SERVICE_UNAVAILABLE (debug_id x)")

    c = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=Down))
    r = c.post("/api/audit", data={"text": c.get("/api/samples/C08").json()["text"]}).json()
    resp = c.post(f"/api/audits/{r['audit_id']}/order")
    assert resp.status_code == 502 and "could not create the payment" in resp.json()["error"]


def test_security_headers_and_early_size_limit(client: TestClient) -> None:
    resp = client.get("/")
    assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]
    assert resp.headers["x-content-type-options"] == "nosniff"
    big = client.post("/api/audit", content=b"x", headers={"content-length": str(10_000_000),
                                                            "content-type": "text/plain"})
    assert big.status_code == 413


def test_garbage_pdf_is_a_clear_error(client: TestClient) -> None:
    resp = client.post("/api/audit", files={"file": ("bill.pdf", b"%PDF-1.7 not really a pdf", "application/pdf")})
    assert resp.status_code == 400 and "PDF could not be read" in resp.json()["error"]


def test_invoice_failure_is_reported_and_retry_resumes(client: TestClient) -> None:
    class Flaky(FakePayPal):
        fail = True

        def send_invoice(self, invoice_id):
            if Flaky.fail:
                raise PayPalError("PayPal 500 INTERNAL_SERVER_ERROR (debug_id x)")
            super().send_invoice(invoice_id)

    c = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=Flaky))
    r = c.post("/api/audit", data={"text": c.get("/api/samples/C08").json()["text"]}).json()
    c.post(f"/api/audits/{r['audit_id']}/order")
    first = c.post(f"/api/audits/{r['audit_id']}/capture").json()
    assert first["invoice_status"] == "pending" and first["invoice_id"] is None
    Flaky.fail = False
    second = c.post(f"/api/audits/{r['audit_id']}/capture").json()
    assert second["invoice_status"] == "issued"
    assert [x[0] for x in FakePayPal.calls].count("capture") == 1
    assert [x[0] for x in FakePayPal.calls].count("invoice") == 1


def test_paypal_error_details_stay_on_the_server(client: TestClient) -> None:
    class Down(FakePayPal):
        def capture_order(self, order_id):
            raise PayPalError("PayPal 422 ORDER_NOT_APPROVED (debug_id secretish123)")

    c = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=Down))
    r = c.post("/api/audit", data={"text": c.get("/api/samples/C08").json()["text"]}).json()
    c.post(f"/api/audits/{r['audit_id']}/order")
    resp = c.post(f"/api/audits/{r['audit_id']}/capture")
    assert resp.status_code == 502 and "secretish123" not in resp.text


def test_store_full_of_paid_audits_says_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "STORE_MAX", 1)
    c = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=FakePayPal))
    text = c.get("/api/samples/C08").json()["text"]
    r = c.post("/api/audit", data={"text": text}).json()
    c.post(f"/api/audits/{r['audit_id']}/order")
    assert c.post("/api/audit", data={"text": text}).status_code == 503


def test_payment_attempts_are_capped(client: TestClient) -> None:
    r = _audit(client)
    codes = [client.post(f"/api/audits/{r['audit_id']}/order").status_code for _ in range(web.PAYMENT_CALLS_PER_AUDIT + 1)]
    assert codes[-1] == 429


def test_forwarded_for_uses_the_rightmost_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "CLIENT_IP_HEADER", "X-Forwarded-For")
    monkeypatch.setattr(web, "AUDITS_PER_IP_PER_HOUR", 2)
    c = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=FakePayPal))
    codes = [c.post("/api/audit", data={"text": " "}, headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).status_code
             for i in range(3)]
    assert codes[-1] == 429  # spoofed leftmost values do not reset the limit for 203.0.113.7


def test_frame_ancestors_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "FRAME_ANCESTORS", "https://huggingface.co")
    c = TestClient(web.create_app(llm_factory=FakeLLM, paypal_factory=FakePayPal))
    resp = c.get("/")
    assert "frame-ancestors https://huggingface.co" in resp.headers["content-security-policy"]
    assert "x-frame-options" not in resp.headers
