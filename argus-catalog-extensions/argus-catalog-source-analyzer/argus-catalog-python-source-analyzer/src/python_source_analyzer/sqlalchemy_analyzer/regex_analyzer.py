"""Regex-based SQLAlchemy pattern extraction."""

from __future__ import annotations

import re

from python_source_analyzer.models import FileAnalysisResult, RawMapping
from python_source_analyzer.sql_parser import SqlParser

FRAMEWORK = "SQLAlchemy"

_RE_SA_IMPORT = re.compile(r"(?:from\s+sqlalchemy|import\s+sqlalchemy|from\s+sqlmodel)")

# __tablename__ = "users" or __tablename__ = 'users'
_RE_TABLENAME = re.compile(r'__tablename__\s*=\s*["\'](\w+)["\']')

# Table("users", metadata, ...) or Table("users", ...)
_RE_TABLE_CORE = re.compile(r'Table\s*\(\s*["\'](\w+)["\']')

# text("SQL") — raw SQL via text()
_RE_TEXT_SQL = re.compile(r'text\s*\(\s*["\']([^"\']+)["\']', re.DOTALL)
_RE_TEXT_SQL_TRIPLE = re.compile(r'text\s*\(\s*"""(.*?)"""', re.DOTALL)
_RE_TEXT_SQL_TRIPLE_SQ = re.compile(r"text\s*\(\s*'''(.*?)'''", re.DOTALL)

# session.execute(text("SQL")) or connection.execute(text("SQL"))
_RE_EXECUTE_TEXT = re.compile(
    r'\.execute\s*\(\s*text\s*\(\s*["\']([^"\']+)["\']', re.DOTALL,
)
_RE_EXECUTE_STR = re.compile(
    r'\.execute\s*\(\s*["\']([^"\']+)["\']', re.DOTALL,
)

# Class definition
_RE_CLASS = re.compile(r"class\s+(\w+)\s*\(")

# Function definition
_RE_FUNC = re.compile(r"def\s+(\w+)\s*\(")


class SqlAlchemyRegexAnalyzer:
    """Regex-based SQLAlchemy pattern extraction."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult:
        if not _RE_SA_IMPORT.search(source_code):
            return FileAnalysisResult(source_file=file_path, module_path="", imports=[])

        mappings: list[RawMapping] = []

        # __tablename__ = "users"
        for m in _RE_TABLENAME.finditer(source_code):
            class_name = self._find_enclosing_class(source_code, m.start())
            mappings.append(RawMapping(
                table_name=m.group(1),
                class_or_function=class_name or "Unknown",
                access_type="RW",
                framework=FRAMEWORK,
                pattern="__tablename__",
            ))

        # Table("users", ...)
        for m in _RE_TABLE_CORE.finditer(source_code):
            mappings.append(RawMapping(
                table_name=m.group(1),
                class_or_function="<module>",
                access_type="RW",
                framework=FRAMEWORK,
                pattern="Table()",
            ))

        # text("SQL") patterns
        for pattern in (_RE_TEXT_SQL_TRIPLE, _RE_TEXT_SQL_TRIPLE_SQ, _RE_TEXT_SQL):
            for m in pattern.finditer(source_code):
                sql = m.group(1).strip()
                func_name = self._find_enclosing_func(source_code, m.start())
                refs = self._sql_parser.parse(sql)
                for ref in refs:
                    mappings.append(RawMapping(
                        table_name=ref.table_name,
                        class_or_function=func_name or "<module>",
                        access_type=ref.access_type,
                        framework=FRAMEWORK,
                        pattern="text()",
                    ))

        # .execute("SQL") — direct string
        for m in _RE_EXECUTE_STR.finditer(source_code):
            sql = m.group(1)
            # Skip if this was already caught by text() patterns
            if "text(" in source_code[max(0, m.start()-10):m.start()]:
                continue
            func_name = self._find_enclosing_func(source_code, m.start())
            refs = self._sql_parser.parse(sql)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_function=func_name or "<module>",
                    access_type=ref.access_type,
                    framework=FRAMEWORK,
                    pattern="execute()",
                ))

        return FileAnalysisResult(
            source_file=file_path,
            module_path="",
            imports=["sqlalchemy"],
            mappings=mappings,
        )

    def _find_enclosing_class(self, source: str, pos: int) -> str | None:
        preceding = source[:pos]
        matches = list(_RE_CLASS.finditer(preceding))
        return matches[-1].group(1) if matches else None

    def _find_enclosing_func(self, source: str, pos: int) -> str | None:
        preceding = source[:pos]
        classes = list(_RE_CLASS.finditer(preceding))
        funcs = list(_RE_FUNC.finditer(preceding))
        parts = []
        if classes:
            parts.append(classes[-1].group(1))
        if funcs:
            parts.append(funcs[-1].group(1))
        return ".".join(parts) if parts else None
