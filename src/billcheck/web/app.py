"""BillCheck web app: upload or pick a synthetic bill → AI reads it → audit vs 2026 Medicare → pay with PayPal (sandbox).

Server-side rules (item-7 security review): the browser never sends amounts; every audit and its order live on the
server; only orders this server created are captured; the paid amount and capture id come from PayPal's capture;
one corrected invoice per audit, sent only to the payer email PayPal returns; per-IP rate limits; double-click safe.
Run: PAYPAL_CLIENT_ID=… PAYPAL_CLIENT_SECRET=… FIREWORKS_API_KEY=… uvicorn billcheck.web.app:app
"""

import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from importlib import resources
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Deque, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from ..auditor import BillAuditor
from ..explainer import explain
from ..extractor import ExtractionError, extract_bill
from ..llm import FireworksLLM, LLMError, SpendCapReached
from ..models import AuditReport, MedicalBill
from ..paypal_client import PayPalClient, PayPalError
from ..render import render_table
from .pdftext import extract_text as pdf_text

log = logging.getLogger("billcheck")

MAX_UPLOAD_BYTES = 2_000_000
AUDITS_PER_IP_PER_HOUR = int(os.environ.get("BILLCHECK_AUDITS_PER_HOUR", "20"))
STORE_TTL_S = 2 * 3600
STORE_MAX = 500
PAYMENT_CALLS_PER_AUDIT = 10
HISTORY_MAX_IDS = 50
# Behind a tunnel or proxy, set BILLCHECK_CLIENT_IP_HEADER to the header IT sets (e.g. CF-Connecting-IP).
# For X-Forwarded-For the rightmost entry is used: it is the one the nearest proxy appended (leftmost is client-made).
CLIENT_IP_HEADER = os.environ.get("BILLCHECK_CLIENT_IP_HEADER", "")
# Default: no site may frame the app. A host that shows apps in an iframe (e.g. https://huggingface.co) is named here.
FRAME_ANCESTORS = os.environ.get("BILLCHECK_FRAME_ANCESTORS", "")
CSP = ("default-src 'self'; script-src 'self' https://www.sandbox.paypal.com https://www.paypalobjects.com; "
       "connect-src 'self' https://www.sandbox.paypal.com https://*.paypal.com; "
       "frame-src https://www.sandbox.paypal.com https://*.paypal.com; img-src 'self' data: https://*.paypalobjects.com "
       "https://*.paypal.com; style-src 'self' 'unsafe-inline'; font-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors ")
DEMO_CASES = ("C08", "C01", "C04", "C10", "C11")  # sample bills a judge can try without uploading


@dataclass
class AuditRecord:
    report: AuditReport
    created: float = field(default_factory=time.time)
    order_id: str = ""
    state: str = "audited"  # audited → ordered → captured → invoiced
    payment_calls: int = 0
    capture: Dict[str, str] = field(default_factory=dict)
    invoice_id: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)


class Store:
    def __init__(self) -> None:
        self._items: Dict[str, AuditRecord] = {}
        self._lock = threading.Lock()

    def add(self, report: AuditReport) -> str:
        with self._lock:
            now = time.time()
            for key in [k for k, v in self._items.items() if now - v.created > STORE_TTL_S]:
                del self._items[key]
            if len(self._items) >= STORE_MAX:
                unpaid = [k for k, v in self._items.items() if v.state == "audited"]
                if not unpaid:
                    raise HTTPException(503, "BillCheck is busy right now. Please try again in a few minutes.")
                del self._items[min(unpaid, key=lambda k: self._items[k].created)]
            audit_id = uuid.uuid4().hex
            self._items[audit_id] = AuditRecord(report)
            return audit_id

    def find(self, audit_ids: List[str]) -> List[tuple]:
        """The (id, record) pairs for the ids given that still exist, oldest first. Never lists other audits."""
        with self._lock:
            found = [(a, self._items[a]) for a in dict.fromkeys(audit_ids) if a in self._items]
        return sorted(found, key=lambda pair: pair[1].created)

    def get(self, audit_id: str) -> AuditRecord:
        record = self._items.get(audit_id)
        if record is None:
            raise HTTPException(404, "This audit has expired. Please run it again.")
        return record


class RateLimit:
    def __init__(self, per_hour: int) -> None:
        self.per_hour, self.hits = per_hour, defaultdict(deque)  # type: int, Dict[str, Deque[float]]
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        with self._lock:
            q, now = self.hits[key], time.time()
            while q and now - q[0] > 3600:
                q.popleft()
            for stale in [k for k, v in self.hits.items() if not v and k != key]:
                del self.hits[stale]
            if len(q) >= self.per_hour:
                raise HTTPException(429, "Too many audits from this connection. Please try again later.")
            q.append(now)


def _samples() -> Dict[str, Dict[str, Any]]:
    cases = json.loads(resources.files("billcheck").joinpath("demo_cases.json").read_text(encoding="utf-8"))
    out = {}
    for c in cases:
        bill = MedicalBill(**c["bill"])
        out[c["id"]] = {"id": c["id"], "title": f"{bill.provider_name} · ${bill.total_billed:,.2f}",
                        "text": render_table(bill)}
    return out


def _bill_text(text: Optional[str], upload: Optional[UploadFile]) -> str:
    if upload is not None and upload.filename:
        raw = upload.file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "The file is larger than 2 MB.")
        if raw[:5] == b"%PDF-":
            try:
                return pdf_text(raw)
            except ValueError as exc:
                raise HTTPException(400, "This PDF could not be read. Try pasting the bill text.") from exc
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(400, "Please upload a text-based PDF or a .txt file.") from exc
    return text or ""


AuditId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]


class HistoryRequest(BaseModel):
    """The browser sends the audit ids it created; ids travel in the body, never in a URL."""
    audit_ids: List[AuditId] = Field(default_factory=list, max_length=HISTORY_MAX_IDS)


def _findings(report: AuditReport) -> List[Dict[str, Any]]:
    return [f.model_dump(include={"line_id", "description", "cpt_code", "billed_amount", "benchmark_amount",
                                  "benchmark_source", "markup_ratio", "flag_type", "explanation",
                                  "suggested_amount", "evidence"}) for f in report.findings]


def _history_row(audit_id: str, record: "AuditRecord") -> Dict[str, Any]:
    r = record.report
    return {"audit_id": audit_id, "created": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "provider_name": r.provider_name, "bill_id": r.bill_id, "state": record.state,
            "total_billed": r.total_billed, "line_sum": r.line_sum, "total_suggested": r.total_suggested,
            "potential_negotiation_difference": r.potential_negotiation_difference,
            "paid_amount": record.capture.get("amount") if record.state in ("captured", "invoiced") else None,
            "invoice_id": record.invoice_id if record.state == "invoiced" else None,
            "findings": _findings(r)}


def _public(report: AuditReport, explanation) -> Dict[str, Any]:
    return {
        "bill_id": report.bill_id, "provider_name": report.provider_name,
        "total_billed": report.total_billed, "line_sum": report.line_sum, "totals_match": report.totals_match,
        "total_suggested": report.total_suggested,
        "potential_negotiation_difference": report.potential_negotiation_difference,
        "caveat": report.caveat,
        "summary": {"text": explanation.text, "source": explanation.source},
        "findings": _findings(report),
    }


def create_app(llm_factory: Callable[[], Any] = FireworksLLM,
               paypal_factory: Callable[[], PayPalClient] = PayPalClient) -> FastAPI:
    app = FastAPI(title="BillCheck", docs_url=None, redoc_url=None, openapi_url=None)

    class Guard(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_UPLOAD_BYTES + 100_000:
                return JSONResponse({"error": "The file is larger than 2 MB."}, status_code=413)
            resp = await call_next(request)
            headers = {"Content-Security-Policy": CSP + (FRAME_ANCESTORS or "'none'"),
                       "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
            if not FRAME_ANCESTORS:
                headers["X-Frame-Options"] = "DENY"
            resp.headers.update(headers)
            return resp

    app.add_middleware(Guard)

    def client_ip(request: Request) -> str:
        if CLIENT_IP_HEADER and request.headers.get(CLIENT_IP_HEADER):
            parts = [p.strip() for p in request.headers[CLIENT_IP_HEADER].split(",") if p.strip()]
            if parts:
                return parts[-1] if CLIENT_IP_HEADER.lower() == "x-forwarded-for" else parts[0]
        return request.client.host if request.client else "unknown"

    def count_payment_call(record: "AuditRecord") -> None:
        record.payment_calls += 1
        if record.payment_calls > PAYMENT_CALLS_PER_AUDIT:
            raise HTTPException(429, "Too many payment attempts for this bill.")
    store, limiter, auditor, samples = Store(), RateLimit(AUDITS_PER_IP_PER_HOUR), BillAuditor(), _samples()
    static = resources.files("billcheck").joinpath("web/static")
    app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return static.joinpath("index.html").read_text(encoding="utf-8")

    @app.get("/api/config")
    def config() -> Dict[str, Any]:
        return {"paypal_client_id": os.environ.get("PAYPAL_CLIENT_ID", ""),
                "samples": [{"id": s["id"], "title": s["title"]} for s in samples.values()]}

    @app.get("/api/samples/{sample_id}")
    def sample(sample_id: str) -> Dict[str, str]:
        if sample_id not in samples:
            raise HTTPException(404, "Unknown sample.")
        return {"id": sample_id, "text": samples[sample_id]["text"]}

    @app.post("/api/audit")
    def audit(request: Request, text: Optional[str] = Form(None),
              file: Optional[UploadFile] = File(None)) -> Dict[str, Any]:
        limiter.check(client_ip(request))
        bill_text = _bill_text(text, file)
        try:
            llm = llm_factory()
            bill = extract_bill(bill_text, llm)
        except ExtractionError as exc:
            raise HTTPException(422, f"BillCheck could not read this bill safely: {exc}") from exc
        except (LLMError, SpendCapReached) as exc:
            raise HTTPException(503, "The AI reader is unavailable right now. Please try a sample later.") from exc
        report = auditor.audit(bill)
        audit_id = store.add(report)
        return {"audit_id": audit_id, **_public(report, explain(report, llm))}

    @app.post("/api/history")
    def history(body: HistoryRequest) -> Dict[str, Any]:
        return {"audits": [_history_row(a, rec) for a, rec in store.find(body.audit_ids)]}

    @app.post("/api/audits/{audit_id}/order")
    def create_order(audit_id: str) -> Dict[str, str]:
        record = store.get(audit_id)
        with record.lock:
            count_payment_call(record)
            if record.state != "audited":
                if record.order_id and record.state == "ordered":
                    return {"order_id": record.order_id}  # double click: same order
                raise HTTPException(409, "This bill has already been paid.")
            if record.report.total_suggested <= 0:
                raise HTTPException(400, "There is nothing to pay on this bill.")
            try:
                order = paypal_factory().create_settlement_order(record.report)
            except PayPalError as exc:
                log.warning("order failed for %s: %s", audit_id, exc)
                raise HTTPException(502, "PayPal could not create the payment. Please try again.") from exc
            record.order_id, record.state = order["id"], "ordered"
            return {"order_id": order["id"]}

    @app.post("/api/audits/{audit_id}/capture")
    def capture(audit_id: str) -> Dict[str, Any]:
        record = store.get(audit_id)
        with record.lock:
            count_payment_call(record)
            if record.state == "invoiced":
                return _receipt(record)  # double click: same receipt
            paypal = paypal_factory()
            if record.state == "ordered" and record.order_id:
                try:
                    cap = paypal.capture_order(record.order_id)
                except PayPalError as exc:
                    log.warning("capture failed for %s: %s", audit_id, exc)
                    raise HTTPException(502, "PayPal could not complete the payment. Please try again.") from exc
                record.capture, record.state = cap, "captured"  # money moved: keep the record first
                if cap["amount"] != f"{record.report.total_suggested:.2f}":
                    log.error("capture amount mismatch for %s: %s", audit_id, cap["amount"])
                    raise HTTPException(502, "PayPal captured an amount that does not match this audit.")
            if record.state != "captured":
                raise HTTPException(409, "There is no approved payment to complete for this bill.")
            if record.capture.get("amount") != f"{record.report.total_suggested:.2f}":
                raise HTTPException(502, "PayPal captured an amount that does not match this audit.")
            if record.capture.get("payer_email"):
                try:  # each step is idempotent at PayPal, so a retry resumes safely
                    record.invoice_id = record.invoice_id or paypal.create_corrected_invoice(
                        record.report, record.capture["payer_email"])
                    paypal.send_invoice(record.invoice_id)
                    paypal.record_payment(record.invoice_id, record.capture["capture_id"], record.capture["amount"])
                    record.state = "invoiced"
                except PayPalError as exc:
                    log.warning("invoice step failed for %s: %s", audit_id, exc)
            return _receipt(record)

    def _receipt(record: AuditRecord) -> Dict[str, Any]:
        issued = record.state == "invoiced"
        return {"status": "paid", "amount": record.capture.get("amount"), "capture_id": record.capture.get("capture_id"),
                "invoice_status": "issued" if issued else "pending",
                "invoice_id": record.invoice_id if issued else None,
                "invoice_url": (f"https://www.sandbox.paypal.com/invoice/p/#{record.invoice_id.replace('INV2-', '').replace('-', '')}"
                                if issued else None)}

    @app.exception_handler(HTTPException)
    def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return app


app = create_app()
