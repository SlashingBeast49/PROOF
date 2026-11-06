"""Reporting engine for PROOF.

Generates structured JSON reports, human-readable CLI summaries,
and professional printable HTML audit reports backed by source evidence.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional, Tuple

from proof.extract import ExtractionResult
from proof.models import VerificationCase, VerificationStatus
from proof.validate import Check


def build_report(input_path: Path, extraction: ExtractionResult, checks: list[Check]) -> dict:
    """Legacy report builder for backward compatibility."""
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
    """Legacy text formatter."""
    lines = [
        f"PROOF verification report: {report['verdict']}",
        f"Input: {report['input_file']}",
        "",
        "Extracted fields:",
    ]
    lines.extend(f"- {name}: {value}" for name, value in report.get("extracted_fields", {}).items())
    lines.extend(["", "Checks:"])
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'} — {check['name']}: {check['explanation']}" for check in report.get("checks", []))
    if report.get("extraction_notes"):
        lines.extend(["", "Extraction notes:"])
        lines.extend(f"- {note}" for note in report["extraction_notes"])
    return "\n".join(lines)


def save_report(report: dict, output_dir: Path) -> Path:
    """Legacy JSON report saver."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{Path(report['input_file']).stem}_report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination


# Modern Multi-document Case Reporting


def build_case_dict(case: VerificationCase) -> dict:
    """Converts a VerificationCase into a clean JSON-serializable dictionary."""
    return {
        "case_id": case.case_id,
        "title": case.title,
        "created_at": case.created_at.isoformat(),
        "verdict": case.verdict,
        "philosophy": (
            "PROOF does not certify document authenticity. "
            "Findings reflect deterministic checks across extracted information."
        ),
        "summary_stats": case.summary_stats,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "doc_type": doc.doc_type.value,
                "page_count": doc.page_count,
                "extracted_fields": {
                    k: {
                        "label": f.label,
                        "original_value": f.original_value,
                        "normalized_value": f.normalized_value,
                        "confidence": f.confidence,
                        "evidence": f.evidence.model_dump() if f.evidence else None,
                    }
                    for k, f in doc.extracted_fields.items()
                },
                "notes": doc.notes,
            }
            for doc in case.documents
        ],
        "findings": [
            {
                "id": f.id,
                "rule_id": f.rule_id,
                "title": f.title,
                "category": f.category,
                "status": f.status.value,
                "severity": f.severity.value,
                "explanation": f.explanation,
                "human_action_needed": f.human_action_needed,
                "evidence": [ev.model_dump() for ev in f.evidence],
            }
            for f in case.findings
        ],
    }


def format_case_cli(case: VerificationCase) -> str:
    """Formats verification case results for terminal output."""
    lines = [
        "=" * 64,
        "  PROOF — Document Intelligence & Consistency Verification",
        "=" * 64,
        f"Case ID  : {case.case_id}",
        f"Title    : {case.title}",
        f"Verdict  : {case.verdict}",
        f"Documents: {len(case.documents)} uploaded",
        "",
        "Summary Findings:",
    ]
    for status, count in case.summary_stats.items():
        lines.append(f"  • {status:18}: {count}")

    lines.append("\n" + "-" * 64)
    lines.append("DETAILED FINDINGS & EVIDENCE:")
    lines.append("-" * 64)

    for i, f in enumerate(case.findings, 1):
        lines.append(f"[{i}] {f.status.value.upper():16} | {f.category} — {f.title}")
        lines.append(f"    Explanation : {f.explanation}")
        if f.human_action_needed:
            lines.append(f"    Action      : {f.human_action_needed}")
        if f.evidence:
            lines.append("    Source Evidence:")
            for ev in f.evidence:
                loc = f"p.{ev.page_number or 1}"
                if ev.line_number:
                    loc += f", line {ev.line_number}"
                lines.append(f"      - [{ev.document_name} ({loc})]: \"{ev.snippet}\"")
        lines.append("")

    lines.append("=" * 64)
    lines.append("Core Philosophy: PROOF explains what was extracted and verified.")
    lines.append("It does not make unbacked certifications of legal authenticity.")
    lines.append("=" * 64)
    return "\n".join(lines)


def generate_html_report(case: VerificationCase) -> str:
    """Generates a standalone, beautifully styled, printable HTML audit report."""
    verdict_colors = {
        "VERIFIED_CONSISTENT": ("#065f46", "#d1fae5", "VERIFIED CONSISTENT"),
        "INCONSISTENCIES_FOUND": ("#991b1b", "#fee2e2", "INCONSISTENCIES FOUND"),
        "REVIEW_REQUIRED": ("#92400e", "#fef3c7", "REVIEW REQUIRED"),
        "INSUFFICIENT_EVIDENCE": ("#1e40af", "#dbeafe", "INSUFFICIENT EVIDENCE"),
    }
    v_color, v_bg, v_text = verdict_colors.get(case.verdict, ("#374151", "#f3f4f6", case.verdict))

    status_badge_classes = {
        "Match": "background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0;",
        "Mismatch": "background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;",
        "Missing": "background-color: #ffedd5; color: #9a3412; border: 1px solid #fdba74;",
        "Unable to verify": "background-color: #e0f2fe; color: #075985; border: 1px solid #bae6fd;",
        "Needs review": "background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a;",
        "Not applicable": "background-color: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb;",
    }

    # Generate document tables
    docs_html = []
    for doc in case.documents:
        fields_rows = []
        for k, f in doc.extracted_fields.items():
            ev_snip = f.evidence.snippet if f.evidence else "N/A"
            fields_rows.append(f"""
                <tr>
                    <td style="font-weight: 600; padding: 8px 12px; border-bottom: 1px solid #e5e7eb;">{f.label}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace;">{f.normalized_value}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">{ev_snip}</td>
                </tr>
            """)
        docs_html.append(f"""
            <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 24px; padding: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h3 style="margin: 0; font-size: 18px; color: #111827;">📄 {doc.filename}</h3>
                    <span style="background: #f3f4f6; color: #374151; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600;">{doc.doc_type.value}</span>
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                    <thead>
                        <tr style="background: #f9fafb; color: #4b5563;">
                            <th style="padding: 8px 12px; border-bottom: 2px solid #e5e7eb;">Field</th>
                            <th style="padding: 8px 12px; border-bottom: 2px solid #e5e7eb;">Normalized Value</th>
                            <th style="padding: 8px 12px; border-bottom: 2px solid #e5e7eb;">Source Line Evidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(fields_rows) if fields_rows else '<tr><td colspan="3" style="padding: 12px; color: #9ca3af;">No structured fields extracted.</td></tr>'}
                    </tbody>
                </table>
            </div>
        """)

    # Generate findings rows
    findings_html = []
    for f in case.findings:
        badge_style = status_badge_classes.get(f.status.value, "background-color: #f3f4f6; color: #374151;")
        ev_items = []
        for ev in f.evidence:
            ev_items.append(f"""
                <li style="margin-top: 4px; font-size: 13px; color: #4b5563;">
                    <strong>{ev.document_name}</strong> (p. {ev.page_number or 1}{f', line {ev.line_number}' if ev.line_number else ''}): 
                    <code style="background: #f3f4f6; padding: 2px 6px; border-radius: 4px;">{ev.snippet}</code>
                </li>
            """)
        ev_block = f"<ul style='margin: 8px 0 0 0; padding-left: 20px;'>{''.join(ev_items)}</ul>" if ev_items else ""
        action_block = f"<div style='margin-top: 6px; font-size: 13px; color: #b45309;'><strong>Recommended Action:</strong> {f.human_action_needed}</div>" if f.human_action_needed else ""

        findings_html.append(f"""
            <div style="background: #ffffff; border: 1px solid #e5e7eb; border-left: 4px solid { '#ef4444' if f.status == VerificationStatus.MISMATCH else '#10b981' if f.status == VerificationStatus.MATCH else '#f59e0b' }; border-radius: 6px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; font-weight: bold;">{f.category}</span>
                        <h4 style="margin: 4px 0 6px 0; font-size: 16px; color: #111827;">{f.title}</h4>
                    </div>
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; {badge_style}">
                        {f.status.value}
                    </span>
                </div>
                <p style="margin: 6px 0; color: #374151; font-size: 14px; line-height: 1.5;">{f.explanation}</p>
                {action_block}
                {ev_block}
            </div>
        """)

    # Stats HTML
    stats_pills = []
    for st, count in case.summary_stats.items():
        b_style = status_badge_classes.get(st, "background-color: #f3f4f6; color: #374151;")
        stats_pills.append(f"""
            <div style="padding: 10px 16px; border-radius: 8px; {b_style} text-align: center; min-width: 110px;">
                <div style="font-size: 20px; font-weight: 700;">{count}</div>
                <div style="font-size: 11px; text-transform: uppercase; font-weight: 600;">{st}</div>
            </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PROOF Verification Report — {case.case_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f8fafc;
            color: #0f172a;
            margin: 0;
            padding: 32px 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        @media print {{
            body {{ background-color: #ffffff; padding: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px;">
            <div>
                <h1 style="margin: 0; font-size: 26px; color: #0f172a; letter-spacing: -0.02em;">PROOF</h1>
                <div style="color: #64748b; font-size: 13px; margin-top: 4px;">Document Intelligence & Consistency Verification Report</div>
            </div>
            <div style="text-align: right;">
                <button class="no-print" onclick="window.print()" style="background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; margin-bottom: 8px;">Print / Save as PDF</button>
                <div style="font-size: 12px; color: #64748b;">Generated: {case.created_at.strftime('%Y-%m-%d %H:%M UTC')}</div>
            </div>
        </div>

        <!-- Verdict Banner -->
        <div style="background-color: {v_bg}; border: 1px solid {v_color}; color: {v_color}; border-radius: 8px; padding: 18px 24px; margin-bottom: 28px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Case Verdict</div>
                <div style="font-size: 22px; font-weight: 800; margin-top: 4px;">{v_text}</div>
                <div style="font-size: 13px; margin-top: 4px; opacity: 0.9;">Case ID: <code>{case.case_id}</code> &bull; {case.title}</div>
            </div>
        </div>

        <!-- Summary Statistics -->
        <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 32px;">
            {"".join(stats_pills)}
        </div>

        <!-- Philosophy Card -->
        <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 12px 16px; margin-bottom: 32px; font-size: 13px; color: #1e40af;">
            <strong>Core Philosophy:</strong> PROOF does not pretend to certify that a document is authentic. It shows what was extracted, what deterministic rules were checked, what was found, and what could not be established.
        </div>

        <!-- Documents Section -->
        <h2 style="font-size: 20px; color: #1e293b; margin-bottom: 16px;">1. Uploaded Documents & Extracted Fields</h2>
        {"".join(docs_html)}

        <!-- Findings Section -->
        <h2 style="font-size: 20px; color: #1e293b; margin-top: 36px; margin-bottom: 16px;">2. Verification Findings & Source Evidence</h2>
        {"".join(findings_html)}

        <!-- Footer -->
        <div style="margin-top: 48px; border-top: 1px solid #e2e8f0; padding-top: 16px; text-align: center; font-size: 12px; color: #94a3b8;">
            Generated by PROOF — Document verification, without the magic-word marketing.
        </div>
    </div>
</body>
</html>
"""


def save_case_report(case: VerificationCase, output_dir: Path, as_html: bool = True) -> Tuple[Path, Optional[Path]]:
    """Saves both the machine-readable JSON report and the printable HTML report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{case.case_id}_report.json"
    json_data = build_case_dict(case)
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    html_path: Optional[Path] = None
    if as_html:
        html_path = output_dir / f"{case.case_id}_report.html"
        html_content = generate_html_report(case)
        html_path.write_text(html_content, encoding="utf-8")

    return json_path, html_path
