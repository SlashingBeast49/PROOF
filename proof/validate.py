from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass
class Check:
    name: str
    passed: bool
    explanation: str


def validate_invoice(fields: dict[str, str]) -> list[Check]:
    checks = [_required_fields_check(fields)]
    if "invoice_number" in fields:
        checks.append(Check("invoice number", bool(fields["invoice_number"].strip()), "Invoice Number is present."))
    checks.append(_date_order_check(fields))
    checks.append(_total_check(fields))
    return checks


def _required_fields_check(fields: dict[str, str]) -> Check:
    required = {"document_type", "invoice_number", "issue_date", "due_date", "currency", "subtotal", "tax", "total"}
    missing = sorted(required - fields.keys())
    if missing:
        return Check("required fields", False, f"Missing: {', '.join(missing)}.")
    return Check("required fields", True, "All expected invoice fields were extracted.")


def _date_order_check(fields: dict[str, str]) -> Check:
    if not {"issue_date", "due_date"} <= fields.keys():
        return Check("date order", False, "Cannot compare dates because one or both dates are missing.")
    try:
        issue_date = date.fromisoformat(fields["issue_date"])
        due_date = date.fromisoformat(fields["due_date"])
    except ValueError:
        return Check("date order", False, "Dates must use YYYY-MM-DD so they can be checked reliably.")
    passed = due_date >= issue_date
    return Check("date order", passed, "Due Date is on or after Issue Date." if passed else "Due Date is before Issue Date.")


def _total_check(fields: dict[str, str]) -> Check:
    needed = {"subtotal", "tax", "total"}
    if not needed <= fields.keys():
        return Check("amount total", False, "Cannot check the total because subtotal, tax, or total is missing.")
    try:
        subtotal = _money(fields["subtotal"])
        tax = _money(fields["tax"])
        total = _money(fields["total"])
    except InvalidOperation:
        return Check("amount total", False, "Amounts must be plain numbers, for example 1250.00.")
    expected_total = subtotal + tax
    passed = expected_total == total
    return Check("amount total", passed, f"Subtotal + Tax = {expected_total:.2f}; stated Total = {total:.2f}.")


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", "").strip())
