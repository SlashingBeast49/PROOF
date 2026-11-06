"""PROOF — Document Intelligence and Consistency Verification Platform."""

__version__ = "0.1.0"

from proof.engine import verify_documents, verify_text_or_files
from proof.extract import extract_fields, parse_document, read_document
from proof.models import (
    Document,
    DocumentType,
    Evidence,
    ExtractedField,
    Finding,
    Severity,
    VerificationCase,
    VerificationReport,
    VerificationStatus,
)
from proof.report import (
    build_case_dict,
    build_report,
    format_case_cli,
    format_report,
    generate_html_report,
    save_case_report,
    save_report,
)
from proof.validate import Check, validate_invoice

__all__ = [
    "__version__",
    "verify_documents",
    "verify_text_or_files",
    "parse_document",
    "read_document",
    "extract_fields",
    "Document",
    "DocumentType",
    "Evidence",
    "ExtractedField",
    "Finding",
    "Severity",
    "VerificationCase",
    "VerificationReport",
    "VerificationStatus",
    "Check",
    "validate_invoice",
    "build_case_dict",
    "build_report",
    "format_case_cli",
    "format_report",
    "generate_html_report",
    "save_case_report",
    "save_report",
]
