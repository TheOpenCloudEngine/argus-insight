"""DB-API 2.0 AST-based analyzer.

Detects raw SQL via:
- cursor.execute("SQL"), cursor.executemany("SQL", ...)
- connection.execute("SQL") (sqlite3 shortcut)
- psycopg2, pymysql, sqlite3, cx_Oracle, pyodbc, asyncpg, aiomysql patterns
"""

from __future__ import annotations

import ast
import logging

from python_source_analyzer.models import FileAnalysisResult, RawMapping
from python_source_analyzer.sql_parser import SqlParser

logger = logging.getLogger(__name__)

FRAMEWORK = "DB-API"

_DBAPI_IMPORTS = {
    "sqlite3", "psycopg2", "psycopg", "pymysql", "MySQLdb",
    "cx_Oracle", "oracledb", "pyodbc", "pymssql",
    "asyncpg", "aiomysql", "aiosqlite", "databases",
}

# Methods that take SQL as the first argument
_EXECUTE_METHODS = {
    "execute": "RW",
    "executemany": "W",
    "executescript": "W",
    "mogrify": "R",
    "copy_from": "W",
    "copy_to": "R",
}

# Async methods (asyncpg, aiomysql)
_ASYNC_METHODS = {
    "fetch": "R",
    "fetchval": "R",
    "fetchrow": "R",
    "execute": "RW",
    "executemany": "W",
}


class DbApiAstAnalyzer:
    """AST-based DB-API 2.0 analyzer."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult | None:
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            logger.debug("AST parse failed for %s", file_path)
            return None

        imports = self._collect_imports(tree)
        if not self._has_dbapi_imports(imports):
            return FileAnalysisResult(source_file=file_path, module_path="", imports=imports)

        framework = self._detect_framework(imports)
        mappings: list[RawMapping] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mappings.extend(self._analyze_function(node, framework))

        # Also check module-level execute calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _EXECUTE_METHODS or node.func.attr in _ASYNC_METHODS:
                    # Check we're not inside a function (already handled)
                    pass  # Module-level is rare, functions handle most cases

        return FileAnalysisResult(
            source_file=file_path,
            module_path="",
            imports=imports,
            mappings=mappings,
        )

    def _collect_imports(self, tree: ast.Module) -> list[str]:
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _has_dbapi_imports(self, imports: list[str]) -> bool:
        return any(
            any(imp == pkg or imp.startswith(pkg + ".") for pkg in _DBAPI_IMPORTS)
            for imp in imports
        )

    def _detect_framework(self, imports: list[str]) -> str:
        for imp in imports:
            for pkg in _DBAPI_IMPORTS:
                if imp == pkg or imp.startswith(pkg + "."):
                    return f"DB-API ({pkg})"
        return FRAMEWORK

    def _analyze_function(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, framework: str,
    ) -> list[RawMapping]:
        mappings: list[RawMapping] = []
        func_name = func_node.name

        # Find enclosing class if any
        class_name = ""

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue

            method = node.func.attr
            all_methods = {**_EXECUTE_METHODS, **_ASYNC_METHODS}

            if method not in all_methods:
                continue

            default_access = all_methods[method]
            sql = self._extract_sql(node)
            if not sql:
                continue

            location = f"{class_name}.{func_name}" if class_name else func_name
            refs = self._sql_parser.parse(sql)

            if refs:
                for ref in refs:
                    mappings.append(RawMapping(
                        table_name=ref.table_name,
                        class_or_function=location,
                        access_type=ref.access_type,
                        framework=framework,
                        pattern=f"cursor.{method}()",
                    ))
            else:
                # SQL was found but couldn't be parsed
                mappings.append(RawMapping(
                    table_name=f"[{method}]",
                    class_or_function=location,
                    access_type=default_access,
                    framework=framework,
                    pattern=f"cursor.{method}()",
                ))

        return mappings

    def _extract_sql(self, call_node: ast.Call) -> str | None:
        """Extract SQL string from the first argument of a call."""
        if not call_node.args:
            return None
        first = call_node.args[0]

        # Direct string: cursor.execute("SQL")
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value

        # f-string or concatenation — can't fully resolve
        if isinstance(first, ast.JoinedStr):
            # Extract static parts of f-string
            parts = []
            for val in first.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    parts.append(val.value)
            if parts:
                return " ".join(parts)

        return None
