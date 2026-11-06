"""Data models for PROOF document intelligence and verification platform.

Core Philosophy:
PROOF does not certify authenticity. It shows what it extracted,
what it checked, what it found, and what it could not establish.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    INVOICE = "Invoice"
    PURCHASE_ORDER = "Purchase Order"
    RECEIPT = "Receipt"
    CONTRACT = "Contract"
    UNKNOWN = "Unknown"


class VerificationStatus(str, Enum):
    MATCH = "Match"
    MISMATCH = "Mismatch"
    MISSING = "Missing"
    UNABLE_TO_VERIFY = "Unable to verify"
    NEEDS_REVIEW = "Needs review"
    NOT_APPLICABLE = "Not applicable"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Evidence(BaseModel):
    document_id: str
    document_name: str
    field_name: Optional[str] = None
    snippet: str
    line_number: Optional[int] = None
    page_number: Optional[int] = 1


class ExtractedField(BaseModel):
    key: str
    label: str
    original_value: str
    normalized_value: Any
    confidence: float = 1.0
    extraction_method: str = "regex"
    evidence: Optional[Evidence] = None
    user_override: Optional[str] = None
    is_reviewed: bool = False


class Document(BaseModel):
    id: str
    filename: str
    doc_type: DocumentType = DocumentType.UNKNOWN
    raw_text: str
    page_count: int = 1
    extracted_fields: Dict[str, ExtractedField] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Finding(BaseModel):
    id: str
    rule_id: str
    title: str
    category: str
    status: VerificationStatus
    severity: Severity
    explanation: str
    evidence: List[Evidence] = Field(default_factory=list)
    human_action_needed: Optional[str] = None


class VerificationCase(BaseModel):
    case_id: str
    title: str = "Verification Case"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    documents: List[Document] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    verdict: str = "PENDING"
    summary_stats: Dict[str, int] = Field(default_factory=dict)
    version: int = 1


class VerificationReport(BaseModel):
    case_id: str
    verdict: str
    created_at: datetime
    documents: List[Dict[str, Any]]
    findings: List[Finding]
    summary_stats: Dict[str, int]
    philosophy_note: str = (
        "PROOF does not certify document authenticity. "
        "Findings reflect deterministic checks across extracted information."
    )
