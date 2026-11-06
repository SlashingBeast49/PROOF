from pathlib import Path
from proof.engine import verify_documents
from proof.extract import parse_document
from proof.report import generate_html_report, save_case_report


def test_verify_single_consistent_document():
    path = Path("samples") / "valid_invoice.txt"
    doc = parse_document(path)
    case = verify_documents([doc])
    assert case.verdict == "VERIFIED_CONSISTENT"
    assert case.summary_stats["Match"] >= 3
    assert case.summary_stats["Mismatch"] == 0


def test_verify_multi_document_matching():
    inv_doc = parse_document(Path("samples") / "valid_invoice.txt")
    po_doc = parse_document(Path("samples") / "matching_purchase_order.txt")
    case = verify_documents([inv_doc, po_doc])

    assert case.verdict == "VERIFIED_CONSISTENT"
    assert case.summary_stats["Mismatch"] == 0
    assert len(case.findings) >= 5


def test_verify_multi_document_mismatch():
    inv_doc = parse_document(Path("samples") / "valid_invoice.txt")
    po_doc = parse_document(Path("samples") / "mismatched_purchase_order.txt")
    case = verify_documents([inv_doc, po_doc])

    assert case.verdict == "INCONSISTENCIES_FOUND"
    assert case.summary_stats["Mismatch"] > 0


def test_case_report_generation(tmp_path):
    inv_doc = parse_document(Path("samples") / "valid_invoice.txt")
    case = verify_documents([inv_doc])
    json_path, html_path = save_case_report(case, tmp_path)

    assert json_path.is_file()
    assert html_path.is_file()

    html_content = html_path.read_text(encoding="utf-8")
    assert "PROOF Verification Report" in html_content
    assert case.case_id in html_content
