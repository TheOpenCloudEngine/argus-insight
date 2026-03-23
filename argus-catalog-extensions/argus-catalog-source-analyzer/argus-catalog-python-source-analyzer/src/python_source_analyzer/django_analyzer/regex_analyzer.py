"""Regex-based Django ORM pattern extraction."""

from __future__ import annotations

import re

from python_source_analyzer.models import FileAnalysisResult, RawMapping
from python_source_analyzer.sql_parser import SqlParser

FRAMEWORK = "Django ORM"

_RE_DJANGO_IMPORT = re.compile(r"(?:from\s+django\.db|import\s+django\.db)")

# class Foo(models.Model):
_RE_MODEL_CLASS = re.compile(
    r"class\s+(\w+)\s*\(\s*(?:models\.)?Model\s*\)",
)

# db_table = "users"
_RE_DB_TABLE = re.compile(r'db_table\s*=\s*["\'](\w+)["\']')

# Model.objects.raw("SQL")
_RE_OBJECTS_RAW = re.compile(r'\.objects\.raw\s*\(\s*["\']([^"\']+)["\']', re.DOTALL)

# cursor.execute("SQL")
_RE_CURSOR_EXECUTE = re.compile(r'cursor\.execute\s*\(\s*["\']([^"\']+)["\']', re.DOTALL)

# Class for context
_RE_CLASS = re.compile(r"class\s+(\w+)")
_RE_FUNC = re.compile(r"def\s+(\w+)")


class DjangoRegexAnalyzer:
    """Regex-based Django ORM pattern extraction."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult:
        if not _RE_DJANGO_IMPORT.search(source_code):
            return FileAnalysisResult(source_file=file_path, module_path="", imports=[])

        mappings: list[RawMapping] = []

        # Find model classes
        model_classes = set()
        for m in _RE_MODEL_CLASS.finditer(source_code):
            model_classes.add(m.group(1))

        # Find db_table assignments — db_table is inside class Meta which is inside Model class
        db_tables: dict[str, str] = {}  # class_name -> table_name
        for m in _RE_DB_TABLE.finditer(source_code):
            class_name = self._find_enclosing_model_class(source_code, m.start())
            if class_name:
                db_tables[class_name] = m.group(1)

        # Create mappings for model classes
        for cls in model_classes:
            table = db_tables.get(cls, cls.lower())
            pattern = "Meta.db_table" if cls in db_tables else "Model(auto)"
            mappings.append(RawMapping(
                table_name=table,
                class_or_function=cls,
                access_type="RW",
                framework=FRAMEWORK,
                pattern=pattern,
            ))

        # objects.raw("SQL")
        for m in _RE_OBJECTS_RAW.finditer(source_code):
            sql = m.group(1)
            func = self._find_enclosing_func(source_code, m.start())
            refs = self._sql_parser.parse(sql)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_function=func or "<module>",
                    access_type=ref.access_type,
                    framework=FRAMEWORK,
                    pattern="objects.raw()",
                ))

        # cursor.execute("SQL")
        for m in _RE_CURSOR_EXECUTE.finditer(source_code):
            sql = m.group(1)
            func = self._find_enclosing_func(source_code, m.start())
            refs = self._sql_parser.parse(sql)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_function=func or "<module>",
                    access_type=ref.access_type,
                    framework=FRAMEWORK,
                    pattern="cursor.execute()",
                ))

        return FileAnalysisResult(
            source_file=file_path,
            module_path="",
            imports=["django.db"],
            mappings=mappings,
        )

    def _find_enclosing_class(self, source: str, pos: int) -> str | None:
        matches = list(_RE_CLASS.finditer(source[:pos]))
        return matches[-1].group(1) if matches else None

    def _find_enclosing_model_class(self, source: str, pos: int) -> str | None:
        """Find the Model class that contains Meta.db_table (skip 'Meta' itself)."""
        matches = list(_RE_CLASS.finditer(source[:pos]))
        # Walk backwards, skip "Meta"
        for m in reversed(matches):
            if m.group(1) != "Meta":
                return m.group(1)
        return None

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
