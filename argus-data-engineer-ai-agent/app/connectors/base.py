"""Abstract base for database connectors.

All connectors implement read-only query execution and metadata retrieval.
Write operations are intentionally excluded — the agent generates code, not executes DML.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class QueryResult:
    """Result of a SQL query execution."""

    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "error": self.error,
        }

    def to_table_str(self, max_col_width: int = 50) -> str:
        """Render as a simple text table for LLM consumption."""
        if self.error:
            return f"Error: {self.error}"
        if not self.rows:
            return "Empty result set."

        # Truncate long values
        def trunc(val, width=max_col_width):
            s = str(val) if val is not None else "NULL"
            return s[:width] + "..." if len(s) > width else s

        headers = [trunc(c, 30) for c in self.columns]
        data = [[trunc(v) for v in row] for row in self.rows]

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in data:
            for i, v in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(v))

        def fmt_row(vals):
            return " | ".join(v.ljust(widths[i]) for i, v in enumerate(vals))

        lines = [fmt_row(headers)]
        lines.append("-+-".join("-" * w for w in widths))
        for row in data:
            lines.append(fmt_row(row))

        if self.truncated:
            lines.append(f"... (truncated, showing {len(self.rows)} of {self.row_count} rows)")
        return "\n".join(lines)


class DBConnector(ABC):
    """Abstract database connector for read-only operations."""

    @abstractmethod
    async def execute_query(
        self,
        sql: str,
        max_rows: int = 100,
    ) -> QueryResult:
        """Execute a read-only SQL query and return results.

        Args:
            sql: SQL query to execute (must be SELECT or EXPLAIN).
            max_rows: Maximum rows to return.

        Returns:
            QueryResult with columns, rows, and metadata.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release connection resources."""
        ...

    def _validate_read_only(self, sql: str) -> str | None:
        """Validate that the SQL is read-only. Returns error message if not."""
        normalized = sql.strip().upper()

        # Allow SELECT and EXPLAIN only
        if normalized.startswith(("SELECT", "EXPLAIN", "SHOW", "DESCRIBE", "DESC")):
            return None

        # Block everything else
        blocked = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
            "MERGE",
            "CALL",
            "EXEC",
        ]
        for keyword in blocked:
            if normalized.startswith(keyword):
                return f"Blocked: {keyword} statements are not allowed. Read-only mode."

        return "Only SELECT, EXPLAIN, SHOW, and DESCRIBE statements are allowed."
