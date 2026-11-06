"""Extraction engine for PROOF.

Responsible for reading raw document sources (PDF, text), classifying document
type, extracting candidate fields with source evidence snippets, and normalising values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from proof.models import Document, DocumentType, Evidence, ExtractedField


# Backward compatibility dictionary
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
    """Legacy extraction container retained for backward-compatibility."""
    fields: dict[str, str]
    source_text: str
    notes: list[str]


# Field aliases for fuzzy matching
FIELD_PATTERNS: Dict[str, List[str]] = {
    "document_type": [
        r"Document\s*Type",
        r"Doc\s*Type",
        r"Document\s*Category",
    ],
    "invoice_number": [
        r"Invoice\s*(?:Number|No\.?|Num|#|ID)",
        r"Inv\s*(?:#|No\.?|Num)",
        r"Bill\s*(?:Number|No\.?|#)",
    ],
    "po_reference": [
        r"(?:Purchase\s*Order|PO|P\.O\.)\s*(?:Reference|Ref|Number|No\.?|#)",
        r"Order\s*(?:Ref|Reference|#)",
    ],
    "po_number": [
        r"(?:Purchase\s*Order|PO|P\.O\.)\s*(?:Number|No\.?|#|ID)",
        r"Order\s*Number",
    ],
    "issue_date": [
        r"Issue\s*Date",
        r"Invoice\s*Date",
        r"Order\s*Date",
        r"Date\s*of\s*Issue",
        r"PO\s*Date",
        r"Billing\s*Date",
        r"^Date",
    ],
    "due_date": [
        r"Due\s*Date",
        r"Payment\s*Due",
        r"Pay\s*By",
        r"Delivery\s*Date",
        r"Valid\s*Until",
    ],
    "vendor_name": [
        r"Vendor(?:\s*Name)?",
        r"From(?:\s*Name)?",
        r"Seller(?:\s*Name)?",
        r"Supplier(?:\s*Name)?",
        r"Billed\s*By",
        r"Issued\s*By",
        r"Merchant(?:\s*Name)?",
    ],
    "customer_name": [
        r"Customer(?:\s*Name)?",
        r"Client(?:\s*Name)?",
        r"Bill\s*To",
        r"Billed\s*To",
        r"Buyer(?:\s*Name)?",
        r"Ship\s*To",
    ],
    "currency": [
        r"Currency(?:\s*Code)?",
        r"Curr",
    ],
    "subtotal": [
        r"Sub\s*[-]?\s*Total",
        r"Net\s*Amount",
        r"Base\s*Amount",
        r"Pre-Tax\s*Total",
    ],
    "tax": [
        r"Tax(?:\s*Amount)?",
        r"VAT(?:\s*Amount)?",
        r"GST(?:\s*Amount)?",
        r"Sales\s*Tax",
    ],
    "total": [
        r"Total(?:\s*Amount)?",
        r"Grand\s*Total",
        r"Amount\s*Due",
        r"Total\s*Due",
        r"Final\s*Amount",
    ],
}


def read_document(path: Path) -> str:
    """Reads raw text from supported document formats."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        return _read_text_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        return _read_image(path)
    raise ValueError(f"Unsupported file type: {suffix or 'no file extension'}")


def _read_text_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF support needs pypdf. Run: pip install -r requirements.txt") from error

    try:
        reader = PdfReader(str(path))
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            text_parts.append(f"--- [Page {i + 1}] ---\n" + page_text)
        return "\n".join(text_parts)
    except Exception as exc:
        raise ValueError(f"Failed to read PDF '{path.name}': {exc}") from exc


def _read_image(path: Path) -> str:
    """Extract text from images using available tools, or informative placeholder."""
    # We attempt pytesseract if available, otherwise return descriptive synthetic text notice
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        img = Image.open(path)
        extracted = pytesseract.image_to_string(img)
        if extracted.strip():
            return extracted
    except Exception:
        pass

    # Safe fallback if OCR engine not bound
    return (
        f"[OCR Notice: Image file '{path.name}' uploaded. "
        f"PaddleOCR/Tesseract engine not locally configured in current runtime. "
        f"Please provide text or PDF documents for deterministic field verification.]"
    )


def detect_document_type(text: str) -> DocumentType:
    """Classifies document type based on headers, keywords, and structure."""
    lower = text.lower()

    if "purchase order" in lower or re.search(r"\bpo\s*(?:#|number|no)\b", lower):
        if "invoice" in lower and "purchase order" in lower:
            # Check which occurs as title/header
            first_lines = "\n".join(lower.splitlines()[:5])
            if "purchase order" in first_lines:
                return DocumentType.PURCHASE_ORDER
            if "invoice" in first_lines:
                return DocumentType.INVOICE
        elif "purchase order" in lower:
            return DocumentType.PURCHASE_ORDER

    if "invoice" in lower or "bill to" in lower or "amount due" in lower:
        return DocumentType.INVOICE

    if "receipt" in lower or "cashier" in lower or "payment receipt" in lower:
        return DocumentType.RECEIPT

    if "agreement" in lower or "contract" in lower or "parties" in lower:
        return DocumentType.CONTRACT

    return DocumentType.UNKNOWN


def normalize_amount(raw_value: str) -> Optional[Decimal]:
    """Cleans and parses monetary strings into normalized Decimal."""
    cleaned = re.sub(r"[^\d.,-]", "", raw_value.strip())
    # Handle European comma as decimal separator vs comma as thousands separator
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # e.g. 1.250,50
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # e.g. 1,250.50
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # e.g. 1250,50 or 1,250
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def normalize_currency(raw_value: str, context_text: str = "") -> str:
    """Normalizes currency symbols and codes to ISO 3-letter codes."""
    raw = raw_value.strip().upper()
    currency_map = {
        "$": "USD",
        "USD": "USD",
        "US$": "USD",
        "₹": "INR",
        "INR": "INR",
        "RS": "INR",
        "RS.": "INR",
        "€": "EUR",
        "EUR": "EUR",
        "£": "GBP",
        "GBP": "GBP",
        "CAD": "CAD",
        "AUD": "AUD",
        "JPY": "JPY",
        "¥": "JPY",
    }
    for symbol, code in currency_map.items():
        if symbol == raw or raw.startswith(symbol):
            return code

    # Infer from symbol in text if raw is empty
    for sym, code in [("$", "USD"), ("₹", "INR"), ("€", "EUR"), ("£", "GBP")]:
        if sym in context_text:
            return code

    return raw or "UNKNOWN"


def normalize_date(raw_value: str) -> Optional[str]:
    """Parses various date formats to ISO YYYY-MM-DD."""
    cleaned = raw_value.strip()

    # Try ISO YYYY-MM-DD directly
    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
    if iso_match:
        try:
            d = date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            return d.isoformat()
        except ValueError:
            pass

    # Try standard patterns
    formats = [
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue

    return None


def extract_fields_from_text(source_text: str, document_id: str, document_name: str) -> Tuple[Dict[str, ExtractedField], List[str]]:
    """Extracts structured fields, retaining source snippet evidence for every finding."""
    fields: Dict[str, ExtractedField] = {}
    notes: List[str] = []
    lines = source_text.splitlines()

    # Map patterns to find fields
    for field_key, patterns in FIELD_PATTERNS.items():
        found = False
        for pattern in patterns:
            # Look for lines with Label : Value or Label - Value or Label = Value
            regex = re.compile(rf"^\s*(?:[-*]\s*)?({pattern})\s*[:\-=]\s*(.+?)\s*$", re.IGNORECASE)
            for idx, line in enumerate(lines):
                m = regex.match(line)
                if m:
                    label_matched = m.group(1).strip()
                    val = m.group(2).strip()

                    # Create evidence record
                    evidence = Evidence(
                        document_id=document_id,
                        document_name=document_name,
                        field_name=field_key,
                        snippet=line.strip(),
                        line_number=idx + 1,
                        page_number=_estimate_page(lines, idx),
                    )

                    # Compute normalized value
                    norm_val: Any = val
                    if "date" in field_key:
                        norm_val = normalize_date(val) or val
                    elif field_key in {"subtotal", "tax", "total"}:
                        amt = normalize_amount(val)
                        norm_val = str(amt) if amt is not None else val
                    elif field_key == "currency":
                        norm_val = normalize_currency(val, source_text)

                    fields[field_key] = ExtractedField(
                        key=field_key,
                        label=label_matched,
                        original_value=val,
                        normalized_value=norm_val,
                        confidence=0.95,
                        extraction_method="regex_key_value",
                        evidence=evidence,
                    )
                    found = True
                    break
            if found:
                break

        if not found:
            notes.append(f"Field '{field_key}' could not be unambiguously extracted from '{document_name}'.")

    # If currency not explicitly set, try to infer from total/subtotal symbol
    if "currency" not in fields or fields["currency"].normalized_value == "UNKNOWN":
        for sym, code in [("$", "USD"), ("₹", "INR"), ("€", "EUR"), ("£", "GBP")]:
            if sym in source_text:
                evidence = Evidence(
                    document_id=document_id,
                    document_name=document_name,
                    field_name="currency",
                    snippet=f"Inferred from symbol '{sym}' present in document text",
                    line_number=None,
                    page_number=1,
                )
                fields["currency"] = ExtractedField(
                    key="currency",
                    label="Currency (Inferred)",
                    original_value=sym,
                    normalized_value=code,
                    confidence=0.85,
                    extraction_method="symbol_heuristic",
                    evidence=evidence,
                )
                break

    return fields, notes


def _estimate_page(lines: List[str], current_idx: int) -> int:
    """Estimates page number based on --- [Page X] --- markers if present."""
    current_page = 1
    for i in range(current_idx + 1):
        m = re.match(r"^---\s*\[Page\s*(\d+)\]", lines[i])
        if m:
            current_page = int(m.group(1))
    return current_page


def parse_document(source: str | Path, filename: Optional[str] = None) -> Document:
    """Parses a document file or raw text into a rich Document model."""
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"

    if isinstance(source, Path):
        filename = filename or source.name
        raw_text = read_document(source)
    else:
        filename = filename or "pasted_document.txt"
        raw_text = str(source)

    doc_type = detect_document_type(raw_text)
    fields, notes = extract_fields_from_text(raw_text, doc_id, filename)

    # Estimate page count
    page_markers = len(re.findall(r"^---\s*\[Page\s*(\d+)\]", raw_text, re.MULTILINE))
    page_count = max(1, page_markers)

    return Document(
        id=doc_id,
        filename=filename,
        doc_type=doc_type,
        raw_text=raw_text,
        page_count=page_count,
        extracted_fields=fields,
        notes=notes,
    )


# Backward compatible function
def extract_fields(source_text: str) -> ExtractionResult:
    """Legacy helper for existing tests and single-document scripts."""
    doc = parse_document(source_text, "document.txt")
    simple_fields = {k: v.original_value for k, v in doc.extracted_fields.items()}
    return ExtractionResult(fields=simple_fields, source_text=source_text, notes=doc.notes)
