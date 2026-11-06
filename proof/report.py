from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from proof.extract import ExtractionResult
from proof.validate import Check


def build_report(input_path: Path, extraction: ExtractionResult, checks: list[Check]) -> dict:
    passed = all(check.passed for check in checks)
    return {
        "input_file": str(input_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS" if passed else "REVIEW REQUIRED",
        "extracted_fields": extraction.fields,
        "extraction_notes": extraction.notes,
        "checks": [asdict(check) for check in checks],
    }


def format_report(report: dict) -> str:
    lines = [f"PROOF verification report: {report['verdict']}", f"Input: {report['input_file']}", "", "Extracted fields:"]
    lines.extend(f"- {name}: {value}" for name, value in report["extracted_fields"].items())
    lines.extend(["", "Checks:"])
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'} — {check['name']}: {check['explanation']}" for check in report["checks"])
    if report["extraction_notes"]:
        lines.extend(["", "Extraction notes:"])
        lines.extend(f"- {note}" for note in report["extraction_notes"])
    return "\n".join(lines)


def save_report(report: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{Path(report['input_file']).stem}_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination
