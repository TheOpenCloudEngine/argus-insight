"""JPA/Hibernate AST-based analyzer using javalang.

Parses Java source files into ASTs and extracts table mappings from
JPA annotations, JPQL/native queries, and EntityManager method calls.
"""

from __future__ import annotations

import logging

import javalang

from java_source_analyzer.jpa.sql_parser import SqlParser
from java_source_analyzer.models import FileAnalysisResult, RawMapping

logger = logging.getLogger(__name__)

# JPA entity manager method -> access type
_EM_METHODS: dict[str, str] = {
    "persist": "W",
    "merge": "W",
    "remove": "W",
    "find": "R",
    "getReference": "R",
    "refresh": "R",
}

# Annotations that contain table names in their 'name' element
_TABLE_ANNOTATIONS = {"Table", "SecondaryTable", "CollectionTable"}

# Annotations that contain table names in their 'name' element (join tables)
_JOIN_TABLE_ANNOTATIONS = {"JoinTable"}

# Named query annotations
_NAMED_QUERY_ANNOTATIONS = {"NamedQuery", "NamedNativeQuery"}
_NAMED_QUERIES_ANNOTATIONS = {"NamedQueries", "NamedNativeQueries"}

# Relationship annotations
_RELATIONSHIP_ANNOTATIONS = {"OneToMany", "ManyToOne", "OneToOne", "ManyToMany"}


class JpaAstAnalyzer:
    """Uses javalang to parse Java source and extract JPA table mappings."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult | None:
        """Parse source and extract all JPA-related table mappings.

        Returns None if the source cannot be parsed by javalang.
        """
        try:
            tree = javalang.parse.parse(source_code)
        except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError, Exception) as e:
            logger.debug("javalang parse failed for %s: %s", file_path, e)
            return None

        package_name = tree.package.name if tree.package else ""
        imports = [imp.path for imp in (tree.imports or [])]

        # Check if this file uses JPA at all
        if not self._has_jpa_imports(imports):
            return FileAnalysisResult(
                source_file=file_path,
                package_name=package_name,
                imports=imports,
            )

        framework = self._detect_framework(imports)
        mappings: list[RawMapping] = []

        for type_decl in tree.types or []:
            if not isinstance(type_decl, javalang.tree.ClassDeclaration):
                continue
            class_mappings = self._analyze_class(type_decl, framework)
            mappings.extend(class_mappings)

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=imports,
            mappings=mappings,
        )

    def _has_jpa_imports(self, imports: list[str]) -> bool:
        """Check if the file imports JPA/Hibernate packages."""
        for imp in imports:
            if (
                imp.startswith("javax.persistence")
                or imp.startswith("jakarta.persistence")
                or imp.startswith("org.hibernate")
            ):
                return True
        return False

    def _detect_framework(self, imports: list[str]) -> str:
        """Determine framework from imports."""
        has_jpa = False
        has_hibernate = False
        for imp in imports:
            if imp.startswith("javax.persistence") or imp.startswith("jakarta.persistence"):
                has_jpa = True
            if imp.startswith("org.hibernate"):
                has_hibernate = True
        if has_jpa and has_hibernate:
            return "JPA/Hibernate"
        if has_hibernate:
            return "Hibernate"
        return "JPA"

    def _analyze_class(
        self, class_decl: javalang.tree.ClassDeclaration, framework: str,
    ) -> list[RawMapping]:
        """Extract all mappings from a class declaration."""
        mappings: list[RawMapping] = []
        class_name = class_decl.name

        # 1. Class-level annotations
        mappings.extend(self._extract_entity_table(class_decl, framework))
        mappings.extend(self._extract_named_queries(class_decl, class_name, framework))

        # 2. Field-level annotations
        mappings.extend(self._extract_field_mappings(class_decl, class_name, framework))

        # 3. Method body analysis
        mappings.extend(self._extract_method_queries(class_decl, framework))

        return mappings

    def _extract_entity_table(
        self, class_decl: javalang.tree.ClassDeclaration, framework: str,
    ) -> list[RawMapping]:
        """Extract @Entity/@Table/@SecondaryTable mappings."""
        mappings: list[RawMapping] = []
        annotations = class_decl.annotations or []

        has_entity = any(a.name == "Entity" for a in annotations)
        table_name = None

        for anno in annotations:
            # @Table(name="...")
            if anno.name in _TABLE_ANNOTATIONS:
                name = self._get_annotation_element(anno, "name")
                if name:
                    table_name = name
                    mappings.append(RawMapping(
                        table_name=name,
                        class_or_method=class_decl.name,
                        access_type="RW",
                        framework=framework,
                        annotation=f"@{anno.name}",
                    ))

            # @JoinTable(name="...")
            if anno.name in _JOIN_TABLE_ANNOTATIONS:
                name = self._get_annotation_element(anno, "name")
                if name:
                    mappings.append(RawMapping(
                        table_name=name,
                        class_or_method=class_decl.name,
                        access_type="RW",
                        framework=framework,
                        annotation=f"@{anno.name}",
                    ))

        # @Entity without @Table -> class name is table name
        if has_entity and table_name is None:
            mappings.append(RawMapping(
                table_name=class_decl.name,
                class_or_method=class_decl.name,
                access_type="RW",
                framework=framework,
                annotation="@Entity",
            ))

        return mappings

    def _extract_named_queries(
        self,
        class_decl: javalang.tree.ClassDeclaration,
        class_name: str,
        framework: str,
    ) -> list[RawMapping]:
        """Extract @NamedQuery/@NamedNativeQuery SQL and parse for tables."""
        mappings: list[RawMapping] = []
        annotations = class_decl.annotations or []

        for anno in annotations:
            if anno.name in _NAMED_QUERY_ANNOTATIONS:
                mappings.extend(
                    self._parse_query_annotation(anno, class_name, framework),
                )
            elif anno.name in _NAMED_QUERIES_ANNOTATIONS:
                # @NamedQueries({@NamedQuery(...), @NamedQuery(...)})
                inner_annos = self._get_annotation_array(anno)
                for inner in inner_annos:
                    mappings.extend(
                        self._parse_query_annotation(inner, class_name, framework),
                    )

        return mappings

    def _parse_query_annotation(
        self, anno: javalang.tree.Annotation, class_name: str, framework: str,
    ) -> list[RawMapping]:
        """Parse a single @NamedQuery or @NamedNativeQuery annotation."""
        query = self._get_annotation_element(anno, "query")
        if not query:
            return []

        is_native = "Native" in (anno.name or "")
        refs = self._sql_parser.parse(query, is_jpql=not is_native)

        mappings = []
        for ref in refs:
            mappings.append(RawMapping(
                table_name=ref.table_name,
                class_or_method=class_name,
                access_type=ref.access_type,
                framework=framework,
                annotation=f"@{anno.name}",
            ))
        return mappings

    def _extract_field_mappings(
        self,
        class_decl: javalang.tree.ClassDeclaration,
        class_name: str,
        framework: str,
    ) -> list[RawMapping]:
        """Extract @JoinTable from field annotations."""
        mappings: list[RawMapping] = []

        for field in class_decl.fields or []:
            for anno in field.annotations or []:
                if anno.name in _JOIN_TABLE_ANNOTATIONS:
                    name = self._get_annotation_element(anno, "name")
                    if name:
                        mappings.append(RawMapping(
                            table_name=name,
                            class_or_method=class_name,
                            access_type="RW",
                            framework=framework,
                            annotation=f"@{anno.name}",
                        ))

        return mappings

    def _extract_method_queries(
        self, class_decl: javalang.tree.ClassDeclaration, framework: str,
    ) -> list[RawMapping]:
        """Extract queries from method bodies (createQuery, createNativeQuery, etc.)."""
        mappings: list[RawMapping] = []

        for method in class_decl.methods or []:
            method_name = method.name
            if method.body is None:
                continue

            # Walk the method body looking for MethodInvocation nodes
            for _, node in method.filter(javalang.tree.MethodInvocation):
                if node.member in ("createQuery", "createNativeQuery"):
                    sql = self._extract_string_argument(node)
                    if sql:
                        is_native = node.member == "createNativeQuery"
                        refs = self._sql_parser.parse(sql, is_jpql=not is_native)
                        for ref in refs:
                            mappings.append(RawMapping(
                                table_name=ref.table_name,
                                class_or_method=f"{class_decl.name}.{method_name}",
                                access_type=ref.access_type,
                                framework=framework,
                                annotation=node.member,
                            ))

                elif node.member in _EM_METHODS:
                    access = _EM_METHODS[node.member]
                    # For find/getReference, the first arg is the entity class
                    # For persist/merge/remove, the arg is an entity instance
                    # We record the method but can't resolve the entity class from AST alone
                    mappings.append(RawMapping(
                        table_name=f"[EntityManager.{node.member}]",
                        class_or_method=f"{class_decl.name}.{method_name}",
                        access_type=access,
                        framework=framework,
                        annotation=f"EntityManager.{node.member}",
                    ))

        return mappings

    def _get_annotation_element(
        self, anno: javalang.tree.Annotation, key: str,
    ) -> str | None:
        """Extract a string value from an annotation element.

        Handles both @Table(name="X") and @Table("X") forms.
        """
        if anno.element is None:
            return None

        # @Table("X") - single value
        if isinstance(anno.element, javalang.tree.Literal):
            if key == "name" or key == "value":
                return self._unquote(anno.element.value)
            return None

        # @Table(name="X") - element-value pairs
        if isinstance(anno.element, list):
            for ev in anno.element:
                if isinstance(ev, javalang.tree.ElementValuePair):
                    if ev.name == key and isinstance(ev.value, javalang.tree.Literal):
                        return self._unquote(ev.value.value)
        return None

    def _get_annotation_array(
        self, anno: javalang.tree.Annotation,
    ) -> list[javalang.tree.Annotation]:
        """Extract array of annotations from @NamedQueries({...}) style."""
        if anno.element is None:
            return []

        # Single element: @NamedQueries(@NamedQuery(...))
        if isinstance(anno.element, javalang.tree.Annotation):
            return [anno.element]

        # Array: @NamedQueries({@NamedQuery(...), @NamedQuery(...)})
        if isinstance(anno.element, list):
            results = []
            for item in anno.element:
                if isinstance(item, javalang.tree.Annotation):
                    results.append(item)
                elif isinstance(item, javalang.tree.ElementValuePair):
                    if isinstance(item.value, javalang.tree.Annotation):
                        results.append(item.value)
                    elif isinstance(item.value, list):
                        for v in item.value:
                            if isinstance(v, javalang.tree.Annotation):
                                results.append(v)
            return results

        return []

    def _extract_string_argument(
        self, invocation: javalang.tree.MethodInvocation,
    ) -> str | None:
        """Extract the first string literal argument from a method call."""
        if not invocation.arguments:
            return None

        first_arg = invocation.arguments[0]
        if isinstance(first_arg, javalang.tree.Literal):
            return self._unquote(first_arg.value)

        # Handle string concatenation: "SELECT " + "FROM users"
        if isinstance(first_arg, javalang.tree.BinaryOperation):
            return self._concat_string_parts(first_arg)

        return None

    def _concat_string_parts(self, expr: javalang.tree.BinaryOperation) -> str | None:
        """Recursively concatenate string literals in binary + operations."""
        parts = []
        self._collect_string_parts(expr, parts)
        if parts:
            return "".join(parts)
        return None

    def _collect_string_parts(
        self, expr: javalang.tree.Node, parts: list[str],
    ) -> None:
        """Collect string literal parts from a binary expression tree."""
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
        """Remove surrounding quotes from a Java string literal."""
        if value and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return None
