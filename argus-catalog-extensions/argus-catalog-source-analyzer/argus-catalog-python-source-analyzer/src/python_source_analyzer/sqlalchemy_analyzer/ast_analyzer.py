"""SQLAlchemy AST-based analyzer using Python's built-in ast module.

Detects:
- Declarative ORM: __tablename__, Column, relationship, mapped_column
- Core: Table("name", metadata, ...), select(), insert(), update(), delete()
- Session: session.query(), session.add(), session.delete(), session.execute(text("SQL"))
"""

from __future__ import annotations

import ast
import logging

from python_source_analyzer.models import FileAnalysisResult, RawMapping
from python_source_analyzer.sql_parser import SqlParser

logger = logging.getLogger(__name__)

FRAMEWORK = "SQLAlchemy"

# session/connection method -> access type
_SESSION_METHODS: dict[str, str] = {
    "add": "W",
    "add_all": "W",
    "delete": "W",
    "merge": "W",
    "bulk_save_objects": "W",
    "bulk_insert_mappings": "W",
    "bulk_update_mappings": "W",
    "query": "R",
    "get": "R",
    "refresh": "R",
    "execute": "RW",
}

# SQLAlchemy Core DML functions
_CORE_DML: dict[str, str] = {
    "select": "R",
    "insert": "W",
    "update": "W",
    "delete": "W",
}

# Known SQLAlchemy base classes
_SA_BASES = {
    "Base", "DeclarativeBase", "DeclarativeMeta",
    "MappedAsDataclass", "AsyncAttrs",
}

_SA_IMPORTS = {"sqlalchemy", "sqlmodel"}


class SqlAlchemyAstAnalyzer:
    """AST-based SQLAlchemy analyzer."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult | None:
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            logger.debug("AST parse failed for %s", file_path)
            return None

        imports = self._collect_imports(tree)
        if not self._has_sqlalchemy_imports(imports):
            return FileAnalysisResult(source_file=file_path, module_path="", imports=imports)

        mappings: list[RawMapping] = []

        for node in ast.walk(tree):
            # Class-level: __tablename__, Table()
            if isinstance(node, ast.ClassDef):
                mappings.extend(self._analyze_class(node))

            # Module-level Table() definitions
            elif isinstance(node, ast.Assign):
                mappings.extend(self._analyze_assignment(node, "<module>"))

            # Function-level session/connection calls
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mappings.extend(self._analyze_function(node))

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

    def _has_sqlalchemy_imports(self, imports: list[str]) -> bool:
        return any(
            any(imp.startswith(prefix) for prefix in _SA_IMPORTS)
            for imp in imports
        )

    def _analyze_class(self, class_node: ast.ClassDef) -> list[RawMapping]:
        mappings: list[RawMapping] = []
        class_name = class_node.name

        # Check if this extends a known SA base
        if not self._is_sa_model(class_node):
            return mappings

        table_name = None
        for node in class_node.body:
            # __tablename__ = "users"
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            table_name = node.value.value
                            mappings.append(RawMapping(
                                table_name=table_name,
                                class_or_function=class_name,
                                access_type="RW",
                                framework=FRAMEWORK,
                                pattern="__tablename__",
                            ))

            # Check for methods with session calls
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for m in self._analyze_function(node, class_name):
                    mappings.append(m)

        # If @Entity-like class without __tablename__, use class name
        if table_name is None and self._is_sa_model(class_node):
            # Check if it's not an abstract base
            has_abstract = False
            for item in class_node.body:
                if isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name) and t.id == "__abstract__":
                            has_abstract = True
            if not has_abstract:
                mappings.append(RawMapping(
                    table_name=class_name.lower(),
                    class_or_function=class_name,
                    access_type="RW",
                    framework=FRAMEWORK,
                    pattern="class(Base)",
                ))

        return mappings

    def _is_sa_model(self, class_node: ast.ClassDef) -> bool:
        """Check if a class extends a SQLAlchemy base."""
        for base in class_node.bases:
            if isinstance(base, ast.Name) and base.id in _SA_BASES:
                return True
            if isinstance(base, ast.Attribute):
                if base.attr in _SA_BASES:
                    return True
        # Check for __tablename__ assignment as a strong signal
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        return True
        return False

    def _analyze_assignment(self, node: ast.Assign, context: str) -> list[RawMapping]:
        """Detect Table("name", metadata, ...) at module level."""
        mappings: list[RawMapping] = []
        if isinstance(node.value, ast.Call):
            func = node.value.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr

            if func_name == "Table" and node.value.args:
                first_arg = node.value.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    # Variable name for context
                    var_name = ""
                    if node.targets and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                    mappings.append(RawMapping(
                        table_name=first_arg.value,
                        class_or_function=var_name or context,
                        access_type="RW",
                        framework=FRAMEWORK,
                        pattern="Table()",
                    ))
        return mappings

    def _analyze_function(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str = "",
    ) -> list[RawMapping]:
        """Analyze function body for session/connection/DML calls."""
        mappings: list[RawMapping] = []
        func_name = func_node.name
        location = f"{class_name}.{func_name}" if class_name else func_name

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            # session.add(obj), session.query(Model), etc.
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

                if method_name in _SESSION_METHODS:
                    access = _SESSION_METHODS[method_name]
                    mappings.append(RawMapping(
                        table_name=f"[session.{method_name}]",
                        class_or_function=location,
                        access_type=access,
                        framework=FRAMEWORK,
                        pattern=f"session.{method_name}",
                    ))

                # connection.execute(text("SQL"))
                if method_name == "execute":
                    sql = self._extract_text_sql(node)
                    if sql:
                        refs = self._sql_parser.parse(sql)
                        for ref in refs:
                            mappings.append(RawMapping(
                                table_name=ref.table_name,
                                class_or_function=location,
                                access_type=ref.access_type,
                                framework=FRAMEWORK,
                                pattern="execute(text())",
                            ))

            # Core DML: select(table), insert(table), etc.
            elif isinstance(node.func, ast.Name):
                if node.func.id in _CORE_DML:
                    access = _CORE_DML[node.func.id]
                    # Try to extract table reference from first argument
                    if node.args:
                        table_ref = self._extract_table_ref(node.args[0])
                        if table_ref:
                            mappings.append(RawMapping(
                                table_name=table_ref,
                                class_or_function=location,
                                access_type=access,
                                framework=FRAMEWORK,
                                pattern=f"{node.func.id}()",
                            ))

        return mappings

    def _extract_text_sql(self, call_node: ast.Call) -> str | None:
        """Extract SQL from text("SQL") inside execute()."""
        if not call_node.args:
            return None
        first = call_node.args[0]
        # text("SQL")
        if isinstance(first, ast.Call):
            if isinstance(first.func, ast.Name) and first.func.id == "text":
                if first.args and isinstance(first.args[0], ast.Constant):
                    return first.args[0].value
        # Direct string: execute("SQL")
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return None

    def _extract_table_ref(self, node: ast.expr) -> str | None:
        """Extract table name/reference from select()/insert() argument."""
        # select(users_table) or select(User)
        if isinstance(node, ast.Name):
            return node.id
        # select(User.__table__)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                return node.value.id
        return None
