"""Audit history (AG Grid view): the server returns only the audits whose ids the browser sends, never a list of all."""

import hashlib
import sys
import uuid
from importlib import resources
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from test_web import FakeLLM, FakePayPal, _audit, client  # noqa: E402,F401
from billcheck.web import app as web  # noqa: E402

GRID_JS = "web/static/vendor/ag-grid-community.min.js"
GRID_SHA256 = "5f8ddee2e7e2d78e4005f29329404e67bba54ee6db63710b91878e81076ebc1e"  # ag-grid-community 36.2.0, npm


def _history(c: TestClient, ids: list) -> list:
    resp = c.post("/api/history", json={"audit_ids": ids})
    assert resp.status_code == 200, resp.text
    return resp.json()["audits"]


def test_history_returns_only_the_requested_audits(client: TestClient) -> None:  # noqa: F811
    mine, other = _audit(client), _audit(client)
    rows = _history(client, [mine["audit_id"]])
    assert [r["audit_id"] for r in rows] == [mine["audit_id"]]
    assert other["audit_id"] not in str(rows)
    row = rows[0]
    assert row["provider_name"] == mine["provider_name"] and row["state"] == "audited"
    assert row["total_billed"] == 4445.0 and row["total_suggested"] == 1882.38
    assert len(row["findings"]) == len(mine["findings"])
    assert {"billed_amount", "benchmark_amount", "suggested_amount", "flag_type", "cpt_code"} <= set(row["findings"][0])
    assert row["paid_amount"] is None and row["invoice_id"] is None


def test_history_shows_payment_status(client: TestClient) -> None:  # noqa: F811
    r = _audit(client)
    client.post(f"/api/audits/{r['audit_id']}/order")
    client.post(f"/api/audits/{r['audit_id']}/capture")
    row = _history(client, [r["audit_id"]])[0]
    assert row["state"] == "invoiced" and row["paid_amount"] == "1882.38"
    assert row["invoice_id"] == "INV2-X5XP-5VZX-VN62-QYR8"


def test_history_skips_unknown_ids_and_keeps_order(client: TestClient) -> None:  # noqa: F811
    a, b = _audit(client), _audit(client)
    rows = _history(client, [b["audit_id"], uuid.uuid4().hex, a["audit_id"]])
    assert [r["audit_id"] for r in rows] == [a["audit_id"], b["audit_id"]]  # oldest first
    assert _history(client, []) == []


def test_history_rejects_bad_input(client: TestClient) -> None:  # noqa: F811
    assert client.post("/api/history", json={"audit_ids": ["../etc/passwd"]}).status_code == 422
    assert client.post("/api/history", json={"audit_ids": [uuid.uuid4().hex for _ in range(51)]}).status_code == 422
    assert client.post("/api/history", json={"audit_ids": "abc"}).status_code == 422
    assert client.post("/api/history", content=b"not json", headers={"content-type": "application/json"}).status_code == 422
    assert client.get("/api/history").status_code == 405  # ids never travel in a URL


def test_grid_library_is_pinned_and_self_hosted() -> None:
    data = resources.files("billcheck").joinpath(GRID_JS).read_bytes()
    assert hashlib.sha256(data).hexdigest() == GRID_SHA256
    assert "MIT License" in resources.files("billcheck").joinpath(
        "web/static/vendor/ag-grid-community.LICENSE.txt").read_text(encoding="utf-8")
    page = resources.files("billcheck").joinpath("web/static/index.html").read_text(encoding="utf-8")
    assert '<script src="/static/vendor/ag-grid-community.min.js"></script>' in page
    assert "ag-grid" not in web.CSP  # served from this server: no new script host in the CSP
    assert "font-src 'self' data:;" in web.CSP  # the grid's icon font is inline; no outside font host


def test_grid_script_is_served(client: TestClient) -> None:  # noqa: F811
    resp = client.get("/static/vendor/ag-grid-community.min.js")
    assert resp.status_code == 200 and len(resp.content) > 1_000_000
