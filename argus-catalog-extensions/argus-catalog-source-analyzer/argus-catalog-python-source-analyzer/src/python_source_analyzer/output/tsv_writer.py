"""TSV output writer for table mapping results."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from python_source_analyzer.models import TableMapping

HEADERS = [
    "프로젝트명",
    "소스파일",
    "모듈경로",
    "클래스/함수",
    "Python Version",
    "프레임워크",
    "테이블명",
    "사용방식",
]


def write_tsv(
    mappings: list[TableMapping],
    output_path: str | Path | None = None,
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
    writer.writerow(HEADERS)
    for m in mappings:
        writer.writerow([
            m.project_name, m.source_file, m.module_path,
            m.class_or_function, m.python_version, m.framework,
            m.table_name, m.access_type,
        ])
    content = buf.getvalue()
    if output_path is not None:
        Path(output_path).write_text(content, encoding="utf-8")
    return content
