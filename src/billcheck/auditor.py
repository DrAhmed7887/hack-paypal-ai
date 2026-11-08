"""Compare medical bill lines with public 2026 Medicare prices, following docs/DECISIONS.md v1.3.

Rule IDs (R1-R6, R2a-R4a, R3b, R3c) refer to that file; E-ids refer to the evidence pack.
"""

import json
import re
from datetime import date
from importlib import resources
from typing import Any, Dict, List, Optional

from .models import AuditFinding, AuditReport, BillLineItem, MedicalBill

NOT_AVAILABLE = "Benchmark not available"
# Wording rules (DECISIONS.md): never call a price fair/standard or a charge an error, overcharge or fraud.
BANNED_WORDS = re.compile(r"\b(fair|unfair|error|overcharg\w*|fraud\w*|verified reasonable|standard|wrong\w*)\b", re.I)
CT_CODES = {"70450"}  # CT/CTA codes in the table (R3a)
ED_VISIT_CODES = {"99283", "99284", "99285"}
ROUTINE_LABS = {"80053", "85025"}  # not molecular pathology, ADLT or preventive (R4a)
PFS_COMPONENTS = {None: "global", "26": "26", "TC": "TC"}  # R1 imaging components


def load_table() -> Dict[str, Any]:
    return json.loads(resources.files("billcheck").joinpath("benchmarks.json").read_text(encoding="utf-8"))


def _money(x: float) -> float:
    return round(x + 1e-9, 2)


class BillAuditor:
    def __init__(self, table: Optional[Dict[str, Any]] = None):
        self.table = table if table is not None else load_table()

    # ---- public -------------------------------------------------------------
    def audit(self, bill: MedicalBill) -> AuditReport:
        findings = [self._audit_line(bill, n) for n in range(len(bill.line_items))]
        line_sum = _money(sum(i.billed_amount for i in bill.line_items))
        total_suggested = _money(sum(f.suggested_amount for f in findings))
        return AuditReport(
            bill_id=bill.bill_id,
            provider_name=bill.provider_name,
            total_billed=bill.total_billed,
            line_sum=line_sum,
            totals_match=abs(line_sum - bill.total_billed) < 0.005,
            total_suggested=total_suggested,
            potential_negotiation_difference=_money(line_sum - total_suggested),
            findings=findings,
        )

    # ---- per line -----------------------------------------------------------
    def _audit_line(self, bill: MedicalBill, index: int) -> AuditFinding:
        item = bill.line_items[index]
        entry = self.table["codes"].get(item.cpt_code or "")
        if entry is None:
            return self._not_available(item, "this code is not in BillCheck's public price table.")
        if bill.claim_type == "professional":
            return self._professional(bill, item, entry)
        if bill.claim_type == "lab":
            return self._lab_info(bill, item, entry)
        return self._facility(bill, index, entry)

    def _professional(self, bill: MedicalBill, item: BillLineItem, entry: Dict[str, Any]) -> AuditFinding:
        pfs = entry.get("pfs")
        if pfs is None:  # labs have no Physician Fee Schedule price
            return self._not_available(item, "Medicare does not price this test on the physician fee schedule.")
        if not self._in_release("pfs", bill.date_of_service):
            return self._not_available(item, "the date of service is outside the 2026 fee schedule.")
        component = PFS_COMPONENTS.get(item.modifier.upper() if item.modifier else None)
        rate = pfs.get(component) if component else None
        if rate is None:
            return self._not_available(item, "no Medicare price for this code with this modifier.")
        return self._compare(item, rate, "pfs", "professional", [pfs["evidence"]])

    def _facility(self, bill: MedicalBill, index: int, entry: Dict[str, Any]) -> AuditFinding:
        item = bill.line_items[index]
        code = item.cpt_code or ""
        if not self._in_release("opps", bill.date_of_service):
            return self._not_available(item, "the date of service is before the October 2026 hospital price release.")
        if code in ROUTINE_LABS:
            if all((i.cpt_code or "") in ROUTINE_LABS for i in bill.line_items):
                # R4a needs other services on the bill; R5 covers independent-lab bills only
                return self._not_available(item, "no signed rule for a hospital bill with only lab tests.")
            return self._packaged(item, entry)
        if item.modifier:
            return self._not_available(item, "hospital lines are not priced by component.")
        if code in ED_VISIT_CODES and not self._closed_world(bill, index):
            return self._not_available(
                item, "another line on this bill may change how Medicare pays the visit (for example observation hours)."
            )
        if code in CT_CODES and not self._only_ct(bill, index):
            return self._not_available(item, "Medicare pays several CT scans on one date as a single combined payment.")
        if code in ED_VISIT_CODES or code in CT_CODES:
            opps = entry["opps"]
            return self._compare(item, opps["rate"], "opps", "facility", [opps["evidence"], "E51", "E55"])
        return self._not_available(item, "Medicare's separate hospital payment for this line is not confirmed.")

    def _lab_info(self, bill: MedicalBill, item: BillLineItem, entry: Dict[str, Any]) -> AuditFinding:
        clfs = entry.get("clfs")
        if clfs is None or not self._in_release("clfs", bill.date_of_service):
            return self._not_available(item, "no 2026 Medicare lab price for this line.")
        bench = _money(clfs["rate"] * item.units)
        return AuditFinding(
            **self._base(item),
            benchmark_amount=bench,
            benchmark_source=self.table["releases"]["clfs"]["label"],
            markup_ratio=_money(item.billed_amount / bench) if bench else None,
            flag_type="INFO_ONLY",
            explanation=(
                f"For information: Medicare's 2026 lab price for this test is ${bench:,.2f}. "
                "BillCheck does not suggest a different amount for lab tests."
            ),
            suggested_amount=item.billed_amount,
            evidence=[clfs["evidence"]],
        )

    # ---- rule helpers ---------------------------------------------------------
    def _compare(self, item: BillLineItem, rate: float, release: str, kind: str, evidence: List[str]) -> AuditFinding:
        bench = _money(rate * item.units)
        mult = self.table["multipliers"][kind]
        reference = _money(bench * mult["value"])
        if bench <= 0:
            return self._not_available(item, "the Medicare price for this line is zero.")
        ratio = _money(item.billed_amount / bench)
        source = self.table["releases"][release]["label"]
        if item.billed_amount > reference:
            flag, suggested = "ABOVE_REFERENCE", min(reference, item.billed_amount)
            text = (
                f"Billed ${item.billed_amount:,.2f}, which is {ratio:.2f}x the 2026 Medicare price of ${bench:,.2f}. "
                f"Suggested negotiation amount: ${reference:,.2f} ({mult['value']}x Medicare, {mult['label']}). "
                "This is a negotiation reference, not a judgement about this charge."
            )
        else:
            flag, suggested = "NOT_FLAGGED", item.billed_amount
            text = (
                f"Not flagged by this comparison: billed ${item.billed_amount:,.2f} against a 2026 Medicare price "
                f"of ${bench:,.2f} ({ratio:.2f}x)."
            )
        return AuditFinding(
            **self._base(item),
            benchmark_amount=bench,
            benchmark_source=source,
            markup_ratio=ratio,
            flag_type=flag,
            explanation=text,
            suggested_amount=_money(suggested),
            evidence=[*evidence, *mult["evidence"]],
        )

    def _packaged(self, item: BillLineItem, entry: Dict[str, Any]) -> AuditFinding:
        return AuditFinding(
            **self._base(item),
            benchmark_amount=None,
            benchmark_source=None,
            markup_ratio=None,
            flag_type="PACKAGED",
            explanation=(
                "Medicare pays lab tests separately only when they are the only services on the claim, "
                "so on this bill they would usually be included in other payments. Not flagged."
            ),
            suggested_amount=item.billed_amount,
            evidence=[entry["opps"]["evidence"], "E50"],
        )

    def _not_available(self, item: BillLineItem, reason: str) -> AuditFinding:
        return AuditFinding(
            **self._base(item),
            benchmark_amount=None,
            benchmark_source=None,
            markup_ratio=None,
            flag_type="NOT_AVAILABLE",
            explanation=f"{NOT_AVAILABLE}: {reason}",
            suggested_amount=item.billed_amount,
            evidence=[],
        )

    def _closed_world(self, bill: MedicalBill, index: int) -> bool:
        """R3b: every other facility line is a known code (G0378 is never in the table)."""
        codes = self.table["codes"]
        return all((i.cpt_code or "") in codes for n, i in enumerate(bill.line_items) if n != index)

    def _only_ct(self, bill: MedicalBill, index: int) -> bool:
        """R3a/R3c: one CT procedure (one line, one unit), and no unknown code that could be a CT."""
        codes = self.table["codes"]
        ct = bill.line_items[index]
        others = [i for n, i in enumerate(bill.line_items) if n != index]
        return (
            ct.units == 1
            and not any((i.cpt_code or "") in CT_CODES for i in others)
            and all((i.cpt_code or "") in codes for i in others)
        )

    def _in_release(self, release: str, day: date) -> bool:
        r = self.table["releases"][release]
        return date.fromisoformat(r["from"]) <= day <= date.fromisoformat(r["to"])

    @staticmethod
    def _base(item: BillLineItem) -> Dict[str, Any]:
        return {
            "line_id": item.line_id,
            "description": item.description,
            "cpt_code": item.cpt_code,
            "billed_amount": item.billed_amount,
        }
