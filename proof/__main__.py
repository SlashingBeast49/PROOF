from __future__ import annotations

import argparse
from pathlib import Path

from proof.extract import extract_fields, read_document
from proof.report import build_report, format_report, save_report
from proof.validate import validate_invoice


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a simple, text-based invoice locally.")
    parser.add_argument("document", type=Path, help="Path to a text-based PDF or development .txt file")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Where to save the JSON report")
    arguments = parser.parse_args()

    if not arguments.document.is_file():
        parser.error(f"File not found: {arguments.document}")

    try:
        extraction = extract_fields(read_document(arguments.document))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))

    report = build_report(arguments.document, extraction, validate_invoice(extraction.fields))
    report_path = save_report(report, arguments.output_dir)
    print(format_report(report))
    print(f"\nSaved JSON report: {report_path}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
