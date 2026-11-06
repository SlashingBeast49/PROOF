from proof.extract import parse_document
from proof.models import DocumentType, VerificationStatus
from proof.rules import run_crossdoc_rules, run_intradoc_rules


def test_intradoc_rules_pass():
    text = """Document Type: Invoice
Invoice Number: INV-001
Issue Date: 2026-08-20
Due Date: 2026-09-20
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1180.00"""
    doc = parse_document(text, "inv.txt")
    findings = run_intradoc_rules(doc)
    statuses = {f.title: f.status for f in findings}

    assert statuses["Required Fields (Invoice)"] == VerificationStatus.MATCH
    assert statuses["Chronological Date Order"] == VerificationStatus.MATCH
    assert statuses["Tax & Total Calculation"] == VerificationStatus.MATCH


def test_intradoc_rules_date_mismatch():
    text = """Document Type: Invoice
Invoice Number: INV-001
Issue Date: 2026-09-20
Due Date: 2026-08-20
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1180.00"""
    doc = parse_document(text, "inv.txt")
    findings = run_intradoc_rules(doc)
    date_finding = next(f for f in findings if f.title == "Chronological Date Order")
    assert date_finding.status == VerificationStatus.MISMATCH


def test_intradoc_rules_total_math_discrepancy():
    text = """Document Type: Invoice
Invoice Number: INV-001
Issue Date: 2026-08-20
Due Date: 2026-09-20
Currency: INR
Subtotal: 1000.00
Tax: 180.00
Total: 1500.00"""
    doc = parse_document(text, "inv.txt")
    findings = run_intradoc_rules(doc)
    math_finding = next(f for f in findings if f.title == "Tax & Total Calculation")
    assert math_finding.status == VerificationStatus.MISMATCH


def test_crossdoc_rules_matching():
    inv_text = """Document Type: Invoice
Invoice Number: INV-001
PO Reference: PO-777
Issue Date: 2026-08-20
Currency: USD
Total: 2500.00"""
    po_text = """Document Type: Purchase Order
PO Number: PO-777
Issue Date: 2026-08-15
Currency: USD
Total: 2500.00"""
    inv = parse_document(inv_text, "inv.txt")
    po = parse_document(po_text, "po.txt")
    findings = run_crossdoc_rules([inv, po])
    statuses = {f.title: f.status for f in findings}

    assert statuses["PO Reference Identifier Match"] == VerificationStatus.MATCH
    assert statuses["Cross-Document Total Comparison"] == VerificationStatus.MATCH
    assert statuses["Currency Harmonization"] == VerificationStatus.MATCH
    assert statuses["Document Date Timeline Sequence"] == VerificationStatus.MATCH


def test_crossdoc_rules_mismatch():
    inv_text = """Document Type: Invoice
Invoice Number: INV-001
PO Reference: PO-777
Issue Date: 2026-08-10
Currency: USD
Total: 3000.00"""
    po_text = """Document Type: Purchase Order
PO Number: PO-999
Issue Date: 2026-08-15
Currency: INR
Total: 2500.00"""
    inv = parse_document(inv_text, "inv.txt")
    po = parse_document(po_text, "po.txt")
    findings = run_crossdoc_rules([inv, po])
    statuses = {f.title: f.status for f in findings}

    assert statuses["PO Reference Identifier Match"] == VerificationStatus.MISMATCH
    assert statuses["Cross-Document Total Comparison"] == VerificationStatus.MISMATCH
    assert statuses["Currency Harmonization"] == VerificationStatus.MISMATCH
    assert statuses["Document Date Timeline Sequence"] == VerificationStatus.MISMATCH
