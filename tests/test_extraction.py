from pathlib import Path
from proof.extract import (
    detect_document_type,
    extract_fields,
    extract_fields_from_text,
    normalize_amount,
    normalize_currency,
    normalize_date,
    parse_document,
)
from proof.models import DocumentType


def test_normalize_date():
    assert normalize_date("2026-08-20") == "2026-08-20"
    assert normalize_date("20/08/2026") == "2026-08-20"
    assert normalize_date("08/20/2026") == "2026-08-20"
    assert normalize_date("August 20, 2026") == "2026-08-20"
    assert normalize_date("invalid-date") is None


def test_normalize_amount():
    assert str(normalize_amount("1000.00")) == "1000.00"
    assert str(normalize_amount("$ 1,250.50")) == "1250.50"
    assert str(normalize_amount("₹ 1,180.00")) == "1180.00"
    assert str(normalize_amount("1.250,50")) == "1250.50"
    assert normalize_amount("N/A") is None


def test_normalize_currency():
    assert normalize_currency("INR") == "INR"
    assert normalize_currency("₹") == "INR"
    assert normalize_currency("$") == "USD"
    assert normalize_currency("USD") == "USD"
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("£") == "GBP"


def test_detect_document_type():
    assert detect_document_type("Document Type: Invoice\nInvoice Number: 123") == DocumentType.INVOICE
    assert detect_document_type("Purchase Order\nPO Number: PO-9942") == DocumentType.PURCHASE_ORDER
    assert detect_document_type("Receipt\nCashier: 04") == DocumentType.RECEIPT


def test_parse_document_extraction():
    content = """Document Type: Invoice
Invoice Number: INV-2026-999
Issue Date: 2026-08-20
Due Date: 2026-09-20
Currency: USD
Subtotal: 500.00
Tax: 50.00
Total: 550.00"""
    doc = parse_document(content, "test_inv.txt")
    assert doc.doc_type == DocumentType.INVOICE
    assert doc.extracted_fields["invoice_number"].normalized_value == "INV-2026-999"
    assert doc.extracted_fields["subtotal"].normalized_value == "500.00"
    assert doc.extracted_fields["tax"].normalized_value == "50.00"
    assert doc.extracted_fields["total"].normalized_value == "550.00"
    assert doc.extracted_fields["currency"].normalized_value == "USD"
    assert doc.extracted_fields["invoice_number"].evidence is not None


def test_legacy_extract_fields_compatibility():
    content = "Document Type: Invoice\nInvoice Number: INV-001\nTotal: 100.00"
    res = extract_fields(content)
    assert res.fields["invoice_number"] == "INV-001"
    assert res.fields["total"] == "100.00"
