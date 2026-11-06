"""FastAPI Web Application and REST API for PROOF.

Serves the interactive document verification platform, RESTful verification endpoints,
and downloadable HTML/JSON audit reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from proof.engine import verify_documents
from proof.extract import parse_document
from proof.models import Document, ExtractedField, VerificationCase
from proof.report import build_case_dict, generate_html_report, generate_pdf_report, save_case_report

app = FastAPI(
    title="PROOF Document Intelligence API",
    description="Deterministic document verification without magic-word marketing.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory case cache for the active session
CASE_STORE: Dict[str, VerificationCase] = {}

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class TextDocumentPayload(BaseModel):
    filename: str
    content: str


class VerifyTextRequest(BaseModel):
    title: Optional[str] = "Verification Case"
    documents: List[TextDocumentPayload]


class FieldOverridePayload(BaseModel):
    case_id: str
    document_id: str
    field_key: str
    new_value: str


# Benchmark Pre-packaged Scenarios for Instant Demonstration
BENCHMARK_SCENARIOS = {
    "perfect_match": {
        "title": "Scenario 1: Invoice & PO Harmonized (Pass)",
        "description": "Invoice and Purchase Order have matching PO references, matching totals (₹1,180.00), valid dates, and identical currency.",
        "documents": [
            {
                "filename": "INV-2026-001.txt",
                "content": """Document Type: Invoice
Invoice Number: INV-2026-001
PO Reference: PO-9942
Issue Date: 2026-08-20
Due Date: 2026-09-19
Vendor Name: Apex Software Solutions
Customer Name: Siddarth Tech Ltd
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1180.00""",
            },
            {
                "filename": "PO-9942.txt",
                "content": """Document Type: Purchase Order
PO Number: PO-9942
Issue Date: 2026-08-15
Delivery Date: 2026-09-15
Vendor Name: Apex Software Solutions
Customer Name: Siddarth Tech Ltd
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1180.00""",
            },
        ],
    },
    "amount_and_po_mismatch": {
        "title": "Scenario 2: Total Discrepancy & PO Conflict (Fail)",
        "description": "Invoice billed $1,350.00 against an approved PO of $1,000.00, references wrong PO number, and invoice date precedes the PO creation date.",
        "documents": [
            {
                "filename": "Supplier_Invoice_781.txt",
                "content": """Document Type: Invoice
Invoice Number: INV-781
PO Reference: PO-8800
Issue Date: 2026-08-10
Due Date: 2026-09-10
Vendor Name: Global Hardware Inc
Customer Name: Siddarth Tech Ltd
Currency: USD
Subtotal: 1200.00
Tax: 150.00
Total: 1350.00""",
            },
            {
                "filename": "Approved_PO_8801.txt",
                "content": """Document Type: Purchase Order
PO Number: PO-8801
Issue Date: 2026-08-14
Delivery Date: 2026-09-20
Vendor Name: Global Hardware Inc
Customer Name: Siddarth Tech Ltd
Currency: USD
Subtotal: 900.00
Tax: 100.00
Total: 1000.00""",
            },
        ],
    },
    "incomplete_tax_error": {
        "title": "Scenario 3: Missing Fields & Arithmetic Inconsistency",
        "description": "Invoice missing Tax and Due Date, with subtotal and total conflicting.",
        "documents": [
            {
                "filename": "Incomplete_Invoice.txt",
                "content": """Document Type: Invoice
Invoice Number: INV-990-ERR
Issue Date: 2026-08-25
Currency: USD
Subtotal: 500.00
Total: 580.00""",
            }
        ],
    },
    "currency_clash": {
        "title": "Scenario 4: Currency Clash (INR vs USD)",
        "description": "Vendor billed in USD when the procurement agreement and PO were designated in INR.",
        "documents": [
            {
                "filename": "Invoice_US.txt",
                "content": """Document Type: Invoice
Invoice Number: INV-US-102
PO Reference: PO-IN-55
Issue Date: 2026-08-22
Due Date: 2026-09-22
Vendor Name: Cloud Matrix Corp
Currency: USD
Subtotal: 5000.00
Tax: 0.00
Total: 5000.00""",
            },
            {
                "filename": "Purchase_Order_Domestic.txt",
                "content": """Document Type: Purchase Order
PO Number: PO-IN-55
Issue Date: 2026-08-10
Vendor Name: Cloud Matrix Corp
Currency: INR
Subtotal: 5000.00
Tax: 0.00
Total: 5000.00""",
            },
        ],
    },
}


@app.get("/api/health")
def health():
    return {"status": "ok", "platform": "PROOF", "version": "0.1.0"}


@app.get("/api/scenarios")
def get_scenarios():
    """Returns available benchmark demonstration scenarios."""
    return [
        {
            "id": key,
            "title": data["title"],
            "description": data["description"],
            "document_count": len(data["documents"]),
        }
        for key, data in BENCHMARK_SCENARIOS.items()
    ]


@app.get("/api/scenarios/{scenario_id}")
def load_scenario(scenario_id: str):
    """Loads and verifies a benchmark scenario immediately."""
    scenario = BENCHMARK_SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    docs: List[Document] = []
    for item in scenario["documents"]:
        doc = parse_document(item["content"], item["filename"])
        docs.append(doc)

    case = verify_documents(docs, title=scenario["title"])
    CASE_STORE[case.case_id] = case
    return build_case_dict(case)


@app.post("/api/cases/verify-text")
def verify_text(payload: VerifyTextRequest):
    """Parses raw text inputs and runs deterministic verification."""
    if not payload.documents:
        raise HTTPException(status_code=400, detail="At least one document is required")

    docs: List[Document] = []
    for item in payload.documents:
        doc = parse_document(item.content, item.filename)
        docs.append(doc)

    case = verify_documents(docs, title=payload.title or "Text Verification Case")
    CASE_STORE[case.case_id] = case
    return build_case_dict(case)


@app.post("/api/cases/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Accepts uploaded files (PDF, TXT, images) and executes verification."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    docs: List[Document] = []
    upload_dir = Path("outputs") / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    for uploaded in files:
        file_path = upload_dir / f"{uuid.uuid4().hex[:6]}_{uploaded.filename}"
        content = await uploaded.read()
        file_path.write_bytes(content)

        doc = parse_document(file_path, uploaded.filename)
        docs.append(doc)

    case = verify_documents(docs, title=f"Case ({len(docs)} documents)")
    CASE_STORE[case.case_id] = case
    return build_case_dict(case)


@app.post("/api/cases/override-and-reverify")
def override_and_reverify(payload: FieldOverridePayload):
    """Enables human review: override an extracted field value and re-verify deterministically."""
    case = CASE_STORE.get(payload.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    target_doc = next((d for d in case.documents if d.id == payload.document_id), None)
    if not target_doc:
        raise HTTPException(status_code=404, detail="Document not found in case")

    # Update or insert the field
    if payload.field_key in target_doc.extracted_fields:
        fld = target_doc.extracted_fields[payload.field_key]
        fld.original_value = payload.new_value
        fld.normalized_value = payload.new_value
        fld.user_override = payload.new_value
        fld.is_reviewed = True
    else:
        target_doc.extracted_fields[payload.field_key] = ExtractedField(
            key=payload.field_key,
            label=payload.field_key.replace("_", " ").title(),
            original_value=payload.new_value,
            normalized_value=payload.new_value,
            confidence=1.0,
            extraction_method="human_override",
            user_override=payload.new_value,
            is_reviewed=True,
        )

    # Re-run verification pipeline with edited document
    updated_case = verify_documents(case.documents, title=f"{case.title} (Human Reviewed)")
    updated_case.case_id = case.case_id  # maintain case identity
    CASE_STORE[case.case_id] = updated_case
    return build_case_dict(updated_case)


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = CASE_STORE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return build_case_dict(case)


@app.get("/api/cases/{case_id}/report.html", response_class=HTMLResponse)
def get_case_html(case_id: str):
    case = CASE_STORE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return generate_html_report(case)


@app.get("/api/cases/{case_id}/report.pdf")
def get_case_pdf(case_id: str):
    """Generates and serves a downloadable PDF audit report."""
    case = CASE_STORE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{case_id}_report.pdf"
    generate_pdf_report(case, pdf_path)

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{case_id}_verification_report.pdf",
    )


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>PROOF Web App Initializing...</h1>"


# Mount static assets directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

