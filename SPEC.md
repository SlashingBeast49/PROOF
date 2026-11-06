# PROOF — Formal Technical Specification (SPEC.md)

**Version:** 0.1.0  
**Status:** Approved / V0.1 Baseline  
**System:** PROOF Document Intelligence & Consistency Verification  
**Author / Maintainer:** Siddharth & Engineering Team  

---

## 1. Product Scope & Core Philosophy

### 1.1 Purpose
PROOF is an evidence-first document intelligence and consistency verification platform. Its objective is to ingest uploaded documents, extract structured fields, execute deterministic comparison rules, identify discrepancies and missing information, link every finding to verifiable source evidence, and produce audit-ready verification reports.

### 1.2 The Non-Authenticity Axiom
> **PROOF shall never certify that a document is authentic.**

PROOF explicitly rejects "magic-word marketing" and black-box authenticity scores. The platform is architected around transparent reporting:
- **What was extracted:** Field values and their verbatim source snippets.
- **What was evaluated:** Explicit deterministic rules.
- **What was verified:** Values that agree across sources or arithmetic constraints.
- **What was found in conflict:** Discrepancies and variances.
- **What could not be established:** Missing information or unproven assertions.

### 1.3 Scope Inclusions and Exclusions

#### In Scope (V0.1):
- Multi-document upload and ingestion (PDF, TXT, Markdown, CSV).
- Document classification (`Invoice`, `Purchase Order`, `Receipt`, `Contract`, `Unknown`).
- Key-value extraction with verbatim line and page citation.
- Date, monetary amount, and currency normalization.
- Deterministic intra-document validation (mandatory fields, date chronology, arithmetic equality).
- Deterministic cross-document consistency checks (identifier match, total agreement, currency match, date sequence, counterparty correspondence).
- Human-in-the-loop review and field override with instantaneous re-verification.
- Downloadable JSON audit trails and printable HTML verification reports.
- Comprehensive REST API and interactive Web UI.

#### Explicitly Excluded (V0.1):
- Autonomous legal certification of document authenticity.
- Biometric verification and facial recognition.
- Direct government database lookups or registry queries.
- Distributed ledger / blockchain verification.
- Guaranteed forensic forgery detection.
- Autonomous binding approval or rejection without human agency.

---

## 2. Domain Data Entities & Schemas

### 2.1 Document
Represents an individual ingested document file or text stream.

```python
class Document:
    id: str                               # Unique document identifier (e.g., 'doc_a8f910')
    filename: str                         # Original file name or user label
    doc_type: DocumentType                # INVOICE, PURCHASE_ORDER, RECEIPT, CONTRACT, UNKNOWN
    raw_text: str                         # Extracted text content
    page_count: int                       # Total page count (default 1)
    extracted_fields: Dict[str, ExtractedField] # Keyed by normalized field key
    notes: List[str]                      # Extraction diagnostic notes
    uploaded_at: datetime                 # UTC timestamp
```

### 2.2 ExtractedField
Represents a structured data point identified within a document.

```python
class ExtractedField:
    key: str                              # Standardized key (e.g., 'subtotal', 'issue_date')
    label: str                            # Human-readable label (e.g., 'Subtotal')
    original_value: str                   # Verbatim string as found in source
    normalized_value: Any                 # Typed representation (Decimal string, ISO date string)
    confidence: float                     # Extraction confidence (0.0 to 1.0)
    extraction_method: str                # e.g., 'regex_key_value', 'human_override'
    evidence: Optional[Evidence]          # Linked source citation
    user_override: Optional[str]          # Human reviewer override value if edited
    is_reviewed: bool                     # Flag indicating human review
```

### 2.3 Evidence
Immutable reference linking an extracted field or verification finding to its source text snippet.

```python
class Evidence:
    document_id: str                      # Document identifier
    document_name: str                    # Human-readable document name
    field_name: Optional[str]             # Field key
    snippet: str                          # Verbatim line from source document
    line_number: Optional[int]            # 1-indexed line position
    page_number: Optional[int]            # 1-indexed page position
```

### 2.4 Finding
The result of an atomic verification rule execution.

```python
class Finding:
    id: str                               # Unique finding identifier
    rule_id: str                          # Unique rule identifier (e.g., 'RULE-MATH-001')
    title: str                            # Human-readable rule title
    category: str                         # Rule category classification
    status: VerificationStatus            # Standardized outcome category
    severity: Severity                    # INFO, WARNING, ERROR
    explanation: str                      # Clear factual description of finding
    evidence: List[Evidence]              # Linked source citations (intra- or cross-document)
    human_action_needed: Optional[str]    # Actionable guidance if human review is required
```

### 2.5 VerificationCase
Orchestration container tracking multiple related documents, the findings matrix, and case status.

```python
class VerificationCase:
    case_id: str                          # Unique case identifier (e.g., 'case_8b98fa2e')
    title: str                            # Case title / audit description
    created_at: datetime                  # UTC timestamp
    documents: List[Document]             # Ingested documents
    findings: List[Finding]               # Generated findings
    verdict: str                          # Case verdict
    summary_stats: Dict[str, int]         # Status count tallies
    version: int                          # Version counter for audit trail integrity
```

---

## 3. Standardized Verification Categories

Every verification check must evaluate to one of the six approved categories:

| Status | Meaning | Criterion |
| :--- | :--- | :--- |
| **`Match`** | Compared values agree | Extracted values or arithmetic identities resolve identically. |
| **`Mismatch`** | Values conflict | Extracted values differ or violate arithmetic invariants. |
| **`Missing`** | Required information absent | A mandatory field for the document type could not be extracted. |
| **`Unable to verify`** | Insufficient evidence | Supporting documents or complementary fields are missing. |
| **`Needs review`** | Ambiguity detected | Format non-standard or entity correspondence uncertain. |
| **`Not applicable`** | Rule inapplicable | Prerequisites for rule not met (e.g. cross-check on single doc). |

---

## 4. Deterministic Verification Rule Catalog

### 4.1 Intra-Document Rules

#### RULE-REQ-001: Required Fields Completeness
- **Preconditions:** Document parsed and classified.
- **Evaluation:** Evaluates presence of mandatory fields according to document type:
  - *Invoice:* `invoice_number`, `issue_date`, `due_date`, `currency`, `subtotal`, `tax`, `total`.
  - *Purchase Order:* `po_number`, `issue_date`, `total`.
  - *Receipt:* `total`, `issue_date`.
- **Status Assignment:**
  - `Match` if all mandatory fields present.
  - `Missing` if one or more fields are absent.

#### RULE-DATE-001: Chronological Date Order
- **Preconditions:** Document contains both `issue_date` and `due_date` (or `delivery_date`).
- **Evaluation:** Checks that $\text{Due Date} \ge \text{Issue Date}$.
- **Status Assignment:**
  - `Match` if due date is on or after issue date.
  - `Mismatch` if due date strictly precedes issue date.
  - `Unable to verify` if either date is missing.
  - `Needs review` if date format cannot be converted to ISO 8601.

#### RULE-MATH-001: Tax and Total Arithmetic Integrity
- **Preconditions:** `subtotal`, `tax`, and `total` extracted.
- **Evaluation:** Computes $|\text{Subtotal} + \text{Tax} - \text{Total}| \le 0.01$.
- **Status Assignment:**
  - `Match` if arithmetic identity holds within 0.01 tolerance.
  - `Mismatch` if discrepancy exceeds 0.01.
  - `Unable to verify` if any component is missing.
  - `Not applicable` if document type is Receipt with unitemized total.

#### RULE-MATH-002: Non-Negative Monetary Values
- **Preconditions:** Any monetary field present.
- **Evaluation:** Verifies value $\ge 0.00$.
- **Status Assignment:**
  - `Needs review` if negative, flagging document as a potential Credit Note or adjustment.

---

### 4.2 Cross-Document Consistency Rules

#### RULE-CROSS-001: Purchase Order Reference Identifier Match
- **Preconditions:** Two or more documents in case (typically Invoice and Purchase Order).
- **Evaluation:** Compares normalized PO reference in Invoice to PO number in Purchase Order.
- **Status Assignment:**
  - `Match` if strings match exactly (case-insensitive, whitespace-trimmed).
  - `Mismatch` if both exist but values differ.
  - `Unable to verify` if either document lacks a PO identifier.

#### RULE-CROSS-002: Cross-Document Monetary Agreement
- **Preconditions:** Total fields present on both documents.
- **Evaluation:** Compares $\text{Total}_A$ and $\text{Total}_B$.
- **Status Assignment:**
  - `Match` if $|\text{Total}_A - \text{Total}_B| \le 0.01$.
  - `Mismatch` if totals differ; outputs delta $\Delta = \text{Total}_A - \text{Total}_B$.
  - `Missing` if total missing from either document.

#### RULE-CROSS-003: Currency Harmonization
- **Preconditions:** Currency fields present on both documents.
- **Evaluation:** Compares ISO currency codes (e.g. `INR` vs `USD`).
- **Status Assignment:**
  - `Match` if currencies are identical.
  - `Mismatch` if currencies differ.
  - `Unable to verify` if currency code cannot be determined on either document.

#### RULE-CROSS-004: Cross-Document Date Timeline Sequencing
- **Preconditions:** Issue dates present on Invoice and Purchase Order.
- **Evaluation:** Verifies that Purchase Order was created prior to or on the same date as Invoice issue date ($\text{Date}_{PO} \le \text{Date}_{Invoice}$).
- **Status Assignment:**
  - `Match` if PO date precedes or matches Invoice date.
  - `Mismatch` if Invoice date strictly precedes PO creation date.
  - `Unable to verify` if issue date is missing on either document.

#### RULE-CROSS-005: Vendor Identity Correspondence
- **Preconditions:** Vendor / supplier name present on both documents.
- **Evaluation:** Compares vendor strings for substring containment or normalized equality.
- **Status Assignment:**
  - `Match` if vendor names correspond.
  - `Needs review` if names differ (e.g., subsidiary vs parent company).
  - `Unable to verify` if vendor name missing on either document.

---

## 5. Case Verdict Formulation State Machine

Case verdict is deterministically synthesized from the collective findings status distribution:

$$\text{Verdict} = \begin{cases} 
\text{INCONSISTENCIES\_FOUND} & \text{if } \text{count}(\text{Mismatch}) > 0 \\
\text{REVIEW\_REQUIRED} & \text{if } \text{count}(\text{Missing}) > 0 \lor \text{count}(\text{Needs review}) > 0 \\
\text{INSUFFICIENT\_EVIDENCE} & \text{if } \text{count}(\text{Unable to verify}) > 0 \land \text{count}(\text{Match}) = 0 \\
\text{VERIFIED\_CONSISTENT} & \text{otherwise}
\end{cases}$$

---

## 6. REST API Specification

### Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/scenarios` | List benchmark demonstration scenarios |
| `GET` | `/api/scenarios/{id}` | Execute and return a benchmark scenario |
| `POST` | `/api/cases/verify-text` | Parse raw text documents and verify |
| `POST` | `/api/cases/upload` | Multipart file upload and verification |
| `POST` | `/api/cases/override-and-reverify`| Human-in-the-loop field edit and re-verification |
| `GET` | `/api/cases/{case_id}` | Retrieve case by ID |
| `GET` | `/api/cases/{case_id}/report.html`| Generate and serve printable HTML audit report |

---

## 7. Security Principles

1. **Synthetic Data Policy:** All sample datasets and automated tests must exclusively utilize synthetic, fictional entity names and mock identifiers.
2. **Deterministic Reproducibility:** Given the identical set of document inputs, PROOF must produce the identical verification findings every time.
3. **No Unauthenticated External Side-Effects:** The verification engine runs purely in local or private tenant memory without transmitting extracted content to third-party tracking APIs.
4. **Audit Trail Immutability:** When a human override occurs, the original extracted value and source snippet are preserved alongside the overridden value, with `is_reviewed=True`.
