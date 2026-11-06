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
    """Generates a standalone, beautifully styled, printable HTML audit report matching thehsiddarth.com aesthetic."""
    verdict_colors = {
        "VERIFIED_CONSISTENT": ("#b8f36a", "color-mix(in srgb, #b8f36a 15%, transparent)", "VERIFIED CONSISTENT"),
        "INCONSISTENCIES_FOUND": ("#f87171", "color-mix(in srgb, #f87171 15%, transparent)", "INCONSISTENCIES FOUND"),
        "REVIEW_REQUIRED": ("#fbbf24", "color-mix(in srgb, #fbbf24 15%, transparent)", "REVIEW REQUIRED"),
        "INSUFFICIENT_EVIDENCE": ("#60a5fa", "color-mix(in srgb, #60a5fa 15%, transparent)", "INSUFFICIENT EVIDENCE"),
    }
    v_color, v_bg, v_text = verdict_colors.get(case.verdict, ("#a8aca2", "#1d211d", case.verdict))

    status_badge_classes = {
        "Match": "background-color: color-mix(in srgb, #b8f36a 15%, transparent); color: #b8f36a; border: 1px solid #b8f36a;",
        "Mismatch": "background-color: color-mix(in srgb, #f87171 15%, transparent); color: #f87171; border: 1px solid #f87171;",
        "Missing": "background-color: color-mix(in srgb, #fbbf24 15%, transparent); color: #fbbf24; border: 1px solid #fbbf24;",
        "Unable to verify": "background-color: color-mix(in srgb, #60a5fa 15%, transparent); color: #60a5fa; border: 1px solid #60a5fa;",
        "Needs review": "background-color: color-mix(in srgb, #fbbf24 15%, transparent); color: #fbbf24; border: 1px solid #fbbf24;",
        "Not applicable": "background-color: #1d211d; color: #a8aca2; border: 1px solid #343a34;",
    }

    # Generate document tables
    docs_html = []
    for doc in case.documents:
        fields_rows = []
        for k, f in doc.extracted_fields.items():
            ev_snip = f.evidence.snippet if f.evidence else "N/A"
            fields_rows.append(f"""
                <tr>
                    <td style="font-weight: 600; padding: 8px 12px; border-bottom: 1px solid #343a34; color: #f2f1eb;">{f.label}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #343a34; font-family: 'DM Mono', monospace; color: #b8f36a;">{f.normalized_value}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #343a34; color: #a8aca2; font-size: 11px; font-family: 'DM Mono', monospace;">{ev_snip}</td>
                </tr>
            """)
        docs_html.append(f"""
            <div style="background: #171a17; border: 1px solid #343a34; border-radius: 12px; margin-bottom: 24px; padding: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                    <h3 style="margin: 0; font-size: 16px; color: #f2f1eb; font-family: 'DM Sans', sans-serif;">📄 {doc.filename}</h3>
                    <span style="background: #1d211d; color: #a8aca2; border: 1px solid #343a34; padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-family: 'DM Mono', monospace;">{doc.doc_type.value}</span>
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 12.5px;">
                    <thead>
                        <tr style="background: #111311; color: #a8aca2; font-family: 'DM Mono', monospace; font-size: 11px;">
                            <th style="padding: 8px 12px; border-bottom: 1px solid #343a34;">FIELD</th>
                            <th style="padding: 8px 12px; border-bottom: 1px solid #343a34;">NORMALIZED VALUE</th>
                            <th style="padding: 8px 12px; border-bottom: 1px solid #343a34;">SOURCE EVIDENCE SNIPPET</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(fields_rows) if fields_rows else '<tr><td colspan="3" style="padding: 12px; color: #a8aca2;">No structured fields extracted.</td></tr>'}
                    </tbody>
                </table>
            </div>
        """)

    # Generate findings rows
    findings_html = []
    for f in case.findings:
        badge_style = status_badge_classes.get(f.status.value, "background-color: #1d211d; color: #f2f1eb;")
        ev_items = []
        for ev in f.evidence:
            ev_items.append(f"""
                <li style="margin-top: 4px; font-size: 11.5px; color: #a8aca2; font-family: 'DM Mono', monospace;">
                    <strong style="color: #b8f36a;">{ev.document_name}</strong> (p. {ev.page_number or 1}{f', line {ev.line_number}' if ev.line_number else ''}): 
                    <code style="background: #111311; border: 1px solid #343a34; padding: 2px 6px; border-radius: 4px; color: #f2f1eb;">{ev.snippet}</code>
                </li>
            """)
        ev_block = f"<ul style='margin: 8px 0 0 0; padding-left: 18px;'>{''.join(ev_items)}</ul>" if ev_items else ""
        action_block = f"<div style='margin-top: 8px; font-size: 12px; color: #fbbf24; font-family: 'DM Mono', monospace;'><strong>ACTION:</strong> {f.human_action_needed}</div>" if f.human_action_needed else ""

        border_color = '#b8f36a' if f.status == VerificationStatus.MATCH else '#f87171' if f.status == VerificationStatus.MISMATCH else '#fbbf24'
        findings_html.append(f"""
            <div style="background: #171a17; border: 1px solid #343a34; border-left: 4px solid {border_color}; border-radius: 10px; padding: 18px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: #a8aca2; font-family: 'DM Mono', monospace;">{f.category} &bull; {f.rule_id}</span>
                        <h4 style="margin: 4px 0 6px 0; font-size: 15px; color: #f2f1eb; font-family: 'DM Sans', sans-serif;">{f.title}</h4>
                    </div>
                    <span style="display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 10.5px; font-family: 'DM Mono', monospace; font-weight: 600; {badge_style}">
                        {f.status.value}
                    </span>
                </div>
                <p style="margin: 6px 0; color: #a8aca2; font-size: 13.5px; line-height: 1.5;">{f.explanation}</p>
                {action_block}
                {ev_block}
            </div>
        """)

    # Stats HTML
    stats_pills = []
    for st, count in case.summary_stats.items():
        b_style = status_badge_classes.get(st, "background-color: #1d211d; color: #f2f1eb;")
        stats_pills.append(f"""
            <div style="padding: 10px 14px; border-radius: 10px; {b_style} text-align: center; min-width: 100px;">
                <div style="font-size: 22px; font-weight: 700; font-family: 'DM Mono', monospace;">{count}</div>
                <div style="font-size: 10px; text-transform: uppercase; font-family: 'DM Mono', monospace; letter-spacing: 0.05em;">{st}</div>
            </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PROOF Verification Report &mdash; {case.case_id}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'DM Sans', sans-serif;
            background-color: #111311;
            color: #f2f1eb;
            margin: 0;
            padding: 40px 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        @media print {{
            body {{ background-color: #ffffff; color: #111111; padding: 0; }}
            .no-print {{ display: none; }}
            div, table {{ border-color: #dddddd !important; color: #111111 !important; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; border-bottom: 1px solid #343a34; padding-bottom: 18px;">
            <div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 28px; height: 28px; border: 1px solid #343a34; border-radius: 50%; display: grid; place-items: center; font-family: 'DM Mono', monospace; font-size: 11px; color: #b8f36a;">PR</div>
                    <h1 style="margin: 0; font-size: 24px; letter-spacing: -0.04em;">PROOF</h1>
                </div>
                <div style="color: #a8aca2; font-size: 12px; margin-top: 4px; font-family: 'DM Mono', monospace;">Document verification without magic-word marketing</div>
            </div>
            <div style="text-align: right;">
                <button class="no-print" onclick="window.print()" style="background: #b8f36a; color: #11150e; border: none; padding: 8px 16px; border-radius: 999px; cursor: pointer; font-weight: 600; font-size: 12px; font-family: 'DM Mono', monospace; margin-bottom: 8px;">Print Report</button>
                <div style="font-size: 11px; color: #a8aca2; font-family: 'DM Mono', monospace;">Generated: {case.created_at.strftime('%Y-%m-%d %H:%M UTC')}</div>
            </div>
        </div>

        <!-- Verdict Banner -->
        <div style="background-color: {v_bg}; border: 1px solid {v_color}; color: {v_color}; border-radius: 12px; padding: 20px 24px; margin-bottom: 26px;">
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; font-family: 'DM Mono', monospace; letter-spacing: 0.1em;">Case Verdict</div>
            <div style="font-size: 22px; font-weight: 800; margin-top: 4px; letter-spacing: -0.02em;">{v_text}</div>
            <div style="font-size: 12px; margin-top: 4px; opacity: 0.9; font-family: 'DM Mono', monospace;">Case ID: <code>{case.case_id}</code> &bull; {case.title}</div>
        </div>

        <!-- Summary Statistics -->
        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 30px;">
            {"".join(stats_pills)}
        </div>

        <!-- Axiom Card -->
        <div style="background: #171a17; border: 1px solid #343a34; border-radius: 10px; padding: 14px 18px; margin-bottom: 30px; font-size: 12.5px; color: #a8aca2; line-height: 1.6;">
            <strong style="color: #b8f36a; font-family: 'DM Mono', monospace;">CORE PHILOSOPHY:</strong> PROOF does not pretend to certify that a document is authentic. It shows what was extracted, what deterministic rules were evaluated, what was found, and what could not be established.
        </div>

        <!-- Documents Section -->
        <h2 style="font-size: 17px; color: #f2f1eb; margin-bottom: 14px; font-family: 'DM Sans', sans-serif;">1. Uploaded Documents & Extracted Fields</h2>
        {"".join(docs_html)}

        <!-- Findings Section -->
        <h2 style="font-size: 17px; color: #f2f1eb; margin-top: 32px; margin-bottom: 14px; font-family: 'DM Sans', sans-serif;">2. Verification Findings & Source Evidence</h2>
        {"".join(findings_html)}

        <!-- Devotional Section matching thehsiddarth.com -->
        <div style="text-align: center; padding: 40px 16px 28px; border-top: 1px solid #343a34; margin-top: 40px;">
            <span style="font-size: 10px; letter-spacing: 3px; opacity: 0.5; margin-bottom: 14px; font-family: 'DM Mono', monospace; display: block; color: #a8aca2;">A MOMENT OF GRATITUDE</span>
            <h3 style="font-family: serif; font-size: 24px; font-weight: 500; margin: 10px 0 16px; color: #b8f36a;">॥ ॐ नमः शिवाय ॥</h3>
            <p style="font-family: serif; font-size: 15px; line-height: 2.1; opacity: 0.85; max-width: 600px; margin: auto; color: #f2f1eb; white-space: pre-line;">
                ॐ नमो हिरण्यबाहवे हिरण्यवर्णाय
                हिरण्यरूपाय हिरण्यपतये ।
                अम्बिकापतये उमापतये पशुपतये
                नमो नमः ॥
            </p>
        </div>

        <!-- Footer -->
        <div style="margin-top: 20px; border-top: 1px solid #343a34; padding-top: 16px; text-align: center; font-size: 11px; color: #a8aca2; font-family: 'DM Mono', monospace;">
            Generated by PROOF &bull; https://thehsiddarth.com
        </div>
    </div>
</body>
</html>
"""


def generate_pdf_report(case: VerificationCase, output_path: Path) -> Path:
    """Generates an executive-ready, downloadable PDF verification audit report using ReportLab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise RuntimeError("Direct PDF generation requires reportlab. Run: pip install reportlab")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ProofTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "ProofSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    )
    verdict_style = ParagraphStyle(
        "ProofVerdict",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.white,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    code_style = ParagraphStyle(
        "CodeSnippet",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("PROOF &mdash; Document Verification Report", title_style))
    elements.append(Paragraph(f"Case ID: {case.case_id} &bull; Generated: {case.created_at.strftime('%Y-%m-%d %H:%M UTC')}", subtitle_style))
    elements.append(Spacer(1, 8))

    # Verdict Banner
    verdict_colors = {
        "VERIFIED_CONSISTENT": colors.HexColor("#059669"),
        "INCONSISTENCIES_FOUND": colors.HexColor("#dc2626"),
        "REVIEW_REQUIRED": colors.HexColor("#d97706"),
        "INSUFFICIENT_EVIDENCE": colors.HexColor("#2563eb"),
    }
    banner_color = verdict_colors.get(case.verdict, colors.HexColor("#475569"))
    verdict_table = Table(
        [[Paragraph(f"VERDICT: {case.verdict} &mdash; {case.title}", verdict_style)]],
        colWidths=[540],
    )
    verdict_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), banner_color),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )
    elements.append(verdict_table)
    elements.append(Spacer(1, 8))

    # Summary Stats Pills Table
    stats_data = [
        [
            f"Matches: {case.summary_stats.get('Match', 0)}",
            f"Mismatches: {case.summary_stats.get('Mismatch', 0)}",
            f"Missing: {case.summary_stats.get('Missing', 0)}",
            f"Needs Review: {case.summary_stats.get('Needs review', 0)}",
            f"Unable: {case.summary_stats.get('Unable to verify', 0)}",
        ]
    ]
    stats_table = Table(stats_data, colWidths=[108, 108, 108, 108, 108])
    stats_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    elements.append(stats_table)
    elements.append(Spacer(1, 10))

    # Documents Section
    elements.append(Paragraph("1. Ingested Documents & Extracted Structured Data", section_heading))
    for doc_item in case.documents:
        doc_header = f"<b>{doc_item.filename}</b> ({doc_item.doc_type.value}, {doc_item.page_count} page(s))"
        elements.append(Paragraph(doc_header, body_style))

        field_rows = [["Field", "Normalized Value", "Original Extraction Snippet"]]
        for k, fld in doc_item.extracted_fields.items():
            ev_snip = fld.evidence.snippet if fld.evidence else "N/A"
            field_rows.append([fld.label, str(fld.normalized_value), ev_snip[:65] + ("..." if len(ev_snip) > 65 else "")])

        if len(field_rows) > 1:
            t = Table(field_rows, colWidths=[110, 110, 320])
            t.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ])
            )
            elements.append(t)
        elements.append(Spacer(1, 6))

    # Findings Section
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("2. Deterministic Verification Findings & Source Evidence", section_heading))

    for idx, f in enumerate(case.findings, 1):
        status_color = colors.HexColor("#059669") if f.status == VerificationStatus.MATCH else colors.HexColor("#dc2626") if f.status == VerificationStatus.MISMATCH else colors.HexColor("#d97706")
        f_header = f"<b>[{idx}] {f.status.value.upper()}</b> &bull; {f.category}: {f.title}"
        elements.append(Paragraph(f_header, ParagraphStyle("FindingHeader", parent=body_style, fontName="Helvetica-Bold", textColor=status_color)))
        elements.append(Paragraph(f.explanation, body_style))

        if f.human_action_needed:
            elements.append(Paragraph(f"<b>Recommended Action:</b> {f.human_action_needed}", ParagraphStyle("ActionReq", parent=body_style, textColor=colors.HexColor("#b45309"))))

        for ev in f.evidence:
            loc = f"p.{ev.page_number or 1}" + (f", line {ev.line_number}" if ev.line_number else "")
            elements.append(Paragraph(f"&bull; <i>{ev.document_name} ({loc})</i>: <code>{ev.snippet}</code>", code_style))

        elements.append(Spacer(1, 4))

    # Philosophy Note Footer
    elements.append(Spacer(1, 14))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    elements.append(Spacer(1, 4))
    elements.append(
        Paragraph(
            "<b>PROOF Axiom:</b> PROOF does not certify document authenticity. "
            "Findings reflect deterministic intra-document and cross-document verification checks.",
            ParagraphStyle("AxiomStyle", parent=body_style, fontSize=7, textColor=colors.HexColor("#64748b")),
        )
    )

    doc.build(elements)
    return output_path


def save_case_report(case: VerificationCase, output_dir: Path, as_html: bool = True, as_pdf: bool = True) -> Tuple[Path, Optional[Path]]:
    """Saves machine-readable JSON report, printable HTML report, and optional binary PDF report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{case.case_id}_report.json"
    json_data = build_case_dict(case)
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    html_path: Optional[Path] = None
    if as_html:
        html_path = output_dir / f"{case.case_id}_report.html"
        html_content = generate_html_report(case)
        html_path.write_text(html_content, encoding="utf-8")

    if as_pdf:
        try:
            pdf_path = output_dir / f"{case.case_id}_report.pdf"
            generate_pdf_report(case, pdf_path)
        except Exception:
            pass

    return json_path, html_path
