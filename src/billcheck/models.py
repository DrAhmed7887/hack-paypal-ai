"""Data models for BillCheck medical bill auditing and settlement."""

from datetime import date
from typing import List, Literal, Optional

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f<>]")


def _clean_text(value: str) -> str:
    """Free text from a bill or a model: no control characters or angle brackets, short."""
    return CONTROL_CHARS.sub(" ", value).strip()[:120]

ClaimType = Literal["professional", "facility", "lab"]
FlagType = Literal["ABOVE_REFERENCE", "NOT_FLAGGED", "PACKAGED", "INFO_ONLY", "NOT_AVAILABLE"]


class BillLineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_id: str
    description: str
    cpt_code: Optional[str] = None
    modifier: Optional[str] = None  # imaging component: "26" (professional) or "TC" (technical)
    units: int = Field(1, ge=1, le=100)
    billed_amount: float = Field(..., ge=0.0, le=10_000_000, allow_inf_nan=False)

    @field_validator("description", "line_id")
    @classmethod
    def _clean(cls, v: str) -> str:
        return _clean_text(v)


class MedicalBill(BaseModel):
    model_config = ConfigDict(frozen=True)

    bill_id: str
    provider_name: str
    claim_type: ClaimType
    date_of_service: date
    line_items: List[BillLineItem] = Field(..., min_length=1)
    total_billed: float = Field(..., ge=0.0, le=10_000_000, allow_inf_nan=False)

    @field_validator("bill_id", "provider_name")
    @classmethod
    def _clean(cls, v: str) -> str:
        return _clean_text(v)


class AuditFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_id: str
    description: str
    cpt_code: Optional[str] = None
    billed_amount: float
    benchmark_amount: Optional[float]  # Medicare reference x units; None when not available
    benchmark_source: Optional[str]
    markup_ratio: Optional[float]  # billed / benchmark; None when not available
    flag_type: FlagType
    explanation: str
    suggested_amount: float
    evidence: List[str]


class AuditReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    bill_id: str
    provider_name: str
    total_billed: float
    line_sum: float
    totals_match: bool
    total_suggested: float
    potential_negotiation_difference: float
    findings: List[AuditFinding]
    caveat: str = (
        "A negotiation reference based on public 2026 Medicare prices and the average that private "
        "health plans paid relative to Medicare (RAND, 2022). It is not a judgement about any charge."
    )
