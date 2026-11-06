from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


SUPPORTED_LABELS = {
    "document_type": "Document Type",
    "invoice_number": "Invoice Number",
    "issue_date": "Issue Date",
    "due_date": "Due Date",
    "currency": "Currency",
    "subtotal": "Subtotal",
    "tax": "Tax",
    "total": "Total",
}


@dataclass
class ExtractionResult:
    fields: dict[str, str]
    source_text: str
    notes: list[str]


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _read_text_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        raise ValueError("Images need OCR, which is deliberately outside PROOF V0.1.")
    raise ValueError(f"Unsupported file type: {suffix or 'no file extension'}")


def _read_text_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF support needs pypdf. Run: pip install -r requirements.txt") from error

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_fields(source_text: str) -> ExtractionResult:
    fields: dict[str, str] = {}
    notes: list[str] = []

    for field_name, label in SUPPORTED_LABELS.items():
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", source_text)
        if match:
            fields[field_name] = match.group(1).strip()
        else:
            notes.append(f"Could not find the '{label}' label.")

    return ExtractionResult(fields=fields, source_text=source_text, notes=notes)
