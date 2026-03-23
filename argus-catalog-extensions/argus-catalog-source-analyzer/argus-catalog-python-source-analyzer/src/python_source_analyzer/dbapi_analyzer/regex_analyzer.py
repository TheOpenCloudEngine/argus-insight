"""Regex-based DB-API pattern extraction."""

from __future__ import annotations

import re

from python_source_analyzer.models import FileAnalysisResult, RawMapping
from python_source_analyzer.sql_parser import SqlParser

FRAMEWORK = "DB-API"

_DBAPI_PACKAGES = [
    "sqlite3", "psycopg2", "psycopg", "pymysql", "MySQLdb",
    "cx_Oracle", "oracledb", "pyodbc", "pymssql",
    "asyncpg", "aiomysql", "aiosqlite",
]

_RE_DBAPI_IMPORT = re.compile(
    r"(?:import|from)\s+(?:" + "|".join(re.escape(p) for p in _DBAPI_PACKAGES) + r")\b",
)

# cursor.execute("SQL") and variants — single-quoted and double-quoted
_RE_EXECUTE = re.compile(r'\.execute\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_EXECUTE_SQ = re.compile(r"\.execute\s*\(\s*'([^']+)'", re.DOTALL)

# cursor.executemany("SQL", ...)
_RE_EXECUTEMANY = re.compile(r'\.executemany\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_EXECUTEMANY_SQ = re.compile(r"\.executemany\s*\(\s*'([^']+)'", re.DOTALL)

# Triple-quoted SQL strings
_RE_EXECUTE_TRIPLE_DQ = re.compile(r'\.execute\s*\(\s*"""(.*?)"""', re.DOTALL)
_RE_EXECUTE_TRIPLE_SQ = re.compile(r"\.execute\s*\(\s*'''(.*?)'''", re.DOTALL)

# SQL string variable: sql = "SELECT ..."
_RE_SQL_VAR = re.compile(
    r'(?:sql|query|stmt)\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)
_RE_SQL_VAR_TRIPLE = re.compile(
    r'(?:sql|query|stmt)\s*=\s*"""(.*?)"""',
    re.IGNORECASE | re.DOTALL,
)

# asyncpg: connection.fetch("SQL"), connection.fetchrow("SQL")
_RE_FETCH = re.compile(r'\.fetch(?:val|row)?\s*\(\s*"([^"]+)"', re.DOTALL)

_RE_CLASS = re.compile(r"class\s+(\w+)")
_RE_FUNC = re.compile(r"def\s+(\w+)")


class DbApiRegexAnalyzer:
    """Regex-based DB-API pattern extraction."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult:
        if not _RE_DBAPI_IMPORT.search(source_code):
            return FileAnalysisResult(source_file=file_path, module_path="", imports=[])

        framework = self._detect_framework(source_code)
        mappings: list[RawMapping] = []
        seen: set[tuple[str, str, str]] = set()

        # cursor.execute("SQL") — all variants
        all_patterns = [
            (_RE_EXECUTE_TRIPLE_DQ, "execute"),
            (_RE_EXECUTE_TRIPLE_SQ, "execute"),
            (_RE_EXECUTE, "execute"),
            (_RE_EXECUTE_SQ, "execute"),
            (_RE_EXECUTEMANY, "executemany"),
            (_RE_EXECUTEMANY_SQ, "executemany"),
            (_RE_FETCH, "fetch"),
        ]

        for pattern, method_name in all_patterns:
            for m in pattern.finditer(source_code):
                sql = m.group(1).strip()
                func = self._find_context(source_code, m.start())
                refs = self._sql_parser.parse(sql)
                for ref in refs:
                    key = (func, ref.table_name, ref.access_type)
                    if key not in seen:
                        seen.add(key)
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_function=func or "<module>",
                            access_type=ref.access_type,
                            framework=framework,
                            pattern=f"cursor.{method_name}()",
                        ))

        # SQL variable assignments
        for pattern in (_RE_SQL_VAR_TRIPLE, _RE_SQL_VAR):
            for m in pattern.finditer(source_code):
                sql = m.group(1).strip()
                func = self._find_context(source_code, m.start())
                refs = self._sql_parser.parse(sql)
                for ref in refs:
                    key = (func, ref.table_name, ref.access_type)
                    if key not in seen:
                        seen.add(key)
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_function=func or "<module>",
                            access_type=ref.access_type,
                            framework=framework,
                            pattern="SQL variable",
                        ))

        return FileAnalysisResult(
            source_file=file_path,
            module_path="",
            imports=[],
            mappings=mappings,
        )

    def _detect_framework(self, source_code: str) -> str:
        for pkg in _DBAPI_PACKAGES:
            if re.search(rf"(?:import|from)\s+{re.escape(pkg)}\b", source_code):
                return f"DB-API ({pkg})"
        return FRAMEWORK

    def _find_context(self, source: str, pos: int) -> str | None:
        preceding = source[:pos]
        classes = list(_RE_CLASS.finditer(preceding))
        funcs = list(_RE_FUNC.finditer(preceding))
        parts = []
        if classes:
            parts.append(classes[-1].group(1))
        if funcs:
            parts.append(funcs[-1].group(1))
        return ".".join(parts) if parts else None
