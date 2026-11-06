"""Verification execution engine for PROOF."""

from __future__ import annotations

from typing import List, Optional
import uuid

from proof.extract import parse_document
from proof.models import (
    Document,
    Finding,
    Severity,
    VerificationCase,
    VerificationStatus,
)
from proof.rules import run_crossdoc_rules, run_intradoc_rules


def verify_documents(documents: List[Document], title: str = "Verification Case") -> VerificationCase:
    """Executes deterministic intra- and cross-document verification pipelines."""
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    findings: List[Finding] = []

    # 1. Run Intra-document verification for each document
    for doc in documents:
        intradoc_findings = run_intradoc_rules(doc)
        findings.extend(intradoc_findings)

    # 2. Run Cross-document consistency rules across documents
    cross_findings = run_crossdoc_rules(documents)
    findings.extend(cross_findings)

    # 3. Compute Summary Statistics
    summary_stats = {
        VerificationStatus.MATCH.value: 0,
        VerificationStatus.MISMATCH.value: 0,
        VerificationStatus.MISSING.value: 0,
        VerificationStatus.UNABLE_TO_VERIFY.value: 0,
        VerificationStatus.NEEDS_REVIEW.value: 0,
        VerificationStatus.NOT_APPLICABLE.value: 0,
    }
    for f in findings:
        summary_stats[f.status.value] = summary_stats.get(f.status.value, 0) + 1

    # 4. Formulate Case Verdict strictly following core philosophy
    if summary_stats[VerificationStatus.MISMATCH.value] > 0:
        verdict = "INCONSISTENCIES_FOUND"
    elif (
        summary_stats[VerificationStatus.MISSING.value] > 0
        or summary_stats[VerificationStatus.NEEDS_REVIEW.value] > 0
    ):
        verdict = "REVIEW_REQUIRED"
    elif summary_stats[VerificationStatus.UNABLE_TO_VERIFY.value] > 0:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "VERIFIED_CONSISTENT"

    return VerificationCase(
        case_id=case_id,
        title=title,
        documents=documents,
        findings=findings,
        verdict=verdict,
        summary_stats=summary_stats,
    )


def verify_text_or_files(sources: List[str], filenames: Optional[List[str]] = None, title: str = "Verification Case") -> VerificationCase:
    """Helper that parses a list of texts or paths and runs verification."""
    docs = []
    filenames = filenames or [f"document_{i + 1}.txt" for i in range(len(sources))]
    for text, name in zip(sources, filenames):
        doc = parse_document(text, name)
        docs.append(doc)
    return verify_documents(docs, title=title)
