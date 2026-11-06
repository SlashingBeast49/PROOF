"""Deterministic verification rules for PROOF.

Rules adhere to the core philosophy:
Deterministic Python code evaluates extracted values without hallucination.
Findings reflect exact source evidence and categorized verification statuses.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from proof.models import (
    Document,
    DocumentType,
    Evidence,
    Finding,
    Severity,
    VerificationStatus,
)


def run_intradoc_rules(doc: Document) -> List[Finding]:
    """Evaluates rules within an individual document."""
    findings: List[Finding] = []

    # Rule 1: Required Fields
    findings.append(_check_required_fields(doc))

    # Rule 2: Date Sequence Order
    findings.append(_check_date_order(doc))

    # Rule 3: Amount Arithmetic (Subtotal + Tax == Total)
    findings.append(_check_total_math(doc))

    # Rule 4: Positive Monetary Amounts
    pos_finding = _check_positive_amounts(doc)
    if pos_finding:
        findings.append(pos_finding)

    return [f for f in findings if f is not None]


def _check_required_fields(doc: Document) -> Finding:
    """Checks that mandatory fields are present for the given document type."""
    if doc.doc_type == DocumentType.PURCHASE_ORDER:
        required = ["po_number", "issue_date", "total"]
        doc_label = "Purchase Order"
    elif doc.doc_type == DocumentType.RECEIPT:
        required = ["total", "issue_date"]
        doc_label = "Receipt"
    else:
        # Default to Invoice requirements
        required = ["document_type", "invoice_number", "issue_date", "due_date", "currency", "subtotal", "tax", "total"]
        doc_label = "Invoice"

    present = set(doc.extracted_fields.keys())
    missing = [req for req in required if req not in present]

    evidence_list: List[Evidence] = []
    for k in required:
        if k in doc.extracted_fields and doc.extracted_fields[k].evidence:
            evidence_list.append(doc.extracted_fields[k].evidence)

    if missing:
        return Finding(
            id=f"req_fields_{doc.id}",
            rule_id="RULE-REQ-001",
            title=f"Required Fields ({doc_label})",
            category="Document Completeness",
            status=VerificationStatus.MISSING,
            severity=Severity.ERROR,
            explanation=f"Document '{doc.filename}' is missing {len(missing)} required field(s): {', '.join(missing)}.",
            evidence=evidence_list,
            human_action_needed=f"Verify if the document image contains {', '.join(missing)} or provide an updated copy.",
        )

    return Finding(
        id=f"req_fields_{doc.id}",
        rule_id="RULE-REQ-001",
        title=f"Required Fields ({doc_label})",
        category="Document Completeness",
        status=VerificationStatus.MATCH,
        severity=Severity.INFO,
        explanation=f"All {len(required)} expected fields for {doc_label} were found in '{doc.filename}'.",
        evidence=evidence_list,
    )


def _check_date_order(doc: Document) -> Finding:
    """Ensures due_date / delivery_date >= issue_date."""
    fields = doc.extracted_fields
    issue_field = fields.get("issue_date")
    due_field = fields.get("due_date")

    evidence_list: List[Evidence] = []
    if issue_field and issue_field.evidence:
        evidence_list.append(issue_field.evidence)
    if due_field and due_field.evidence:
        evidence_list.append(due_field.evidence)

    if not issue_field or not due_field:
        return Finding(
            id=f"date_order_{doc.id}",
            rule_id="RULE-DATE-001",
            title="Chronological Date Order",
            category="Intra-Document Logic",
            status=VerificationStatus.UNABLE_TO_VERIFY,
            severity=Severity.WARNING,
            explanation=f"Cannot verify chronological date order in '{doc.filename}' because issue_date or due_date is absent.",
            evidence=evidence_list,
            human_action_needed="Inspect document to confirm payment terms or expiry date.",
        )

    try:
        issue_d = date.fromisoformat(str(issue_field.normalized_value))
        due_d = date.fromisoformat(str(due_field.normalized_value))
    except (ValueError, TypeError):
        return Finding(
            id=f"date_order_{doc.id}",
            rule_id="RULE-DATE-001",
            title="Chronological Date Order",
            category="Intra-Document Logic",
            status=VerificationStatus.NEEDS_REVIEW,
            severity=Severity.WARNING,
            explanation=f"Dates in '{doc.filename}' could not be parsed to ISO YYYY-MM-DD (Issue: '{issue_field.original_value}', Due: '{due_field.original_value}').",
            evidence=evidence_list,
            human_action_needed="Review source date formats manually.",
        )

    if due_d >= issue_d:
        days_diff = (due_d - issue_d).days
        return Finding(
            id=f"date_order_{doc.id}",
            rule_id="RULE-DATE-001",
            title="Chronological Date Order",
            category="Intra-Document Logic",
            status=VerificationStatus.MATCH,
            severity=Severity.INFO,
            explanation=f"Due Date ({due_d}) is on or after Issue Date ({issue_d}) with a payment window of {days_diff} day(s).",
            evidence=evidence_list,
        )

    return Finding(
        id=f"date_order_{doc.id}",
        rule_id="RULE-DATE-001",
        title="Chronological Date Order",
        category="Intra-Document Logic",
        status=VerificationStatus.MISMATCH,
        severity=Severity.ERROR,
        explanation=f"Due Date ({due_d}) precedes Issue Date ({issue_d}) in '{doc.filename}'.",
        evidence=evidence_list,
        human_action_needed="Confirm whether invoice date or due date was entered backwards.",
    )


def _check_total_math(doc: Document) -> Finding:
    """Verifies that subtotal + tax == total within 0.01 tolerance."""
    fields = doc.extracted_fields
    sub_field = fields.get("subtotal")
    tax_field = fields.get("tax")
    tot_field = fields.get("total")

    evidence_list: List[Evidence] = []
    for fld in (sub_field, tax_field, tot_field):
        if fld and fld.evidence:
            evidence_list.append(fld.evidence)

    if not sub_field or not tax_field or not tot_field:
        # If total exists alone on a receipt, that's normal for receipts
        if doc.doc_type == DocumentType.RECEIPT and tot_field:
            return Finding(
                id=f"total_math_{doc.id}",
                rule_id="RULE-MATH-001",
                title="Tax & Total Calculation",
                category="Mathematical Integrity",
                status=VerificationStatus.NOT_APPLICABLE,
                severity=Severity.INFO,
                explanation="Receipt specifies total amount; itemized tax calculation not required.",
                evidence=evidence_list,
            )

        missing = [name for name, f in [("subtotal", sub_field), ("tax", tax_field), ("total", tot_field)] if not f]
        return Finding(
            id=f"total_math_{doc.id}",
            rule_id="RULE-MATH-001",
            title="Tax & Total Calculation",
            category="Mathematical Integrity",
            status=VerificationStatus.UNABLE_TO_VERIFY,
            severity=Severity.WARNING,
            explanation=f"Cannot calculate arithmetic consistency because {', '.join(missing)} is missing in '{doc.filename}'.",
            evidence=evidence_list,
            human_action_needed="Check if tax or subtotal lines were omitted in source text.",
        )

    try:
        subtotal = Decimal(str(sub_field.normalized_value))
        tax = Decimal(str(tax_field.normalized_value))
        total = Decimal(str(tot_field.normalized_value))
    except (InvalidOperation, TypeError, ValueError):
        return Finding(
            id=f"total_math_{doc.id}",
            rule_id="RULE-MATH-001",
            title="Tax & Total Calculation",
            category="Mathematical Integrity",
            status=VerificationStatus.NEEDS_REVIEW,
            severity=Severity.WARNING,
            explanation=f"Numeric amounts could not be accurately converted to Decimal for '{doc.filename}'.",
            evidence=evidence_list,
            human_action_needed="Verify numeric amounts manually.",
        )

    expected_total = subtotal + tax
    diff = abs(expected_total - total)

    if diff <= Decimal("0.01"):
        return Finding(
            id=f"total_math_{doc.id}",
            rule_id="RULE-MATH-001",
            title="Tax & Total Calculation",
            category="Mathematical Integrity",
            status=VerificationStatus.MATCH,
            severity=Severity.INFO,
            explanation=f"Arithmetic verified: Subtotal ({subtotal:.2f}) + Tax ({tax:.2f}) = Stated Total ({total:.2f}).",
            evidence=evidence_list,
        )

    return Finding(
        id=f"total_math_{doc.id}",
        rule_id="RULE-MATH-001",
        title="Tax & Total Calculation",
        category="Mathematical Integrity",
        status=VerificationStatus.MISMATCH,
        severity=Severity.ERROR,
        explanation=(
            f"Arithmetic discrepancy in '{doc.filename}': "
            f"Subtotal ({subtotal:.2f}) + Tax ({tax:.2f}) yields {expected_total:.2f}, "
            f"which differs from stated Total ({total:.2f}) by {diff:.2f}."
        ),
        evidence=evidence_list,
        human_action_needed="Review invoice line items and discount/fee lines not captured in extraction.",
    )


def _check_positive_amounts(doc: Document) -> Optional[Finding]:
    """Ensures monetary values are non-negative."""
    for key in ("subtotal", "tax", "total"):
        fld = doc.extracted_fields.get(key)
        if fld:
            try:
                val = Decimal(str(fld.normalized_value))
                if val < 0:
                    ev = [fld.evidence] if fld.evidence else []
                    return Finding(
                        id=f"neg_amount_{doc.id}_{key}",
                        rule_id="RULE-MATH-002",
                        title="Negative Monetary Value",
                        category="Mathematical Integrity",
                        status=VerificationStatus.NEEDS_REVIEW,
                        severity=Severity.WARNING,
                        explanation=f"Field '{key}' has a negative amount ({val:.2f}) in '{doc.filename}'.",
                        evidence=ev,
                        human_action_needed="Check if this document is a Credit Note or refund.",
                    )
            except Exception:
                pass
    return None


def run_crossdoc_rules(docs: List[Document]) -> List[Finding]:
    """Runs deterministic consistency rules across multiple uploaded documents."""
    findings: List[Finding] = []

    if len(docs) < 2:
        findings.append(
            Finding(
                id="crossdoc_single_doc",
                rule_id="RULE-CROSS-000",
                title="Cross-Document Verification",
                category="Cross-Document Consistency",
                status=VerificationStatus.NOT_APPLICABLE,
                severity=Severity.INFO,
                explanation="Only one document provided. Upload 2 or more related documents (e.g., Invoice and Purchase Order) to run cross-document consistency checks.",
                evidence=[],
            )
        )
        return findings

    # Identify invoices and purchase orders
    invoices = [d for d in docs if d.doc_type == DocumentType.INVOICE]
    pos = [d for d in docs if d.doc_type == DocumentType.PURCHASE_ORDER]

    # If types aren't clearly differentiated, compare document 0 and document 1
    doc_a = invoices[0] if invoices else docs[0]
    doc_b = pos[0] if pos else docs[1]

    # Cross Check 1: PO Reference Match
    findings.append(_check_cross_po_reference(doc_a, doc_b))

    # Cross Check 2: Total Amount Agreement
    findings.append(_check_cross_total(doc_a, doc_b))

    # Cross Check 3: Currency Alignment
    findings.append(_check_cross_currency(doc_a, doc_b))

    # Cross Check 4: Issue / Order Date Sequencing
    findings.append(_check_cross_dates(doc_a, doc_b))

    # Cross Check 5: Counterparty / Vendor Match
    findings.append(_check_cross_vendor(doc_a, doc_b))

    return [f for f in findings if f is not None]


def _check_cross_po_reference(doc_a: Document, doc_b: Document) -> Finding:
    """Checks if the PO reference in an invoice matches the PO document number."""
    f_a = doc_a.extracted_fields.get("po_reference") or doc_a.extracted_fields.get("po_number")
    f_b = doc_b.extracted_fields.get("po_number") or doc_b.extracted_fields.get("po_reference")

    ev: List[Evidence] = []
    if f_a and f_a.evidence:
        ev.append(f_a.evidence)
    if f_b and f_b.evidence:
        ev.append(f_b.evidence)

    if not f_a or not f_b:
        return Finding(
            id=f"cross_po_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-001",
            title="PO Reference Identifier Match",
            category="Cross-Document Consistency",
            status=VerificationStatus.UNABLE_TO_VERIFY,
            severity=Severity.WARNING,
            explanation=f"Cannot cross-verify PO reference between '{doc_a.filename}' and '{doc_b.filename}' because one or both lack a PO identifier.",
            evidence=ev,
            human_action_needed="Confirm whether these documents originate from the same procurement order.",
        )

    val_a = str(f_a.normalized_value).strip().upper()
    val_b = str(f_b.normalized_value).strip().upper()

    if val_a == val_b:
        return Finding(
            id=f"cross_po_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-001",
            title="PO Reference Identifier Match",
            category="Cross-Document Consistency",
            status=VerificationStatus.MATCH,
            severity=Severity.INFO,
            explanation=f"PO identifier '{val_a}' in '{doc_a.filename}' matches PO identifier '{val_b}' in '{doc_b.filename}'.",
            evidence=ev,
        )

    return Finding(
        id=f"cross_po_{doc_a.id}_{doc_b.id}",
        rule_id="RULE-CROSS-001",
        title="PO Reference Identifier Match",
        category="Cross-Document Consistency",
        status=VerificationStatus.MISMATCH,
        severity=Severity.ERROR,
        explanation=f"PO identifier conflict: '{doc_a.filename}' states '{val_a}', whereas '{doc_b.filename}' states '{val_b}'.",
        evidence=ev,
        human_action_needed="Verify whether the invoice was billed against the wrong purchase order.",
    )


def _check_cross_total(doc_a: Document, doc_b: Document) -> Finding:
    """Verifies that the total billed matches the approved order amount."""
    tot_a = doc_a.extracted_fields.get("total")
    tot_b = doc_b.extracted_fields.get("total")

    ev: List[Evidence] = []
    if tot_a and tot_a.evidence:
        ev.append(tot_a.evidence)
    if tot_b and tot_b.evidence:
        ev.append(tot_b.evidence)

    if not tot_a or not tot_b:
        return Finding(
            id=f"cross_tot_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-002",
            title="Cross-Document Total Comparison",
            category="Cross-Document Consistency",
            status=VerificationStatus.MISSING,
            severity=Severity.WARNING,
            explanation=f"Cannot compare monetary totals between '{doc_a.filename}' and '{doc_b.filename}' because total is missing on one document.",
            evidence=ev,
            human_action_needed="Extract or input the missing total amount.",
        )

    try:
        amt_a = Decimal(str(tot_a.normalized_value))
        amt_b = Decimal(str(tot_b.normalized_value))
    except (InvalidOperation, TypeError):
        return Finding(
            id=f"cross_tot_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-002",
            title="Cross-Document Total Comparison",
            category="Cross-Document Consistency",
            status=VerificationStatus.NEEDS_REVIEW,
            severity=Severity.WARNING,
            explanation=f"Could not convert totals to numeric decimals for comparison ('{tot_a.original_value}' vs '{tot_b.original_value}').",
            evidence=ev,
            human_action_needed="Review amounts manually.",
        )

    diff = amt_a - amt_b
    if abs(diff) <= Decimal("0.01"):
        return Finding(
            id=f"cross_tot_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-002",
            title="Cross-Document Total Comparison",
            category="Cross-Document Consistency",
            status=VerificationStatus.MATCH,
            severity=Severity.INFO,
            explanation=f"Total amount agrees across documents: {amt_a:.2f} in '{doc_a.filename}' matches {amt_b:.2f} in '{doc_b.filename}'.",
            evidence=ev,
        )

    severity = Severity.ERROR if abs(diff) > 0 else Severity.INFO
    return Finding(
        id=f"cross_tot_{doc_a.id}_{doc_b.id}",
        rule_id="RULE-CROSS-002",
        title="Cross-Document Total Comparison",
        category="Cross-Document Consistency",
        status=VerificationStatus.MISMATCH,
        severity=severity,
        explanation=(
            f"Amount variance detected: '{doc_a.filename}' states {amt_a:.2f}, "
            f"while '{doc_b.filename}' states {amt_b:.2f}. Discrepancy: {diff:+.2f}."
        ),
        evidence=ev,
        human_action_needed="Determine whether price increases, shipping fees, or partial billing account for the variance.",
    )


def _check_cross_currency(doc_a: Document, doc_b: Document) -> Finding:
    """Verifies both documents use the identical currency."""
    curr_a = doc_a.extracted_fields.get("currency")
    curr_b = doc_b.extracted_fields.get("currency")

    ev: List[Evidence] = []
    if curr_a and curr_a.evidence:
        ev.append(curr_a.evidence)
    if curr_b and curr_b.evidence:
        ev.append(curr_b.evidence)

    if not curr_a or not curr_b:
        return Finding(
            id=f"cross_curr_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-003",
            title="Currency Harmonization",
            category="Cross-Document Consistency",
            status=VerificationStatus.UNABLE_TO_VERIFY,
            severity=Severity.WARNING,
            explanation=f"One or both documents do not specify a currency code or symbol.",
            evidence=ev,
            human_action_needed="Specify the billing currency for both documents.",
        )

    c_a = str(curr_a.normalized_value).upper()
    c_b = str(curr_b.normalized_value).upper()

    if c_a == c_b and c_a != "UNKNOWN":
        return Finding(
            id=f"cross_curr_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-003",
            title="Currency Harmonization",
            category="Cross-Document Consistency",
            status=VerificationStatus.MATCH,
            severity=Severity.INFO,
            explanation=f"Currency matches: Both '{doc_a.filename}' and '{doc_b.filename}' use {c_a}.",
            evidence=ev,
        )

    return Finding(
        id=f"cross_curr_{doc_a.id}_{doc_b.id}",
        rule_id="RULE-CROSS-003",
        title="Currency Harmonization",
        category="Cross-Document Consistency",
        status=VerificationStatus.MISMATCH,
        severity=Severity.ERROR,
        explanation=f"Currency conflict: '{doc_a.filename}' is in {c_a}, whereas '{doc_b.filename}' is in {c_b}.",
        evidence=ev,
        human_action_needed="Confirm if an international exchange rate or separate transaction was involved.",
    )


def _check_cross_dates(doc_a: Document, doc_b: Document) -> Finding:
    """Validates that PO date precedes or matches Invoice date."""
    date_a = doc_a.extracted_fields.get("issue_date")
    date_b = doc_b.extracted_fields.get("issue_date")

    ev: List[Evidence] = []
    if date_a and date_a.evidence:
        ev.append(date_a.evidence)
    if date_b and date_b.evidence:
        ev.append(date_b.evidence)

    if not date_a or not date_b:
        return Finding(
            id=f"cross_dates_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-004",
            title="Document Date Timeline Sequence",
            category="Cross-Document Consistency",
            status=VerificationStatus.UNABLE_TO_VERIFY,
            severity=Severity.INFO,
            explanation="Cannot establish relative timeline because one of the dates is missing.",
            evidence=ev,
        )

    try:
        d_a = date.fromisoformat(str(date_a.normalized_value))
        d_b = date.fromisoformat(str(date_b.normalized_value))
    except (ValueError, TypeError):
        return Finding(
            id=f"cross_dates_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-004",
            title="Document Date Timeline Sequence",
            category="Cross-Document Consistency",
            status=VerificationStatus.NEEDS_REVIEW,
            severity=Severity.WARNING,
            explanation="Could not parse cross-document dates into calendar timeline.",
            evidence=ev,
        )

    # If doc_a is Invoice and doc_b is PO, PO date should be <= Invoice date
    if doc_a.doc_type == DocumentType.INVOICE and doc_b.doc_type == DocumentType.PURCHASE_ORDER:
        inv_d, po_d = d_a, d_b
        if po_d <= inv_d:
            return Finding(
                id=f"cross_dates_{doc_a.id}_{doc_b.id}",
                rule_id="RULE-CROSS-004",
                title="Document Date Timeline Sequence",
                category="Cross-Document Consistency",
                status=VerificationStatus.MATCH,
                severity=Severity.INFO,
                explanation=f"Timeline valid: Purchase order date ({po_d}) is prior to or on invoice date ({inv_d}).",
                evidence=ev,
            )
        else:
            return Finding(
                id=f"cross_dates_{doc_a.id}_{doc_b.id}",
                rule_id="RULE-CROSS-004",
                title="Document Date Timeline Sequence",
                category="Cross-Document Consistency",
                status=VerificationStatus.MISMATCH,
                severity=Severity.ERROR,
                explanation=f"Chronological anomaly: Invoice issue date ({inv_d}) occurs before the Purchase Order creation date ({po_d}).",
                evidence=ev,
                human_action_needed="Verify whether invoice was backdated or PO was generated post-facto.",
            )

    return Finding(
        id=f"cross_dates_{doc_a.id}_{doc_b.id}",
        rule_id="RULE-CROSS-004",
        title="Document Date Timeline Sequence",
        category="Cross-Document Consistency",
        status=VerificationStatus.MATCH,
        severity=Severity.INFO,
        explanation=f"Dates recorded: '{doc_a.filename}' ({d_a}), '{doc_b.filename}' ({d_b}).",
        evidence=ev,
    )


def _check_cross_vendor(doc_a: Document, doc_b: Document) -> Finding:
    """Checks vendor / seller counterparty name alignment."""
    v_a = doc_a.extracted_fields.get("vendor_name")
    v_b = doc_b.extracted_fields.get("vendor_name")

    ev: List[Evidence] = []
    if v_a and v_a.evidence:
        ev.append(v_a.evidence)
    if v_b and v_b.evidence:
        ev.append(v_b.evidence)

    if not v_a or not v_b:
        return Finding(
            id=f"cross_vendor_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-005",
            title="Vendor Identity Consistency",
            category="Cross-Document Consistency",
            status=VerificationStatus.UNABLE_TO_VERIFY,
            severity=Severity.INFO,
            explanation="Vendor names are not present on both documents.",
            evidence=ev,
        )

    name_a = str(v_a.normalized_value).strip().lower()
    name_b = str(v_b.normalized_value).strip().lower()

    if name_a == name_b or name_a in name_b or name_b in name_a:
        return Finding(
            id=f"cross_vendor_{doc_a.id}_{doc_b.id}",
            rule_id="RULE-CROSS-005",
            title="Vendor Identity Consistency",
            category="Cross-Document Consistency",
            status=VerificationStatus.MATCH,
            severity=Severity.INFO,
            explanation=f"Vendor names align: '{v_a.original_value}' corresponds to '{v_b.original_value}'.",
            evidence=ev,
        )

    return Finding(
        id=f"cross_vendor_{doc_a.id}_{doc_b.id}",
        rule_id="RULE-CROSS-005",
        title="Vendor Identity Consistency",
        category="Cross-Document Consistency",
        status=VerificationStatus.NEEDS_REVIEW,
        severity=Severity.WARNING,
        explanation=f"Vendor name difference: '{v_a.original_value}' vs '{v_b.original_value}'.",
        evidence=ev,
        human_action_needed="Confirm whether these represent subsidiaries or DBAs of the same supplier.",
    )
