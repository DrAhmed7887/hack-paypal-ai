"""Replay mode: recorded AI and PayPal responses, no keys, no network. The audit and the server rules run for real."""

import socket

import pytest
import requests
from fastapi.testclient import TestClient

from billcheck import replay
from billcheck.web import app as web

SAMPLES = ("C08", "C01", "C04", "C10", "C11")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BILLCHECK_REPLAY", "1")
    for name in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "FIREWORKS_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("replay mode tried to use the network")

    monkeypatch.setattr(requests.Session, "request", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    return TestClient(web.create_app())


def test_replay_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BILLCHECK_REPLAY", raising=False)
    c = TestClient(web.create_app(llm_factory=lambda: None, paypal_factory=lambda: None))
    assert "replay-banner" not in c.get("/").text and c.get("/api/config").json()["replay"] is False


def test_page_says_replay_plainly(client: TestClient) -> None:
    page = client.get("/").text
    assert 'id="replay-banner"' in page and "Replay mode: no AI model and no PayPal are called" in page
    cfg = client.get("/api/config").json()
    assert cfg["replay"] is True and cfg["paypal_client_id"] == "" and cfg["simulate_label"] == replay.SIMULATE_LABEL
    assert "Simulate sandbox payment (replay)" == cfg["simulate_label"]


@pytest.mark.parametrize("sample", SAMPLES)
def test_every_sample_audits_in_replay(client: TestClient, sample: str) -> None:
    text = client.get(f"/api/samples/{sample}").json()["text"]
    resp = client.post("/api/audit", data={"text": text})
    assert resp.status_code == 200, resp.text
    assert resp.json()["findings"]


def test_c08_full_flow_with_recorded_ids(client: TestClient) -> None:
    text = client.get("/api/samples/C08").json()["text"]
    r = client.post("/api/audit", data={"text": text}).json()
    assert r["total_suggested"] == 1882.38 and r["summary"]["source"] == "ai"  # recorded summary passed the real check
    assert client.post(f"/api/audits/{r['audit_id']}/order").status_code == 200
    rec = client.post(f"/api/audits/{r['audit_id']}/capture").json()
    assert rec["amount"] == "1882.38" and rec["capture_id"] == "7BB91146F1845732P"
    assert rec["invoice_id"] == "INV2-KLA2-KJ79-245E-WQH7" and rec["invoice_url"] is None
    assert "Replay" in rec["replay_note"]
    assert client.post(f"/api/audits/{r['audit_id']}/capture").json() == rec  # double click: same receipt


def test_other_samples_pay_their_own_server_held_amount(client: TestClient) -> None:
    paid = 0
    for sample in ("C01", "C04", "C10", "C11"):
        text = client.get(f"/api/samples/{sample}").json()["text"]
        r = client.post("/api/audit", data={"text": text}).json()
        if not 0 < r["total_suggested"] < r["line_sum"]:
            continue
        assert r["summary"]["source"] == "template"  # no recorded summary: the fixed template, not a made-up one
        client.post(f"/api/audits/{r['audit_id']}/order")
        assert client.post(f"/api/audits/{r['audit_id']}/capture").json()["amount"] == f"{r['total_suggested']:.2f}"
        paid += 1
    assert paid >= 1


def test_capture_without_order_is_still_refused(client: TestClient) -> None:
    text = client.get("/api/samples/C08").json()["text"]
    r = client.post("/api/audit", data={"text": text}).json()
    assert client.post(f"/api/audits/{r['audit_id']}/capture").status_code == 409


def test_unrecorded_bill_is_a_clear_error(client: TestClient) -> None:
    resp = client.post("/api/audit", data={"text": "Some other bill\nTOTAL CHARGES $10.00"})
    assert resp.status_code == 422 and "five sample bills" in resp.json()["error"]


def test_tampered_sample_is_refused_by_the_real_grounding_check(client: TestClient) -> None:
    text = client.get("/api/samples/C08").json()["text"].replace("$2,400.00", "$2,401.00")
    assert client.post("/api/audit", data={"text": text}).status_code == 422


def test_fixtures_load_and_the_transport_never_calls_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def boom(*a, **k):
        raise AssertionError("network call")

    monkeypatch.setattr(requests.Session, "request", boom)
    llm = replay.ReplayLLM()
    assert len(llm.bills) == 5 and "C08" in llm.summaries
    pp = replay.ReplayPayPal()
    assert pp.fx["capture_id"] == "7BB91146F1845732P"


def test_browser_style_crlf_text_matches_the_sample(client: TestClient) -> None:
    text = client.get("/api/samples/C08").json()["text"].replace("\n", "\r\n")
    assert client.post("/api/audit", data={"text": text}).status_code == 200


def test_unknown_order_and_path_are_refused_without_network() -> None:
    from billcheck.paypal_client import PayPalError

    pp = replay.ReplayPayPal()
    with pytest.raises(PayPalError):
        pp.capture_order("REPLAY-ORDER-99")
    with pytest.raises(PayPalError):
        pp._api("GET", "/v1/unknown")
    with pytest.raises(PayPalError):
        pp._call("GET", "/v1/unknown")


def test_concurrent_orders_get_distinct_ids() -> None:
    from concurrent.futures import ThreadPoolExecutor

    pp = replay.ReplayPayPal()
    body = {"purchase_units": [{"amount": {"value": "1.00"}, "reference_id": "X"}]}
    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda _: pp._api("POST", "/v2/checkout/orders", body)["id"], range(200)))
    assert len(set(ids)) == 200
