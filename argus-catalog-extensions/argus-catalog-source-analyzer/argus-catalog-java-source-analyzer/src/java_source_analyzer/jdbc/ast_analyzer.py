"""JDBC AST-based analyzer using javalang.

Extracts table mappings from:
- Spring JdbcTemplate / NamedParameterJdbcTemplate method calls
- Raw JDBC: Statement.execute*, PreparedStatement, Connection.prepareStatement
"""

from __future__ import annotations

import logging

import javalang

from java_source_analyzer.jpa.sql_parser import SqlParser
from java_source_analyzer.models import FileAnalysisResult, RawMapping

logger = logging.getLogger(__name__)

# Spring JdbcTemplate methods that accept SQL as the first argument
_JDBC_TEMPLATE_QUERY_METHODS = {
    # Read methods
    "query": "R",
    "queryForObject": "R",
    "queryForList": "R",
    "queryForMap": "R",
    "queryForRowSet": "R",
    "queryForStream": "R",
    # Write methods
    "update": "W",
    "batchUpdate": "W",
    "execute": "RW",
}

# Raw JDBC methods that accept SQL
_RAW_JDBC_METHODS = {
    "executeQuery": "R",
    "executeUpdate": "W",
    "execute": "RW",
    "prepareStatement": "RW",
    "prepareCall": "RW",
    "addBatch": "W",
}

# Import prefixes for detection
_SPRING_JDBC_IMPORTS = (
    "org.springframework.jdbc",
)
_RAW_JDBC_IMPORTS = (
    "java.sql",
)


class JdbcAstAnalyzer:
    """AST-based analyzer for Spring JDBC and raw JDBC patterns."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult | None:
        """Parse source and extract JDBC table mappings.

        Returns None if the source cannot be parsed.
        """
        try:
            tree = javalang.parse.parse(source_code)
        except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError, Exception):
            logger.debug("javalang parse failed for %s", file_path)
            return None

        package_name = tree.package.name if tree.package else ""
        imports = [imp.path for imp in (tree.imports or [])]

        if not self._has_jdbc_imports(imports):
            return FileAnalysisResult(
                source_file=file_path,
                package_name=package_name,
                imports=imports,
            )

        framework = self._detect_framework(imports)
        mappings: list[RawMapping] = []

        for type_decl in tree.types or []:
            if isinstance(type_decl, javalang.tree.ClassDeclaration):
                mappings.extend(self._analyze_class(type_decl, framework))

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=imports,
            mappings=mappings,
        )

    def _has_jdbc_imports(self, imports: list[str]) -> bool:
        return any(
            any(imp.startswith(prefix) for prefix in (*_SPRING_JDBC_IMPORTS, *_RAW_JDBC_IMPORTS))
            for imp in imports
        )

    def _detect_framework(self, imports: list[str]) -> str:
        has_spring = any(
            imp.startswith(prefix) for imp in imports for prefix in _SPRING_JDBC_IMPORTS
        )
        has_raw = any(
            imp.startswith(prefix) for imp in imports for prefix in _RAW_JDBC_IMPORTS
        )
        if has_spring and has_raw:
            return "Spring JDBC"
        if has_spring:
            return "Spring JDBC"
        return "JDBC"

    def _analyze_class(
        self, class_decl: javalang.tree.ClassDeclaration, framework: str,
    ) -> list[RawMapping]:
        mappings: list[RawMapping] = []
        class_name = class_decl.name

        for method in class_decl.methods or []:
            if method.body is None:
                continue
            method_name = method.name

            for _, node in method.filter(javalang.tree.MethodInvocation):
                access = None

                # Spring JdbcTemplate methods
                if node.member in _JDBC_TEMPLATE_QUERY_METHODS:
                    access = _JDBC_TEMPLATE_QUERY_METHODS[node.member]
                # Raw JDBC methods
                elif node.member in _RAW_JDBC_METHODS:
                    access = _RAW_JDBC_METHODS[node.member]

                if access is None:
                    continue

                sql = self._extract_string_argument(node)
                if not sql:
                    continue

                location = f"{class_name}.{method_name}"
                refs = self._sql_parser.parse(sql)

                if refs:
                    for ref in refs:
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_method=location,
                            access_type=ref.access_type,
                            framework=framework,
                            annotation=node.member,
                        ))
                else:
                    # Record the method call even if SQL parsing fails
                    mappings.append(RawMapping(
                        table_name=f"[{node.member}]",
                        class_or_method=location,
                        access_type=access,
                        framework=framework,
                        annotation=node.member,
                    ))

        return mappings

    def _extract_string_argument(
        self, invocation: javalang.tree.MethodInvocation,
    ) -> str | None:
        """Extract the first string literal argument from a method call."""
        if not invocation.arguments:
            return None

        first_arg = invocation.arguments[0]
        if isinstance(first_arg, javalang.tree.Literal):
            return self._unquote(first_arg.value)

        if isinstance(first_arg, javalang.tree.BinaryOperation):
            return self._concat_string_parts(first_arg)

        # Variable reference — can't resolve statically
        if isinstance(first_arg, javalang.tree.MemberReference):
            return None

        return None

    def _concat_string_parts(self, expr: javalang.tree.BinaryOperation) -> str | None:
        parts: list[str] = []
        self._collect_string_parts(expr, parts)
        return "".join(parts) if parts else None

    def _collect_string_parts(self, expr: javalang.tree.Node, parts: list[str]) -> None:
        if isinstance(expr, javalang.tree.Literal):
            val = self._unquote(expr.value)
            if val is not None:
                parts.append(val)
        elif isinstance(expr, javalang.tree.BinaryOperation):
            if hasattr(expr, "operandl"):
                self._collect_string_parts(expr.operandl, parts)
            if hasattr(expr, "operandr"):
                self._collect_string_parts(expr.operandr, parts)

    @staticmethod
    def _unquote(value: str) -> str | None:
        if value and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return None
