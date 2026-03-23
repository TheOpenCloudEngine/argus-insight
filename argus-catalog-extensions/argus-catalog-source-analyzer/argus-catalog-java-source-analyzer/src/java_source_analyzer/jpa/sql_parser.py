"""SQL string parser for extracting table names and access types.

Uses sqlglot as primary parser with regex fallback for unparseable SQL.
"""

from __future__ import annotations

import logging
import re

import sqlglot
from sqlglot import exp

from java_source_analyzer.models import SqlTableRef

logger = logging.getLogger(__name__)

# Regex patterns for SQL table extraction (fallback)
_RE_FROM = re.compile(
    r'\bFROM\s+([`"\']?[\w.]+[`"\']?)', re.IGNORECASE
)
_RE_JOIN = re.compile(
    r'\bJOIN\s+([`"\']?[\w.]+[`"\']?)', re.IGNORECASE
)
_RE_INSERT_INTO = re.compile(
    r'\bINSERT\s+INTO\s+([`"\']?[\w.]+[`"\']?)', re.IGNORECASE
)
_RE_UPDATE = re.compile(
    r'\bUPDATE\s+([`"\']?[\w.]+[`"\']?)', re.IGNORECASE
)
_RE_DELETE_FROM = re.compile(
    r'\bDELETE\s+FROM\s+([`"\']?[\w.]+[`"\']?)', re.IGNORECASE
)
_RE_MERGE_INTO = re.compile(
    r'\bMERGE\s+INTO\s+([`"\']?[\w.]+[`"\']?)', re.IGNORECASE
)

# JPQL patterns (entity names instead of table names)
_RE_JPQL_FROM = re.compile(
    r'\bFROM\s+([A-Z]\w+)', re.IGNORECASE
)

WRITE_STATEMENT_TYPES = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create)
READ_STATEMENT_TYPES = (exp.Select,)


def _clean_table_name(name: str) -> str:
    """Remove quotes and backticks from table name."""
    return name.strip("`\"'")


def _table_fqn(table: exp.Table) -> str:
    """Build fully qualified table name from sqlglot Table node."""
    parts = []
    if table.catalog:
        parts.append(table.catalog)
    if table.db:
        parts.append(table.db)
    if table.name:
        parts.append(table.name)
    return ".".join(parts)


class SqlParser:
    """Parses SQL/JPQL strings to extract table references with access types."""

    def parse(self, sql: str, is_jpql: bool = False) -> list[SqlTableRef]:
        """Extract table references from a SQL or JPQL string.

        Args:
            sql: The SQL or JPQL string to parse.
            is_jpql: If True, treat as JPQL (entity names = table names).

        Returns:
            List of SqlTableRef with table names and access types.
        """
        if not sql or not sql.strip():
            return []

        # Try sqlglot first
        refs = self._parse_with_sqlglot(sql)
        if refs is not None:
            return refs

        # Fallback to regex
        return self._parse_with_regex(sql)

    def _parse_with_sqlglot(self, sql: str) -> list[SqlTableRef] | None:
        """Parse SQL using sqlglot. Returns None on parse failure."""
        try:
            statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.IGNORE)
        except Exception:
            logger.debug("sqlglot parse failed for: %.100s", sql)
            return None

        if not statements or statements[0] is None:
            return None

        ast = statements[0]
        refs: list[SqlTableRef] = []
        seen: set[tuple[str, str]] = set()

        # Determine if this is a write statement
        is_write = isinstance(ast, WRITE_STATEMENT_TYPES)

        # Extract target tables (written to)
        target_names: set[str] = set()
        if isinstance(ast, exp.Insert):
            table = ast.find(exp.Table)
            if table:
                name = _table_fqn(table)
                target_names.add(name)
        elif isinstance(ast, (exp.Update, exp.Delete)):
            table = ast.find(exp.Table)
            if table:
                name = _table_fqn(table)
                target_names.add(name)
        elif isinstance(ast, exp.Merge):
            if isinstance(ast.this, exp.Table):
                name = _table_fqn(ast.this)
                target_names.add(name)
        elif isinstance(ast, exp.Create):
            schema = ast.this
            if isinstance(schema, exp.Schema):
                table = schema.this
            else:
                table = schema
            if isinstance(table, exp.Table):
                target_names.add(_table_fqn(table))

        # Add target tables as W
        for name in target_names:
            if name and (name, "W") not in seen:
                refs.append(SqlTableRef(table_name=name, access_type="W"))
                seen.add((name, "W"))

        # Extract all tables (source tables = R)
        for table in ast.find_all(exp.Table):
            name = _table_fqn(table)
            if not name:
                continue
            if name in target_names:
                continue  # already added as W
            if (name, "R") not in seen:
                refs.append(SqlTableRef(table_name=name, access_type="R"))
                seen.add((name, "R"))

        return refs if refs else None

    def _parse_with_regex(self, sql: str) -> list[SqlTableRef]:
        """Fallback regex-based SQL table extraction."""
        refs: list[SqlTableRef] = []
        seen: set[tuple[str, str]] = set()

        # Write targets
        for pattern in (_RE_INSERT_INTO, _RE_UPDATE, _RE_DELETE_FROM, _RE_MERGE_INTO):
            for match in pattern.finditer(sql):
                name = _clean_table_name(match.group(1))
                if name and (name, "W") not in seen:
                    refs.append(SqlTableRef(table_name=name, access_type="W"))
                    seen.add((name, "W"))

        # Read sources
        write_tables = {r.table_name for r in refs}
        for pattern in (_RE_FROM, _RE_JOIN):
            for match in pattern.finditer(sql):
                name = _clean_table_name(match.group(1))
                if not name or name.upper() in _SQL_KEYWORDS:
                    continue
                if name in write_tables:
                    continue
                if (name, "R") not in seen:
                    refs.append(SqlTableRef(table_name=name, access_type="R"))
                    seen.add((name, "R"))

        return refs


# SQL keywords that might appear after FROM/JOIN but aren't table names
_SQL_KEYWORDS = {
    "SELECT", "WHERE", "SET", "VALUES", "INTO", "AS", "ON",
    "AND", "OR", "NOT", "NULL", "IN", "EXISTS", "BETWEEN",
    "LIKE", "ORDER", "GROUP", "HAVING", "LIMIT", "OFFSET",
    "UNION", "EXCEPT", "INTERSECT", "DUAL",
}
