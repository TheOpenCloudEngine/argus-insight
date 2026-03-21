"""Impala SQL lineage parser.

Uses sqlglot's Hive dialect with Impala-specific pre-processing to extract
table-level and column-level lineage from Impala queries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from sqlglot_impala.preprocessor import is_lineage_relevant, preprocess

logger = logging.getLogger(__name__)


@dataclass
class ColumnRef:
    """A reference to a column in a specific table."""

    table: str
    column: str


@dataclass
class ColumnLineageEntry:
    """Mapping from source column to target column."""

    source: ColumnRef
    target: ColumnRef
    transform_type: str  # DIRECT, AGGREGATION, EXPRESSION


@dataclass
class JoinInfo:
    """JOIN relationship between tables."""

    left_table: str
    right_table: str
    join_type: str
    condition: str


@dataclass
class QueryLineageResult:
    """Complete lineage information extracted from a single SQL query."""

    source_tables: list[str] = field(default_factory=list)
    target_tables: list[str] = field(default_factory=list)
    joins: list[JoinInfo] = field(default_factory=list)
    column_lineages: list[ColumnLineageEntry] = field(default_factory=list)


class ImpalaLineageParser:
    """Impala SQL lineage parser using sqlglot Hive dialect with pre-processing."""

    DIALECT = "hive"

    AGGREGATE_FUNCTIONS = {
        "SUM", "COUNT", "AVG", "MIN", "MAX",
        "STDDEV", "VARIANCE", "STDDEV_POP", "STDDEV_SAMP",
        "VAR_POP", "VAR_SAMP", "NDV", "APPX_MEDIAN",
        "GROUP_CONCAT",
        "FIRST_VALUE", "LAST_VALUE", "LEAD", "LAG",
        "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE",
    }

    WRITE_OPERATIONS = (exp.Insert, exp.Create, exp.Merge)

    def parse(self, sql: str) -> QueryLineageResult | None:
        """Parse an Impala SQL statement and extract lineage information.

        Returns None if the SQL cannot be parsed or is not a lineage-relevant statement.
        """
        if not is_lineage_relevant(sql):
            return None

        processed = preprocess(sql)

        try:
            statements = sqlglot.parse(processed, dialect=self.DIALECT)
        except sqlglot.errors.ParseError:
            logger.warning("Failed to parse Impala SQL: %.200s", sql)
            return None

        if not statements:
            return None

        ast = statements[0]
        if ast is None:
            return None

        if not self._is_lineage_relevant(ast):
            return None

        result = QueryLineageResult()
        result.target_tables = self._extract_target_tables(ast)
        result.source_tables = self._extract_source_tables(ast)
        result.joins = self._extract_joins(ast)
        result.column_lineages = self._extract_column_lineage(ast, result.target_tables)

        return result

    def _is_lineage_relevant(self, ast: exp.Expression) -> bool:
        """Check if the parsed AST produces data lineage."""
        if isinstance(ast, (exp.Select, exp.Merge)):
            return True
        if isinstance(ast, exp.Insert):
            return True
        if isinstance(ast, exp.Create):
            return ast.find(exp.Select) is not None
        return False

    def _extract_target_tables(self, ast: exp.Expression) -> list[str]:
        """Extract tables written to."""
        targets: list[str] = []

        if isinstance(ast, exp.Insert):
            table = ast.find(exp.Table)
            if table:
                targets.append(self._table_name(table))
        elif isinstance(ast, exp.Create):
            table = ast.this
            if isinstance(table, exp.Schema):
                table = table.this
            if isinstance(table, exp.Table):
                targets.append(self._table_name(table))
        elif isinstance(ast, exp.Merge):
            table = ast.this
            if isinstance(table, exp.Table):
                targets.append(self._table_name(table))

        return list(dict.fromkeys(targets))

    def _extract_source_tables(self, ast: exp.Expression) -> list[str]:
        """Extract tables read from."""
        sources: list[str] = []
        target_set = set(self._extract_target_tables(ast))

        select = ast.find(exp.Select)
        if select is None:
            return sources

        for table in select.find_all(exp.Table):
            name = self._table_name(table)
            if name and name not in target_set:
                sources.append(name)

        return list(dict.fromkeys(sources))

    def _extract_joins(self, ast: exp.Expression) -> list[JoinInfo]:
        """Extract JOIN relationships."""
        joins: list[JoinInfo] = []
        alias_map = self._build_alias_map(ast)

        for join_node in ast.find_all(exp.Join):
            join_type = self._get_join_type(join_node)
            right_table_node = join_node.find(exp.Table)
            if not right_table_node:
                continue
            right_table = self._table_name(right_table_node)

            left_table = ""
            on_clause = join_node.args.get("on")
            condition_str = ""
            if on_clause:
                condition_str = on_clause.sql(dialect=self.DIALECT)
                for col in on_clause.find_all(exp.Column):
                    resolved = self._resolve_table(col, alias_map)
                    if resolved and resolved != right_table:
                        left_table = resolved
                        break

            joins.append(JoinInfo(
                left_table=left_table,
                right_table=right_table,
                join_type=join_type,
                condition=condition_str,
            ))

        return joins

    def _extract_column_lineage(
        self, ast: exp.Expression, target_tables: list[str],
    ) -> list[ColumnLineageEntry]:
        """Extract column-level lineage."""
        entries: list[ColumnLineageEntry] = []
        alias_map = self._build_alias_map(ast)

        select = ast.find(exp.Select)
        if select is None:
            return entries

        target_table = target_tables[0] if target_tables else ""
        target_columns = self._get_insert_columns(ast)

        for i, select_expr in enumerate(select.expressions):
            if target_columns and i < len(target_columns):
                target_col_name = target_columns[i]
            elif isinstance(select_expr, exp.Alias):
                target_col_name = select_expr.alias
            elif isinstance(select_expr, exp.Column):
                target_col_name = select_expr.name
            else:
                target_col_name = f"_col{i}"

            target_ref = ColumnRef(table=target_table, column=target_col_name)
            actual_expr = select_expr.this if isinstance(select_expr, exp.Alias) else select_expr
            source_cols = self._extract_source_columns(actual_expr, alias_map)
            transform = self._classify_transform(actual_expr)

            if source_cols:
                for src in source_cols:
                    entries.append(ColumnLineageEntry(
                        source=src, target=target_ref, transform_type=transform,
                    ))
            elif target_table:
                entries.append(ColumnLineageEntry(
                    source=ColumnRef(table="", column="*"),
                    target=target_ref,
                    transform_type="EXPRESSION",
                ))

        return entries

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _table_name(self, table: exp.Table) -> str:
        parts = []
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        return ".".join(parts)

    def _build_alias_map(self, ast: exp.Expression) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for table in ast.find_all(exp.Table):
            name = self._table_name(table)
            if table.alias:
                alias_map[table.alias] = name
            if name:
                alias_map[name] = name
        return alias_map

    def _resolve_table(self, col: exp.Column, alias_map: dict[str, str]) -> str:
        if col.table:
            return alias_map.get(col.table, col.table)
        return ""

    def _get_join_type(self, join_node: exp.Join) -> str:
        if join_node.side:
            return f"{join_node.side} JOIN"
        if join_node.kind:
            return f"{join_node.kind} JOIN"
        return "JOIN"

    def _get_insert_columns(self, ast: exp.Expression) -> list[str]:
        if not isinstance(ast, exp.Insert):
            return []
        schema = ast.find(exp.Schema)
        if schema is None:
            return []
        columns: list[str] = []
        for expr in schema.expressions:
            if isinstance(expr, (exp.Column, exp.Identifier, exp.ColumnDef)):
                columns.append(expr.name)
        return columns

    def _extract_source_columns(
        self, expr: exp.Expression, alias_map: dict[str, str],
    ) -> list[ColumnRef]:
        refs: list[ColumnRef] = []
        for col in expr.find_all(exp.Column):
            table = self._resolve_table(col, alias_map)
            refs.append(ColumnRef(table=table, column=col.name))
        return refs

    def _classify_transform(self, expr: exp.Expression) -> str:
        if isinstance(expr, exp.Column):
            return "DIRECT"
        for func_node in expr.find_all(exp.Func):
            func_name = type(func_node).__name__.upper()
            if func_name in self.AGGREGATE_FUNCTIONS:
                return "AGGREGATION"
            if isinstance(func_node, exp.Anonymous):
                if func_node.name.upper() in self.AGGREGATE_FUNCTIONS:
                    return "AGGREGATION"
        if expr.find(exp.Window):
            return "AGGREGATION"
        if expr.find(exp.Case) or expr.find(exp.If):
            return "EXPRESSION"
        if expr.find(exp.Func) or expr.find(exp.Binary):
            return "EXPRESSION"
        return "DIRECT"
