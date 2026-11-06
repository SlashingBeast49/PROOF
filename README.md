# PROOF

> **Document verification, without the magic-word marketing.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-21%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Core Philosophy

PROOF does not pretend to certify that a document is authentic. 

It does not claim to detect guaranteed forgeries or use hand-waving AI buzzwords. Instead, PROOF is an evidence-first document intelligence and consistency verification platform that shows:
1. **What was extracted** (and from which line and page).
2. **What rules were checked** (intra-document and cross-document).
3. **What was found** (exact matches, mathematical discrepancies, missing data).
4. **What could not be established** (gaps in evidence or unverified assertions).

Deterministic Python code evaluates comparisons wherever possible; extraction models parse text while preserving the verbatim source snippet for human auditing.

---

## 2. Key Features in V0.1

- 📂 **Multi-Document Verification**: Process single documents or multi-document procurement sets (e.g., compare an **Invoice** against an approved **Purchase Order** or **Receipt**).
- 🔍 **Structured Extraction & Classification**: Automatic classification of document categories (`Invoice`, `Purchase Order`, `Receipt`, `Contract`) with flexible pattern extraction for numbers, dates, counterparties, currencies, and itemized calculations.
- 📐 **Source Evidence Traceability**: Every extracted field and verification finding links directly to an `Evidence` record containing the source document, page number, line number, and verbatim text quote.
- 🧮 **Deterministic Intra-Document Checks**:
  - Mandatory field completeness per document type.
  - Chronological date ordering (e.g., due date on or after issue date).
  - Mathematical integrity ($\text{Subtotal} + \text{Tax} = \text{Total}$).
  - Non-negative monetary amounts.
- 🔄 **Cross-Document Consistency Checks**:
  - Purchase order identifier alignment (PO reference matching).
  - Cross-document monetary agreement and variance detection.
  - Currency harmonization (flagging international currency clashes).
  - Cross-document timeline consistency (order creation date vs billing date).
  - Counterparty and vendor name correspondence.
- 👤 **Human-in-the-Loop Review & Override**: Web UI allows reviewers to inspect extracted fields, edit/override values (e.g. correcting OCR ambiguities), and trigger instantaneous re-verification.
- 🌐 **Interactive Web Application**: Zero-build FastAPI web dashboard with drag-and-drop file upload, benchmark scenario selector, side-by-side field inspection, and findings matrix.
- 📄 **Evidence-Backed Reports**: Downloadable audit trails in structured JSON and printable, professional HTML/PDF format.
- 💻 **Flexible CLI**: Direct command-line evaluation with colored outputs and batch report generation.

---

## 3. Verification Result Categories

PROOF adheres strictly to six standardized verification categories:

| Status | Meaning | System Action |
| :--- | :--- | :--- |
| **`Match`** | Compared values agree | Evidence confirmed; logged as consistent. |
| **`Mismatch`** | Values conflict or violate arithmetic | Flagged with discrepancy delta and source evidence. |
| **`Missing`** | Mandatory information was not found | Flagged with recommended human action. |
| **`Unable to verify`** | Insufficient evidence to evaluate rule | Transparently reported without false certainty. |
| **`Needs review`** | Human interpretation required | Action recommendation provided for reviewer. |
| **`Not applicable`** | Rule does not apply to this document set | Transparently bypassed (e.g. single doc cross-check). |

> *A mismatch is not automatically evidence of fraud; it indicates a discrepancy requiring human attention.*

---

## 4. Quickstart Guide

### Prerequisites
- Python 3.10 or later
- Dependencies in `requirements.txt`

### Installation

```bash
git clone https://github.com/SlashingBeast49/PROOF.git
cd PROOF

# Install dependencies
pip install -r requirements.txt
```

### Launch the Web Application

Start the local web server:

```bash
python -m proof --serve
```

Then open your browser at **[http://localhost:8000](http://localhost:8000)**.

The web app includes:
1. **1-Click Benchmark Scenarios** to immediately test matching invoices, total mismatches, and currency clashes.
2. **File Uploader** for PDFs and text documents.
3. **Paste Text Input** for rapid testing without files.
4. **Side-by-side Field Inspector & Edit Modal** for human review.
5. **Printable HTML and JSON Export**.

---

### Command-Line Interface (CLI)

Verify a single document:
```bash
python -m proof samples/valid_invoice.txt
```

Verify cross-document consistency between an Invoice and Purchase Order:
```bash
python -m proof samples/valid_invoice.txt samples/matching_purchase_order.txt
```

Test conflict detection on mismatched documents:
```bash
python -m proof samples/valid_invoice.txt samples/mismatched_purchase_order.txt
```

Run all synthetic benchmark demonstrations:
```bash
python -m proof --demo
```

---

## 5. Python API Usage

```python
from pathlib import Path
from proof import parse_document, verify_documents, format_case_cli

# 1. Parse documents
invoice = parse_document(Path("samples/valid_invoice.txt"))
po = parse_document(Path("samples/matching_purchase_order.txt"))

# 2. Run verification
case = verify_documents([invoice, po], title="Vendor Q3 Audit")

# 3. Inspect verdict and findings
print(f"Verdict: {case.verdict}")
for finding in case.findings:
    print(f"[{finding.status.value}] {finding.title}: {finding.explanation}")

# 4. Print CLI summary
print(format_case_cli(case))
```

---

## 6. Project Architecture

PROOF is designed as a **modular monolith**:

```
PROOF/
├── proof/                  # Core package
│   ├── __init__.py         # Package exports
│   ├── models.py           # Pydantic data schemas (Document, Field, Finding, Case)
│   ├── extract.py          # Document parsing, regex key-value extraction, normalization
│   ├── rules.py            # Deterministic intra-doc and cross-doc verification rules
│   ├── engine.py           # Verification pipeline & verdict synthesizer
│   ├── report.py           # JSON, CLI, and printable HTML report generators
│   ├── app.py              # FastAPI application & REST endpoints
│   ├── static/             # Web frontend (HTML, Tailwind CSS, JS UI)
│   └── __main__.py         # CLI entrypoint (--serve, --demo, batch run)
├── samples/                # Synthetic test cases & procurement documents
│   ├── valid_invoice.txt
│   ├── matching_purchase_order.txt
│   ├── mismatched_purchase_order.txt
│   ├── incomplete_invoice.txt
│   └── sample_receipt.txt
├── tests/                  # Pytest verification suite
│   ├── test_extraction.py
│   ├── test_rules.py
│   ├── test_engine.py
│   └── test_api.py
├── SPEC.md                 # Formal Technical Specification
├── ARCHITECTURE.md         # System Architecture & Data Flow
└── requirements.txt        # Runtime dependencies
```

---

## 7. Running the Tests

PROOF maintains a comprehensive test suite covering extraction, deterministic rules, multi-document comparison, report generation, and API endpoints:

```bash
pytest
```

---

## 8. Development Roadmap

- [x] **M0: Discovery & Specification** — Completed (`SPEC.md`, `ARCHITECTURE.md`).
- [x] **M1: Repository & Environment Setup** — Completed (`proof`, `requirements.txt`).
- [x] **M2: Case Management & Multi-Doc Support** — Completed (`VerificationCase`, `Document`).
- [x] **M3: Parsing & Normalization** — Text & PDF extraction with date/amount normalization.
- [x] **M4: Structured Extraction & Evidence Tracking** — Line & page snippet evidence linkage.
- [x] **M5: Deterministic Verification Engine** — Intra-doc math/date rules & cross-doc consistency checks.
- [x] **M6: Evidence & Findings Interface** — Web application with human-in-the-loop review.
- [x] **M7: Audit Report Generation** — JSON and printable HTML reports.
- [x] **M8: Test Suite & V0.1 Release** — 21 automated tests passing.

---

## 9. Security Principles

1. **Synthetic Data**: Use only synthetic documents during development and automated testing.
2. **Deterministic Processing**: Code is strictly auditable Python; no black-box decisions.
3. **Zero Secrets in Repository**: No API keys or private tokens are stored.
4. **Local Execution**: All processing and web views run locally without transmitting documents to third-party endpoints.

---

## 10. License

PROOF is open source software released under the [Apache 2.0 / MIT License](LICENSE).
