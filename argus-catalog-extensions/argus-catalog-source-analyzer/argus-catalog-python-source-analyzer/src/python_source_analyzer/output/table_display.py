"""Display TSV file as a formatted table in the terminal."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def display_table(tsv_path: str | Path) -> None:
    """Read a TSV file and print it as a formatted table."""
    path = Path(tsv_path)
    if not path.is_file():
        print(f"ERROR: File not found: {tsv_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        rows = list(reader)

    if not rows:
        print("(empty file)")
        return

    col_widths = [0] * len(rows[0])
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], _display_width(cell))

    _print_separator(col_widths)
    _print_row(rows[0], col_widths)
    _print_separator(col_widths)
    for row in rows[1:]:
        _print_row(row, col_widths)
    _print_separator(col_widths)
    print(f"\nTotal: {len(rows) - 1} records")


def _display_width(s: str) -> int:
    width = 0
    for ch in s:
        if ord(ch) > 0x1100 and _is_wide(ch):
            width += 2
        else:
            width += 1
    return width


def _is_wide(ch: str) -> bool:
    cp = ord(ch)
    return (
        (0x1100 <= cp <= 0x115F)
        or (0x2E80 <= cp <= 0x9FFF)
        or (0xAC00 <= cp <= 0xD7A3)
        or (0xF900 <= cp <= 0xFAFF)
        or (0xFE10 <= cp <= 0xFE6F)
        or (0xFF01 <= cp <= 0xFF60)
        or (0xFFE0 <= cp <= 0xFFE6)
        or (0x20000 <= cp <= 0x2FA1F)
    )


def _pad(s: str, width: int) -> str:
    diff = width - _display_width(s)
    return s + " " * max(0, diff)


def _print_separator(col_widths: list[int]) -> None:
    parts = ["+" + "-" * (w + 2) for w in col_widths]
    print("".join(parts) + "+")


def _print_row(row: list[str], col_widths: list[int]) -> None:
    parts = []
    for i, cell in enumerate(row):
        w = col_widths[i] if i < len(col_widths) else 0
        parts.append("| " + _pad(cell, w) + " ")
    print("".join(parts) + "|")
