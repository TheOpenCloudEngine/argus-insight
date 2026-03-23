"""Regex-based JDBC pattern extraction.

Supplements the AST analyzer for Spring JDBC and raw JDBC patterns.
"""

from __future__ import annotations

import logging
import re

from java_source_analyzer.jpa.sql_parser import SqlParser
from java_source_analyzer.models import FileAnalysisResult, RawMapping

logger = logging.getLogger(__name__)

# Import detection
_RE_SPRING_JDBC = re.compile(r"import\s+org\.springframework\.jdbc\.")
_RE_RAW_JDBC = re.compile(r"import\s+java\.sql\.")

# Spring JdbcTemplate patterns
_RE_QUERY = re.compile(r'\.query\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_QUERY_FOR_OBJECT = re.compile(r'\.queryForObject\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_QUERY_FOR_LIST = re.compile(r'\.queryForList\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_QUERY_FOR_MAP = re.compile(r'\.queryForMap\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_QUERY_FOR_ROWSET = re.compile(r'\.queryForRowSet\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_QUERY_FOR_STREAM = re.compile(r'\.queryForStream\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_UPDATE = re.compile(r'\.update\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_BATCH_UPDATE = re.compile(r'\.batchUpdate\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_EXECUTE = re.compile(r'\.execute\s*\(\s*"([^"]+)"', re.DOTALL)

# Raw JDBC patterns
_RE_EXECUTE_QUERY = re.compile(r'\.executeQuery\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_EXECUTE_UPDATE = re.compile(r'\.executeUpdate\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_PREPARE_STATEMENT = re.compile(r'\.prepareStatement\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_PREPARE_CALL = re.compile(r'\.prepareCall\s*\(\s*"([^"]+)"', re.DOTALL)

# SQL string variable assignments: String sql = "SELECT ...";
_RE_SQL_VAR = re.compile(
    r'(?:String|final\s+String)\s+\w*[Ss]ql\w*\s*=\s*"([^"]+(?:"\s*\+\s*"[^"]+)*)"',
    re.DOTALL,
)

# All patterns grouped by access type
_QUERY_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (_RE_QUERY, "R", "query"),
    (_RE_QUERY_FOR_OBJECT, "R", "queryForObject"),
    (_RE_QUERY_FOR_LIST, "R", "queryForList"),
    (_RE_QUERY_FOR_MAP, "R", "queryForMap"),
    (_RE_QUERY_FOR_ROWSET, "R", "queryForRowSet"),
    (_RE_QUERY_FOR_STREAM, "R", "queryForStream"),
    (_RE_UPDATE, "W", "update"),
    (_RE_BATCH_UPDATE, "W", "batchUpdate"),
    (_RE_EXECUTE, "RW", "execute"),
    (_RE_EXECUTE_QUERY, "R", "executeQuery"),
    (_RE_EXECUTE_UPDATE, "W", "executeUpdate"),
    (_RE_PREPARE_STATEMENT, "RW", "prepareStatement"),
    (_RE_PREPARE_CALL, "RW", "prepareCall"),
]

# Method declaration for context
_RE_METHOD_DECL = re.compile(
    r"(?:public|protected|private)\s+[\w<>\[\],\s]+\s+(\w+)\s*\(",
)


class JdbcRegexAnalyzer:
    """Regex-based JDBC/Spring JDBC pattern extraction."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult:
        """Extract JDBC table mappings using regex. Always returns a result."""
        has_spring = bool(_RE_SPRING_JDBC.search(source_code))
        has_raw = bool(_RE_RAW_JDBC.search(source_code))

        if not has_spring and not has_raw:
            # Quick check for JdbcTemplate usage without explicit import
            if "JdbcTemplate" not in source_code and "prepareStatement" not in source_code:
                return FileAnalysisResult(source_file=file_path, package_name="", imports=[])

        pkg_match = re.search(r"^\s*package\s+([\w.]+)\s*;", source_code, re.MULTILINE)
        package_name = pkg_match.group(1) if pkg_match else ""

        framework = "Spring JDBC" if has_spring else "JDBC"
        class_name = self._find_primary_class(source_code)

        mappings: list[RawMapping] = []

        # Match all JDBC patterns
        for pattern, default_access, method_name in _QUERY_PATTERNS:
            for m in pattern.finditer(source_code):
                sql = m.group(1)
                # Clean string concatenation remnants
                sql = sql.replace('" + "', "").replace('"+"', "")
                method_ctx = self._find_enclosing_method(source_code, m.start())
                location = f"{class_name}.{method_ctx}" if method_ctx else class_name

                refs = self._sql_parser.parse(sql)
                if refs:
                    for ref in refs:
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_method=location,
                            access_type=ref.access_type,
                            framework=framework,
                            annotation=method_name,
                        ))
                else:
                    mappings.append(RawMapping(
                        table_name=f"[{method_name}]",
                        class_or_method=location,
                        access_type=default_access,
                        framework=framework,
                        annotation=method_name,
                    ))

        # Also check SQL string variable assignments
        for m in _RE_SQL_VAR.finditer(source_code):
            sql = m.group(1).replace('" + "', "").replace('"+"', "")
            method_ctx = self._find_enclosing_method(source_code, m.start())
            location = f"{class_name}.{method_ctx}" if method_ctx else class_name

            refs = self._sql_parser.parse(sql)
            for ref in refs:
                # Check if this table is already recorded from method calls
                key = (location, ref.table_name)
                existing = {(rm.class_or_method, rm.table_name) for rm in mappings}
                if key not in existing:
                    mappings.append(RawMapping(
                        table_name=ref.table_name,
                        class_or_method=location,
                        access_type=ref.access_type,
                        framework=framework,
                        annotation="SQL variable",
                    ))

        imports: list[str] = []
        if has_spring:
            imports.append("org.springframework.jdbc")
        if has_raw:
            imports.append("java.sql")

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=imports,
            mappings=mappings,
        )

    def _find_primary_class(self, source_code: str) -> str:
        m = re.search(r"public\s+(?:abstract\s+)?class\s+(\w+)", source_code)
        if m:
            return m.group(1)
        m = re.search(r"class\s+(\w+)", source_code)
        return m.group(1) if m else "Unknown"

    def _find_enclosing_method(self, source_code: str, position: int) -> str | None:
        preceding = source_code[:position]
        matches = list(_RE_METHOD_DECL.finditer(preceding))
        return matches[-1].group(1) if matches else None
