"""Render a synthetic MedicalBill as plain bill text, in two layouts, for the demo and the G1 evaluation."""

from .models import MedicalBill

HEADERS = {
    "facility": "HOSPITAL OUTPATIENT STATEMENT",
    "professional": "PHYSICIAN SERVICES STATEMENT",
    "lab": "LABORATORY SERVICES STATEMENT",
}


def _money(x: float) -> str:
    return f"${x:,.2f}"


def render_table(bill: MedicalBill) -> str:
    """Layout A: a column table, US date format."""
    d = bill.date_of_service
    rows = [
        f"{bill.provider_name.upper()} - {HEADERS[bill.claim_type]}",
        f"Statement: {bill.bill_id}   Date of service: {d.month:02d}/{d.day:02d}/{d.year}",
        "LINE  CODE   MOD  DESCRIPTION                 UNITS      CHARGE",
    ]
    for i in bill.line_items:
        rows.append(f"{i.line_id:<5} {(i.cpt_code or '-'):<6} {(i.modifier or ''):<4} "
                    f"{i.description[:26]:<26} {i.units:>5} {_money(i.billed_amount):>11}")
    rows.append(f"TOTAL CHARGES {_money(bill.total_billed):>52}")
    return "\n".join(rows) + "\n"


def render_letter(bill: MedicalBill) -> str:
    """Layout B: one service per sentence-like row, written-out month, code-modifier joined."""
    d = bill.date_of_service
    rows = [
        f"{bill.provider_name}",
        f"{HEADERS[bill.claim_type].title()} | Account {bill.bill_id}",
        f"Services on {d.strftime('%B')} {d.day}, {d.year}:",
    ]
    for i in bill.line_items:
        code = f"CPT {i.cpt_code}{'-' + i.modifier if i.modifier else ''}" if i.cpt_code else "No code"
        qty = f" Qty {i.units}" if i.units > 1 else ""
        rows.append(f"  {i.line_id}. {i.description} ({code}){qty} .......... {_money(i.billed_amount)}")
    rows.append(f"Amount due: {_money(bill.total_billed)}")
    return "\n".join(rows) + "\n"


LAYOUTS = {"table": render_table, "letter": render_letter}
