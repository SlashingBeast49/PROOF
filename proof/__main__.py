"""CLI entrypoint for PROOF.

Supports:
1. Verifying single or multiple documents via CLI.
2. Launching the interactive web server (`--serve`).
3. Running benchmark scenarios demonstration (`--demo`).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from proof.engine import verify_documents
from proof.extract import parse_document
from proof.report import format_case_cli, save_case_report


def run_demo(output_dir: Path) -> int:
    """Runs built-in benchmark demonstration cases."""
    from proof.app import BENCHMARK_SCENARIOS

    print("\nRunning PROOF Benchmark Demonstrations...\n")
    all_passed = True

    for key, sc in BENCHMARK_SCENARIOS.items():
        print(f"\n[DEMO] {sc['title']}")
        print(f"       {sc['description']}")
        docs = [parse_document(d["content"], d["filename"]) for d in sc["documents"]]
        case = verify_documents(docs, title=sc["title"])
        print(format_case_cli(case))

        json_path, html_path = save_case_report(case, output_dir)
        print(f"Saved JSON Report: {json_path}")
        if html_path:
            print(f"Saved HTML Report: {html_path}")

    return 0


def run_server(host: str, port: int, reload: bool) -> None:
    """Launches the PROOF FastAPI web platform."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the web server. Run: pip install uvicorn")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  PROOF Web Platform is starting on http://{host}:{port}")
    print(f"  Document verification, without the magic-word marketing.")
    print(f"=======================================================\n")
    uvicorn.run("proof.app:app", host=host, port=port, reload=reload)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="proof",
        description="PROOF: Document intelligence and consistency verification platform.",
    )
    parser.add_argument(
        "documents",
        nargs="*",
        type=Path,
        help="One or more document file paths (PDF or TXT) to verify.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory to save generated JSON and HTML reports (default: outputs).",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the interactive web application.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Web server host (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Web server port (default: 8000).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for local web development.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Execute synthetic multi-document benchmark demonstrations.",
    )

    args = parser.parse_args()

    if args.serve:
        run_server(args.host, args.port, args.reload)
        return 0

    if args.demo:
        return run_demo(args.output_dir)

    if not args.documents:
        parser.print_help()
        print("\nTip: To start the web application, run: python -m proof --serve")
        print("Tip: To run the benchmark demo, run:     python -m proof --demo")
        return 0

    # Parse and verify the provided documents
    docs = []
    for doc_path in args.documents:
        if not doc_path.is_file():
            parser.error(f"File not found: {doc_path}")
        try:
            doc = parse_document(doc_path)
            docs.append(doc)
        except Exception as err:
            parser.error(f"Error parsing '{doc_path}': {err}")

    case = verify_documents(docs, title=f"Verification of {len(docs)} Document(s)")
    print(format_case_cli(case))

    json_path, html_path = save_case_report(case, args.output_dir)
    print(f"\nSaved JSON report: {json_path}")
    if html_path:
        print(f"Saved HTML report: {html_path}")

    # Return 0 if consistent, 1 if review required or inconsistencies found
    return 0 if case.verdict == "VERIFIED_CONSISTENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
