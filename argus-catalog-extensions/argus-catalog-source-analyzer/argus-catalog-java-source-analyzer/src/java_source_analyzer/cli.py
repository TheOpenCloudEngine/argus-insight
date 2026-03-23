"""CLI entry point for java-source-analyzer.

Commands:
    analyze   Scan Java source code and generate a TSV report.
    show      Display a TSV report as a formatted table.
    upload    Upload a TSV report to the Argus Catalog API server.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from java_source_analyzer.output.catalog_uploader import upload_tsv
from java_source_analyzer.output.json_writer import write_json
from java_source_analyzer.output.table_display import display_table
from java_source_analyzer.output.tsv_writer import write_tsv
from java_source_analyzer.scanner import JavaSourceScanner


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="java-source-analyzer",
        description="Analyze Java source code for ORM/DB table mappings",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- analyze ---
    p_analyze = subparsers.add_parser(
        "analyze",
        help="Scan Java source code and generate a TSV report",
    )
    p_analyze.add_argument(
        "source_directory", help="Path to Java project source directory",
    )
    p_analyze.add_argument(
        "--project-name", "-p", required=True, help="Project name for output records",
    )
    p_analyze.add_argument(
        "--output", "-o", help="Output file path (default: stdout, auto-adds .tsv/.json)",
    )
    p_analyze.add_argument(
        "--format", "-f", choices=["tsv", "json", "both"], default="tsv",
        help="Output format (default: tsv)",
    )

    # --- show ---
    p_show = subparsers.add_parser(
        "show",
        help="Display a TSV report as a formatted table",
    )
    p_show.add_argument("tsv_file", help="Path to the TSV file to display")

    # --- upload ---
    p_upload = subparsers.add_parser(
        "upload",
        help="Upload a TSV report to the Argus Catalog API server",
    )
    p_upload.add_argument("tsv_file", help="Path to the TSV file to upload")
    p_upload.add_argument(
        "--api-url", required=True,
        help="Catalog API server URL (e.g., http://localhost:8080)",
    )
    p_upload.add_argument(
        "--api-key", default=None, help="API key for authentication",
    )
    p_upload.add_argument(
        "--timeout", type=int, default=30, help="Request timeout in seconds (default: 30)",
    )

    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(levelname)s: %(message)s", stream=sys.stderr,
    )

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "analyze":
        return _cmd_analyze(args)
    elif args.command == "show":
        return _cmd_show(args)
    elif args.command == "upload":
        return _cmd_upload(args)

    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Execute the analyze command."""
    source_dir = Path(args.source_directory)
    if not source_dir.is_dir():
        print(f"ERROR: Directory not found: {args.source_directory}", file=sys.stderr)
        return 1

    scanner = JavaSourceScanner(args.project_name, source_dir)
    mappings = scanner.scan()

    if not mappings:
        print("No table mappings found.", file=sys.stderr)
        return 0

    fmt = args.format
    output_path = args.output

    if fmt in ("tsv", "both"):
        tsv_path = _resolve_path(output_path, ".tsv", fmt == "both")
        content = write_tsv(mappings, tsv_path)
        if tsv_path is None:
            print(content, end="")
        else:
            print(f"TSV written to: {tsv_path}", file=sys.stderr)

    if fmt in ("json", "both"):
        json_path = _resolve_path(output_path, ".json", fmt == "both")
        content = write_json(mappings, json_path)
        if json_path is None:
            print(content, end="")
        else:
            print(f"JSON written to: {json_path}", file=sys.stderr)

    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    """Execute the show command."""
    display_table(args.tsv_file)
    return 0


def _cmd_upload(args: argparse.Namespace) -> int:
    """Execute the upload command."""
    upload_tsv(
        args.tsv_file,
        args.api_url,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    return 0


def _resolve_path(
    base: str | None, extension: str, force_extension: bool,
) -> str | None:
    """Resolve output path, adding extension if needed."""
    if base is None:
        return None
    if force_extension:
        return f"{base}{extension}" if not base.endswith(extension) else base
    return base


if __name__ == "__main__":
    sys.exit(main())
