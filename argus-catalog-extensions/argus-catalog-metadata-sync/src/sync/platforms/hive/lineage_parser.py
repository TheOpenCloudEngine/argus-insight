"""Hive SQL lineage parser using SQLGlot.

Parses Hive queries to extract:
- Source tables (read from)
- Target tables (written to)
- JOIN relationships
- Column-level lineage (source column → target column)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

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
    transform_type: str  # DIRECT, AGGREGATION, EXPRESSION, JOIN_KEY


@dataclass
class JoinInfo:
    """JOIN relationship between tables."""

    left_table: str
    right_table: str
    join_type: str  # INNER, LEFT, RIGHT, FULL, CROSS
    condition: str


@dataclass
class QueryLineageResult:
    """Complete lineage information extracted from a single SQL query."""

    source_tables: list[str] = field(default_factory=list)
    target_tables: list[str] = field(default_factory=list)
    joins: list[JoinInfo] = field(default_factory=list)
    column_lineages: list[ColumnLineageEntry] = field(default_factory=list)


class HiveLineageParser:
    """Hive SQL lineage parser using SQLGlot AST."""

    WRITE_OPERATIONS = (
        exp.Insert,
        exp.Create,
        exp.Merge,
    )

    AGGREGATE_FUNCTIONS = {
        "SUM", "COUNT", "AVG", "MIN", "MAX",
        "STDDEV", "VARIANCE", "COLLECT_LIST", "COLLECT_SET",
        "PERCENTILE", "PERCENTILE_APPROX", "NTILE",
        "FIRST_VALUE", "LAST_VALUE", "LEAD", "LAG",
        "ROW_NUMBER", "RANK", "DENSE_RANK",
    }

    def parse(self, sql: str) -> QueryLineageResult | None:
        """Parse a Hive SQL statement and extract lineage information.

        Returns None if the SQL cannot be parsed or is not a lineage-relevant statement.
        """
        try:
            statements = sqlglot.parse(sql, dialect="hive")
        except sqlglot.errors.ParseError:
            logger.warning("Failed to parse SQL: %.200s", sql)
            return None

        if not statements:
            return None

        # Process only the first statement
        ast = statements[0]
        if ast is None:
            return None

        # Skip non-lineage statements (DDL-only, USE, SET, etc.)
        if not self._is_lineage_relevant(ast):
            return None

        result = QueryLineageResult()
        result.target_tables = self._extract_target_tables(ast)
        result.source_tables = self._extract_source_tables(ast)
        result.joins = self._extract_joins(ast)
        result.column_lineages = self._extract_column_lineage(ast, result.target_tables)

        # Extract JOIN key columns and add as JOIN_KEY lineage entries
        join_key_entries = self._extract_join_key_columns(ast)
        result.column_lineages.extend(join_key_entries)

        return result

    def _is_lineage_relevant(self, ast: exp.Expression) -> bool:
        """Check if the statement produces data lineage (SELECT, INSERT, CTAS, MERGE)."""
        if isinstance(ast, (exp.Select, exp.Merge)):
            return True
        if isinstance(ast, exp.Insert):
            return True
        if isinstance(ast, exp.Create):
            # CREATE TABLE ... AS SELECT
            return ast.find(exp.Select) is not None
        return False

    def _extract_target_tables(self, ast: exp.Expression) -> list[str]:
        """Extract tables that are written to (INSERT INTO, CREATE TABLE AS, MERGE INTO)."""
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
        """Extract tables that are read from (FROM, JOIN clauses)."""
        sources: list[str] = []
        target_set = set(self._extract_target_tables(ast))

        # Find the SELECT part
        select = ast.find(exp.Select)
        if select is None:
            return sources

        # Walk the FROM and JOIN to find all source tables
        for table in select.find_all(exp.Table):
            name = self._table_name(table)
            if name and name not in target_set:
                sources.append(name)

        return list(dict.fromkeys(sources))

    def _extract_joins(self, ast: exp.Expression) -> list[JoinInfo]:
        """Extract JOIN relationships with conditions."""
        joins: list[JoinInfo] = []
        alias_map = self._build_alias_map(ast)

        for join_node in ast.find_all(exp.Join):
            join_type = self._get_join_type(join_node)
            right_table_node = join_node.find(exp.Table)
            if not right_table_node:
                continue
            right_table = self._table_name(right_table_node)

            # Try to resolve the left side from the ON condition
            left_table = ""
            on_clause = join_node.args.get("on")
            condition_str = ""
            if on_clause:
                condition_str = on_clause.sql(dialect="hive")
                # Find columns in the ON clause to determine the left table
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

    def _extract_join_key_columns(self, ast: exp.Expression) -> list[ColumnLineageEntry]:
        """Extract JOIN ON columns as JOIN_KEY lineage entries.

        For ``... FROM a JOIN b ON a.id = b.id``, produces:
        ColumnLineageEntry(source=a.id, target=b.id, transform_type='JOIN_KEY')
        """
        entries: list[ColumnLineageEntry] = []
        alias_map = self._build_alias_map(ast)

        for join_node in ast.find_all(exp.Join):
            on_clause = join_node.args.get("on")
            if on_clause is None:
                continue

            # Find all EQ comparisons in the ON clause
            for eq in on_clause.find_all(exp.EQ):
                left_expr = eq.left
                right_expr = eq.right

                if not isinstance(left_expr, exp.Column) or not isinstance(right_expr, exp.Column):
                    continue

                left_table = self._resolve_table(left_expr, alias_map)
                right_table = self._resolve_table(right_expr, alias_map)

                entries.append(ColumnLineageEntry(
                    source=ColumnRef(table=left_table, column=left_expr.name),
                    target=ColumnRef(table=right_table, column=right_expr.name),
                    transform_type="JOIN_KEY",
                ))

        return entries

    def _extract_column_lineage(
        self, ast: exp.Expression, target_tables: list[str],
    ) -> list[ColumnLineageEntry]:
        """Extract column-level lineage from SELECT → INSERT/CREATE mappings."""
        entries: list[ColumnLineageEntry] = []
        alias_map = self._build_alias_map(ast)

        select = ast.find(exp.Select)
        if select is None:
            return entries

        target_table = target_tables[0] if target_tables else ""

        # Get target column names from INSERT INTO ... (col1, col2, ...)
        target_columns = self._get_insert_columns(ast)

        for i, select_expr in enumerate(select.expressions):
            # Determine the target column name
            if target_columns and i < len(target_columns):
                target_col_name = target_columns[i]
            elif isinstance(select_expr, exp.Alias):
                target_col_name = select_expr.alias
            elif isinstance(select_expr, exp.Column):
                target_col_name = select_expr.name
            else:
                target_col_name = f"_col{i}"

            target_ref = ColumnRef(table=target_table, column=target_col_name)

            # Extract source columns from the expression
            actual_expr = select_expr.this if isinstance(select_expr, exp.Alias) else select_expr
            source_cols = self._extract_source_columns(actual_expr, alias_map)
            transform = self._classify_transform(actual_expr)

            if source_cols:
                for src in source_cols:
                    entries.append(ColumnLineageEntry(
                        source=src,
                        target=target_ref,
                        transform_type=transform,
                    ))
            elif target_table:
                # Constant or expression without column references
                entries.append(ColumnLineageEntry(
                    source=ColumnRef(table="", column="*"),
                    target=target_ref,
                    transform_type="EXPRESSION",
                ))

        return entries

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _table_name(self, table: exp.Table) -> str:
        """Build a fully qualified table name: db.table."""
        parts = []
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        return ".".join(parts)

    def _build_alias_map(self, ast: exp.Expression) -> dict[str, str]:
        """Build a mapping from table alias → qualified table name."""
        alias_map: dict[str, str] = {}
        for table in ast.find_all(exp.Table):
            name = self._table_name(table)
            if table.alias:
                alias_map[table.alias] = name
            if name:
                alias_map[name] = name
        return alias_map

    def _resolve_table(self, col: exp.Column, alias_map: dict[str, str]) -> str:
        """Resolve a column's table reference using the alias map."""
        if col.table:
            return alias_map.get(col.table, col.table)
        return ""

    def _get_join_type(self, join_node: exp.Join) -> str:
        """Determine the JOIN type from the AST node."""
        if join_node.side:
            return f"{join_node.side} JOIN"
        if join_node.kind:
            return f"{join_node.kind} JOIN"
        return "JOIN"

    def _get_insert_columns(self, ast: exp.Expression) -> list[str]:
        """Get explicitly listed column names from INSERT INTO t (col1, col2, ...)."""
        if not isinstance(ast, exp.Insert):
            return []

        schema = ast.find(exp.Schema)
        if schema is None:
            return []

        columns: list[str] = []
        for expr in schema.expressions:
            if isinstance(expr, exp.Column):
                columns.append(expr.name)
            elif isinstance(expr, (exp.Identifier, exp.ColumnDef)):
                columns.append(expr.name)
        return columns

    def _extract_source_columns(
        self, expr: exp.Expression, alias_map: dict[str, str],
    ) -> list[ColumnRef]:
        """Extract all column references from an expression."""
        refs: list[ColumnRef] = []
        for col in expr.find_all(exp.Column):
            table = self._resolve_table(col, alias_map)
            refs.append(ColumnRef(table=table, column=col.name))
        return refs

    def _classify_transform(self, expr: exp.Expression) -> str:
        """Classify the transformation type of a SELECT expression."""
        if isinstance(expr, exp.Column):
            return "DIRECT"

        # Check for aggregate functions
        for func_node in expr.find_all(exp.Func):
            func_name = type(func_node).__name__.upper()
            # SQLGlot maps SQL functions to class names (Sum, Count, etc.)
            if func_name in self.AGGREGATE_FUNCTIONS:
                return "AGGREGATION"
            # Also check the raw function name for UDFs
            if isinstance(func_node, exp.Anonymous):
                if func_node.name.upper() in self.AGGREGATE_FUNCTIONS:
                    return "AGGREGATION"

        # Check for window functions
        if expr.find(exp.Window):
            return "AGGREGATION"

        # Check for CASE, IF, COALESCE etc.
        if expr.find(exp.Case) or expr.find(exp.If):
            return "EXPRESSION"

        # Any other function or arithmetic
        if expr.find(exp.Func) or expr.find(exp.Binary):
            return "EXPRESSION"

        return "DIRECT"
