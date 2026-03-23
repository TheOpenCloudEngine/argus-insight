"""MyBatis Java annotation analyzer.

Extracts table mappings from MyBatis annotation-based mappers:
@Select, @Insert, @Update, @Delete on interface methods.
Uses both javalang AST and regex for robustness.
"""

from __future__ import annotations

import logging
import re

import javalang

from java_source_analyzer.jpa.sql_parser import SqlParser
from java_source_analyzer.models import FileAnalysisResult, RawMapping

logger = logging.getLogger(__name__)

FRAMEWORK = "MyBatis"

# MyBatis SQL annotations -> access type
_MYBATIS_ANNOTATIONS: dict[str, str] = {
    "Select": "R",
    "Insert": "W",
    "Update": "W",
    "Delete": "W",
}

# Provider annotations (we record them but can't extract SQL at compile time)
_PROVIDER_ANNOTATIONS = {"SelectProvider", "InsertProvider", "UpdateProvider", "DeleteProvider"}

# Regex patterns for annotation-based MyBatis
_RE_MYBATIS_IMPORT = re.compile(r"import\s+org\.apache\.ibatis\.annotations\.")
_RE_MYBATIS_MAPPER = re.compile(r"@Mapper\b")

# Regex for @Select("SQL"), @Insert("SQL"), etc.
_RE_SELECT = re.compile(r'@Select\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_INSERT = re.compile(r'@Insert\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_UPDATE = re.compile(r'@Update\s*\(\s*"([^"]+)"', re.DOTALL)
_RE_DELETE = re.compile(r'@Delete\s*\(\s*"([^"]+)"', re.DOTALL)

# Regex for multi-line SQL: @Select({"SQL1", "SQL2"})
_RE_SELECT_MULTI = re.compile(r'@Select\s*\(\s*\{([^}]+)\}', re.DOTALL)
_RE_INSERT_MULTI = re.compile(r'@Insert\s*\(\s*\{([^}]+)\}', re.DOTALL)
_RE_UPDATE_MULTI = re.compile(r'@Update\s*\(\s*\{([^}]+)\}', re.DOTALL)
_RE_DELETE_MULTI = re.compile(r'@Delete\s*\(\s*\{([^}]+)\}', re.DOTALL)

_REGEX_MAP: dict[str, tuple[re.Pattern, re.Pattern]] = {
    "Select": (_RE_SELECT, _RE_SELECT_MULTI),
    "Insert": (_RE_INSERT, _RE_INSERT_MULTI),
    "Update": (_RE_UPDATE, _RE_UPDATE_MULTI),
    "Delete": (_RE_DELETE, _RE_DELETE_MULTI),
}

# Method declaration pattern
_RE_METHOD_DECL = re.compile(
    r"(?:public|protected|private)?\s*[\w<>\[\],\s]+\s+(\w+)\s*\(",
)


class MyBatisAnnotationAnalyzer:
    """Extracts MyBatis annotation-based SQL mappings from Java source."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze_ast(self, source_code: str, file_path: str) -> FileAnalysisResult | None:
        """AST-based analysis of MyBatis annotations.

        Returns None if parsing fails.
        """
        try:
            tree = javalang.parse.parse(source_code)
        except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError, Exception):
            logger.debug("javalang parse failed for %s", file_path)
            return None

        package_name = tree.package.name if tree.package else ""
        imports = [imp.path for imp in (tree.imports or [])]

        if not self._has_mybatis_imports(imports):
            return FileAnalysisResult(
                source_file=file_path,
                package_name=package_name,
                imports=imports,
            )

        mappings: list[RawMapping] = []

        for type_decl in tree.types or []:
            if isinstance(type_decl, javalang.tree.InterfaceDeclaration):
                mappings.extend(self._analyze_interface(type_decl))
            elif isinstance(type_decl, javalang.tree.ClassDeclaration):
                mappings.extend(self._analyze_class(type_decl))

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=imports,
            mappings=mappings,
        )

    def analyze_regex(self, source_code: str, file_path: str) -> FileAnalysisResult:
        """Regex-based analysis of MyBatis annotations. Always returns a result."""
        # Check if this is a MyBatis file
        if not (_RE_MYBATIS_IMPORT.search(source_code) or _RE_MYBATIS_MAPPER.search(source_code)):
            # Also check for annotation patterns directly
            has_mybatis = any(
                re.search(rf"@{anno}\s*\(", source_code)
                for anno in _MYBATIS_ANNOTATIONS
            )
            if not has_mybatis:
                return FileAnalysisResult(source_file=file_path, package_name="", imports=[])

        # Extract package
        pkg_match = re.search(r"^\s*package\s+([\w.]+)\s*;", source_code, re.MULTILINE)
        package_name = pkg_match.group(1) if pkg_match else ""

        # Find the main interface/class name
        iface_match = re.search(
            r"(?:public\s+)?interface\s+(\w+)", source_code,
        )
        class_match = re.search(
            r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", source_code,
        )
        type_name = (iface_match or class_match).group(1) if (iface_match or class_match) else "Unknown"

        mappings: list[RawMapping] = []

        for anno_name, (single_pat, multi_pat) in _REGEX_MAP.items():
            access = _MYBATIS_ANNOTATIONS[anno_name]

            # Single-string pattern: @Select("SQL")
            for m in single_pat.finditer(source_code):
                sql = m.group(1)
                method_name = self._find_method_after(source_code, m.end())
                location = f"{type_name}.{method_name}" if method_name else type_name
                self._add_sql_mappings(mappings, sql, location, access, anno_name)

            # Multi-string pattern: @Select({"SQL1", "SQL2"})
            for m in multi_pat.finditer(source_code):
                raw = m.group(1)
                sql = self._join_multi_strings(raw)
                method_name = self._find_method_after(source_code, m.end())
                location = f"{type_name}.{method_name}" if method_name else type_name
                self._add_sql_mappings(mappings, sql, location, access, anno_name)

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=[],
            mappings=mappings,
        )

    def _has_mybatis_imports(self, imports: list[str]) -> bool:
        return any(
            i.startswith("org.apache.ibatis") for i in imports
        )

    def _analyze_interface(self, iface: javalang.tree.InterfaceDeclaration) -> list[RawMapping]:
        """Extract MyBatis annotations from interface methods."""
        mappings: list[RawMapping] = []
        iface_name = iface.name

        for method in iface.methods or []:
            for anno in method.annotations or []:
                if anno.name in _MYBATIS_ANNOTATIONS:
                    access = _MYBATIS_ANNOTATIONS[anno.name]
                    sql = self._extract_sql_from_annotation(anno)
                    if sql:
                        location = f"{iface_name}.{method.name}"
                        self._add_sql_mappings(mappings, sql, location, access, anno.name)

                elif anno.name in _PROVIDER_ANNOTATIONS:
                    # Provider-based: we can't extract SQL statically
                    access_char = anno.name.replace("Provider", "")
                    access = _MYBATIS_ANNOTATIONS.get(access_char, "R")
                    mappings.append(RawMapping(
                        table_name=f"[{anno.name}]",
                        class_or_method=f"{iface_name}.{method.name}",
                        access_type=access,
                        framework=FRAMEWORK,
                        annotation=f"@{anno.name}",
                    ))

        return mappings

    def _analyze_class(self, class_decl: javalang.tree.ClassDeclaration) -> list[RawMapping]:
        """Extract MyBatis annotations from class methods (less common)."""
        mappings: list[RawMapping] = []
        class_name = class_decl.name

        for method in class_decl.methods or []:
            for anno in method.annotations or []:
                if anno.name in _MYBATIS_ANNOTATIONS:
                    access = _MYBATIS_ANNOTATIONS[anno.name]
                    sql = self._extract_sql_from_annotation(anno)
                    if sql:
                        location = f"{class_name}.{method.name}"
                        self._add_sql_mappings(mappings, sql, location, access, anno.name)

        return mappings

    def _extract_sql_from_annotation(self, anno: javalang.tree.Annotation) -> str | None:
        """Extract SQL string from a MyBatis annotation."""
        if anno.element is None:
            return None

        # @Select("SQL") — single literal
        if isinstance(anno.element, javalang.tree.Literal):
            return self._unquote(anno.element.value)

        # @Select(value = "SQL")
        if isinstance(anno.element, list):
            for ev in anno.element:
                if isinstance(ev, javalang.tree.ElementValuePair):
                    if ev.name == "value" and isinstance(ev.value, javalang.tree.Literal):
                        return self._unquote(ev.value.value)
                    # Array value: @Select({"SQL1", "SQL2"})
                    if isinstance(ev.value, list):
                        return self._join_literal_list(ev.value)
                # Direct array: @Select({"SQL1", "SQL2"})
                elif isinstance(ev, javalang.tree.Literal):
                    # Part of an array — collect all
                    parts = [
                        self._unquote(item.value)
                        for item in anno.element
                        if isinstance(item, javalang.tree.Literal)
                    ]
                    return " ".join(p for p in parts if p)

        return None

    def _join_literal_list(self, items: list) -> str:
        """Join an array of string literals."""
        parts = []
        for item in items:
            if isinstance(item, javalang.tree.Literal):
                val = self._unquote(item.value)
                if val:
                    parts.append(val)
        return " ".join(parts)

    def _add_sql_mappings(
        self,
        mappings: list[RawMapping],
        sql: str,
        location: str,
        access: str,
        anno_name: str,
    ) -> None:
        """Parse SQL and add table references to mappings."""
        refs = self._sql_parser.parse(sql)
        if refs:
            for ref in refs:
                # Use tag-level access as minimum; SQL parser may refine
                resolved_access = ref.access_type if ref.access_type == "W" else access
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_method=location,
                    access_type=resolved_access,
                    framework=FRAMEWORK,
                    annotation=f"@{anno_name}",
                ))

    def _find_method_after(self, source_code: str, position: int) -> str | None:
        """Find the next method declaration after a given position."""
        remaining = source_code[position:position + 500]
        m = _RE_METHOD_DECL.search(remaining)
        return m.group(1) if m else None

    def _join_multi_strings(self, raw: str) -> str:
        """Join multiple quoted strings from {"str1", "str2"} pattern."""
        parts = re.findall(r'"([^"]*)"', raw)
        return " ".join(parts)

    @staticmethod
    def _unquote(value: str) -> str | None:
        if value and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return None
