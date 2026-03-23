"""Django ORM AST-based analyzer.

Detects:
- Model classes extending models.Model
- Meta.db_table for explicit table names
- Auto table naming: app_modelname (lowercase)
- QuerySet operations: objects.all/filter/get/create/update/delete
- Raw SQL: objects.raw("SQL"), connection.cursor().execute("SQL")
"""

from __future__ import annotations

import ast
import logging

from python_source_analyzer.models import FileAnalysisResult, RawMapping
from python_source_analyzer.sql_parser import SqlParser

logger = logging.getLogger(__name__)

FRAMEWORK = "Django ORM"

_DJANGO_IMPORTS = {"django",}

_DJANGO_BASES = {"Model", "models.Model"}

# QuerySet read methods
_QS_READ = {
    "all", "filter", "exclude", "get", "first", "last",
    "values", "values_list", "count", "exists", "aggregate",
    "annotate", "order_by", "distinct", "select_related",
    "prefetch_related", "only", "defer", "iterator",
}

# QuerySet write methods
_QS_WRITE = {
    "create", "bulk_create", "update", "bulk_update",
    "delete", "save",
}

# QuerySet RW methods
_QS_RW = {"get_or_create", "update_or_create"}


class DjangoAstAnalyzer:
    """AST-based Django ORM analyzer."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult | None:
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            logger.debug("AST parse failed for %s", file_path)
            return None

        imports = self._collect_imports(tree)
        if not self._has_django_imports(imports):
            return FileAnalysisResult(source_file=file_path, module_path="", imports=imports)

        mappings: list[RawMapping] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                mappings.extend(self._analyze_model_class(node))
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

    def _has_django_imports(self, imports: list[str]) -> bool:
        return any(imp.startswith("django") for imp in imports)

    def _analyze_model_class(self, class_node: ast.ClassDef) -> list[RawMapping]:
        """Analyze a Django model class for table mappings."""
        if not self._is_django_model(class_node):
            return []

        mappings: list[RawMapping] = []
        class_name = class_node.name
        table_name = None

        # Look for Meta.db_table
        for node in class_node.body:
            if isinstance(node, ast.ClassDef) and node.name == "Meta":
                for meta_item in node.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "db_table":
                                if isinstance(meta_item.value, ast.Constant) and isinstance(meta_item.value.value, str):
                                    table_name = meta_item.value.value
                            # Check for abstract = True
                            if isinstance(target, ast.Name) and target.id == "abstract":
                                if isinstance(meta_item.value, ast.Constant) and meta_item.value.value is True:
                                    return []  # Skip abstract models

        if table_name is None:
            # Django auto-naming: app_modelname (lowercase)
            # We use just the lowercase class name since we don't know the app name
            table_name = class_name.lower()

        mappings.append(RawMapping(
            table_name=table_name,
            class_or_function=class_name,
            access_type="RW",
            framework=FRAMEWORK,
            pattern="Meta.db_table" if table_name != class_name.lower() else "Model(auto)",
        ))

        return mappings

    def _is_django_model(self, class_node: ast.ClassDef) -> bool:
        """Check if class extends django.db.models.Model."""
        for base in class_node.bases:
            # models.Model
            if isinstance(base, ast.Attribute):
                if base.attr == "Model":
                    return True
            # Model (direct import)
            if isinstance(base, ast.Name):
                if base.id == "Model":
                    return True
        return False

    def _analyze_function(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[RawMapping]:
        """Analyze function body for objects.raw() and cursor.execute()."""
        mappings: list[RawMapping] = []
        func_name = func_node.name

        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            if not isinstance(node.func, ast.Attribute):
                continue

            method = node.func.attr

            # Model.objects.raw("SQL")
            if method == "raw" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    sql = node.args[0].value
                    refs = self._sql_parser.parse(sql)
                    for ref in refs:
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_function=func_name,
                            access_type=ref.access_type,
                            framework=FRAMEWORK,
                            pattern="objects.raw()",
                        ))

            # cursor.execute("SQL")
            if method == "execute" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    sql = node.args[0].value
                    refs = self._sql_parser.parse(sql)
                    for ref in refs:
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_function=func_name,
                            access_type=ref.access_type,
                            framework=FRAMEWORK,
                            pattern="cursor.execute()",
                        ))

        return mappings
