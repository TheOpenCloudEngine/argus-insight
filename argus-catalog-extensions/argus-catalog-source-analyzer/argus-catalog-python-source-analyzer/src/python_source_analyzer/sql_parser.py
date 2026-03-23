"""SQL string parser for extracting table names and access types.

Uses sqlglot as primary parser with regex fallback.
Shared across all Python framework analyzers.
"""

from __future__ import annotations

import logging
import re

import sqlglot
from sqlglot import exp

from python_source_analyzer.models import SqlTableRef

logger = logging.getLogger(__name__)

_RE_FROM = re.compile(r"\bFROM\s+([`\"']?[\w.]+[`\"']?)", re.IGNORECASE)
_RE_JOIN = re.compile(r"\bJOIN\s+([`\"']?[\w.]+[`\"']?)", re.IGNORECASE)
_RE_INSERT_INTO = re.compile(r"\bINSERT\s+INTO\s+([`\"']?[\w.]+[`\"']?)", re.IGNORECASE)
_RE_UPDATE = re.compile(r"\bUPDATE\s+([`\"']?[\w.]+[`\"']?)", re.IGNORECASE)
_RE_DELETE_FROM = re.compile(r"\bDELETE\s+FROM\s+([`\"']?[\w.]+[`\"']?)", re.IGNORECASE)
_RE_MERGE_INTO = re.compile(r"\bMERGE\s+INTO\s+([`\"']?[\w.]+[`\"']?)", re.IGNORECASE)

_SQL_KEYWORDS = {
    "SELECT", "WHERE", "SET", "VALUES", "INTO", "AS", "ON",
    "AND", "OR", "NOT", "NULL", "IN", "EXISTS", "BETWEEN",
    "LIKE", "ORDER", "GROUP", "HAVING", "LIMIT", "OFFSET",
    "UNION", "EXCEPT", "INTERSECT", "DUAL",
}

WRITE_TYPES = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create)


def _clean(name: str) -> str:
    return name.strip("`\"'")


def _table_fqn(table: exp.Table) -> str:
    parts = []
    if table.catalog:
        parts.append(table.catalog)
    if table.db:
        parts.append(table.db)
    if table.name:
        parts.append(table.name)
    return ".".join(parts)


class SqlParser:
    """Parses SQL strings to extract table references with access types."""

    def parse(self, sql: str) -> list[SqlTableRef]:
        if not sql or not sql.strip():
            return []
        refs = self._parse_with_sqlglot(sql)
        if refs is not None:
            return refs
        return self._parse_with_regex(sql)

    def _parse_with_sqlglot(self, sql: str) -> list[SqlTableRef] | None:
        try:
            statements = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.IGNORE)
        except Exception:
            return None
        if not statements or statements[0] is None:
            return None

        ast = statements[0]
        refs: list[SqlTableRef] = []
        seen: set[tuple[str, str]] = set()

        target_names: set[str] = set()
        if isinstance(ast, exp.Insert):
            t = ast.find(exp.Table)
            if t:
                target_names.add(_table_fqn(t))
        elif isinstance(ast, (exp.Update, exp.Delete)):
            t = ast.find(exp.Table)
            if t:
                target_names.add(_table_fqn(t))
        elif isinstance(ast, exp.Merge):
            if isinstance(ast.this, exp.Table):
                target_names.add(_table_fqn(ast.this))
        elif isinstance(ast, exp.Create):
            s = ast.this
            if isinstance(s, exp.Schema):
                s = s.this
            if isinstance(s, exp.Table):
                target_names.add(_table_fqn(s))

        for name in target_names:
            if name and (name, "W") not in seen:
                refs.append(SqlTableRef(table_name=name, access_type="W"))
                seen.add((name, "W"))

        for table in ast.find_all(exp.Table):
            name = _table_fqn(table)
            if not name or name in target_names:
                continue
            if (name, "R") not in seen:
                refs.append(SqlTableRef(table_name=name, access_type="R"))
                seen.add((name, "R"))

        return refs if refs else None

    def _parse_with_regex(self, sql: str) -> list[SqlTableRef]:
        refs: list[SqlTableRef] = []
        seen: set[tuple[str, str]] = set()

        for pattern in (_RE_INSERT_INTO, _RE_UPDATE, _RE_DELETE_FROM, _RE_MERGE_INTO):
            for m in pattern.finditer(sql):
                name = _clean(m.group(1))
                if name and (name, "W") not in seen:
                    refs.append(SqlTableRef(table_name=name, access_type="W"))
                    seen.add((name, "W"))

        write_tables = {r.table_name for r in refs}
        for pattern in (_RE_FROM, _RE_JOIN):
            for m in pattern.finditer(sql):
                name = _clean(m.group(1))
                if not name or name.upper() in _SQL_KEYWORDS or name in write_tables:
                    continue
                if (name, "R") not in seen:
                    refs.append(SqlTableRef(table_name=name, access_type="R"))
                    seen.add((name, "R"))
        return refs
