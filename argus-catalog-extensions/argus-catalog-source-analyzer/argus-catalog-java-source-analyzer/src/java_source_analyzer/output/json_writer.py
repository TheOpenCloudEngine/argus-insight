"""JSON output writer for table mapping results."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from java_source_analyzer.models import TableMapping


def write_json(
    mappings: list[TableMapping],
    output_path: str | Path | None = None,
    indent: int = 2,
) -> str:
    """Write table mappings as JSON.

    Args:
        mappings: List of TableMapping records.
        output_path: File path to write to. If None, returns the JSON string.
        indent: JSON indentation level.

    Returns:
        The JSON content as a string.
    """
    data = [asdict(m) for m in mappings]
    content = json.dumps(data, ensure_ascii=False, indent=indent)

    if output_path is not None:
        Path(output_path).write_text(content, encoding="utf-8")

    return content
