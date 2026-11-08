"""AI step 2: a plain-language summary of an audit, used only if every dollar figure in it is in the report."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .auditor import BANNED_WORDS
from .models import AuditReport

PROMPT = """Write 2 to 4 plain sentences for a patient about this audit of their medical bill.
Use only dollar amounts that appear in the JSON, formatted like $1,234.56. Say "negotiation reference" for flagged
lines. Never say a charge is an error, wrong, unfair or fraudulent. Do not give medical or legal advice.
Audit JSON:
"""
# Any dollar figure: "$2,400", "$2,400.00", "-$50.00", "$ 12.345", "2,400 dollars", "300 USD".
DOLLARS = re.compile(r"(-?)\$\s?(\d[\d,]*(?:\.\d+)?)(?![\d])|(-?)(\d[\d,]*(?:\.\d+)?)\s*(?:dollars|USD)\b", re.I)
MAX_CHARS = 700
UNSAFE = re.compile(r"https?:|www\.|<|>|\[|\]\(|@|\b\d{3}[-.\s]\d{3,4}[-.\s]?\d{0,4}\b", re.I)  # links, markup, emails, phones
NUMBER_WORDS = re.compile(r"\b(hundred|thousand|million)\b", re.I)


@dataclass(frozen=True)
class Explanation:
    text: str
    source: str  # "ai" or "template"
    reason: str = ""  # why the AI text was not used (empty when it was)


def _allowed_amounts(report: AuditReport) -> set:
    """Figures a patient sees on the result screen (incl. the line sum, shown when it differs from the total)."""
    values = {report.total_billed, report.line_sum, report.total_suggested, report.potential_negotiation_difference}
    for f in report.findings:
        values |= {f.billed_amount, f.suggested_amount}
        if f.benchmark_amount is not None:
            values.add(f.benchmark_amount)
    return {Decimal(f"{v:.2f}") for v in values}


def check_grounded(text: str, report: AuditReport) -> str:
    """Return "" when the text may be shown, else the reason it may not."""
    if not text.strip():
        return "empty"
    if len(text) > MAX_CHARS:
        return "too long"
    clean = "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf")
    if clean != unicodedata.normalize("NFKC", text):
        return "hidden format characters"
    text = clean
    unsafe = UNSAFE.search(text)
    if unsafe:
        return f"link, markup or contact detail: {unsafe.group(0)}"
    banned = BANNED_WORDS.search(text) or NUMBER_WORDS.search(text)
    if banned:
        return f"banned word: {banned.group(0)}"
    allowed = _allowed_amounts(report)
    for m in DOLLARS.finditer(text):
        sign, digits = (m.group(1), m.group(2)) if m.group(2) else (m.group(3), m.group(4))
        raw = digits.replace(",", "")
        try:
            value = Decimal(raw)
        except InvalidOperation:
            return f"unreadable amount: {m.group(0).strip()}"
        if sign or "." not in raw or len(raw.split(".")[1]) != 2 or value not in allowed:
            return f"amount not in the report: {m.group(0).strip()}"
    return ""


def template(report: AuditReport) -> str:
    flagged = [f for f in report.findings if f.flag_type == "ABOVE_REFERENCE"]
    if not flagged:
        return (f"No line on this bill is above the negotiation reference. Billed lines total ${report.line_sum:,.2f}; "
                "lines without a Medicare benchmark are listed as not available.")
    lines = "; ".join(f"{f.description} (${f.billed_amount:,.2f} billed, suggested ${f.suggested_amount:,.2f})"
                      for f in flagged)
    return (f"{len(flagged)} line(s) are above the negotiation reference: {lines}. "
            f"The potential negotiation difference is ${report.potential_negotiation_difference:,.2f}.")


def explain(report: AuditReport, llm) -> Explanation:
    try:
        reply = llm.chat([{"role": "user", "content": PROMPT + report.model_dump_json(exclude={"caveat"})}])
    except Exception as exc:  # any model or ledger failure: the patient still gets the checked template
        return Explanation(template(report), "template", f"model unavailable: {type(exc).__name__}")
    text = reply.text.strip()
    reason = check_grounded(text, report)
    return Explanation(text, "ai") if not reason else Explanation(template(report), "template", reason)
