"""JSON output writer."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from python_source_analyzer.models import TableMapping


def write_json(
    mappings: list[TableMapping],
    output_path: str | Path | None = None,
    indent: int = 2,
) -> str:
    data = [asdict(m) for m in mappings]
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    if output_path is not None:
        Path(output_path).write_text(content, encoding="utf-8")
    return content
