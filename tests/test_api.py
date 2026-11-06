from fastapi.testclient import TestClient
from proof.app import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["platform"] == "PROOF"


def test_api_scenarios():
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) >= 4
    assert any(s["id"] == "perfect_match" for s in scenarios)


def test_api_load_scenario():
    res = client.get("/api/scenarios/perfect_match")
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "VERIFIED_CONSISTENT"
    assert len(data["documents"]) == 2
    assert "findings" in data


def test_api_verify_text():
    payload = {
        "title": "Custom Test Case",
        "documents": [
            {
                "filename": "inv.txt",
                "content": "Document Type: Invoice\nInvoice Number: 101\nTotal: 100.00",
            }
        ],
    }
    res = client.post("/api/cases/verify-text", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"].startswith("case_")


def test_api_override_and_reverify():
    # First create a case
    payload = {
        "title": "Override Test",
        "documents": [
            {
                "filename": "inv.txt",
                "content": "Document Type: Invoice\nInvoice Number: 101\nIssue Date: 2026-08-20\nDue Date: 2026-08-10\nCurrency: USD\nSubtotal: 100.00\nTax: 10.00\nTotal: 110.00",
            }
        ],
    }
    create_res = client.post("/api/cases/verify-text", json=payload)
    case_data = create_res.json()
    case_id = case_data["case_id"]
    doc_id = case_data["documents"][0]["id"]

    # Date order was initially mismatch (due date before issue date)
    assert case_data["verdict"] == "INCONSISTENCIES_FOUND"

    # Human fixes the due date
    override_payload = {
        "case_id": case_id,
        "document_id": doc_id,
        "field_key": "due_date",
        "new_value": "2026-09-20",
    }
    reverify_res = client.post("/api/cases/override-and-reverify", json=override_payload)
    assert reverify_res.status_code == 200
    updated_data = reverify_res.json()
    assert updated_data["verdict"] == "VERIFIED_CONSISTENT"


def test_api_report_html():
    load_res = client.get("/api/scenarios/perfect_match")
    case_id = load_res.json()["case_id"]

    html_res = client.get(f"/api/cases/{case_id}/report.html")
    assert html_res.status_code == 200
    assert "PROOF Verification Report" in html_res.text

