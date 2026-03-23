"""Regex-based JPA pattern extraction.

Supplements the AST analyzer by catching patterns that javalang might miss,
and serves as a fallback when AST parsing fails (e.g., newer Java syntax).
"""

from __future__ import annotations

import logging
import re

from java_source_analyzer.jpa.sql_parser import SqlParser
from java_source_analyzer.models import FileAnalysisResult, RawMapping

logger = logging.getLogger(__name__)

# Package declaration
_RE_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

# Import detection
_RE_JAVAX_IMPORT = re.compile(r"import\s+javax\.persistence\.")
_RE_JAKARTA_IMPORT = re.compile(r"import\s+jakarta\.persistence\.")
_RE_HIBERNATE_IMPORT = re.compile(r"import\s+org\.hibernate\.")

# @Entity on a class
_RE_ENTITY_CLASS = re.compile(
    r"@Entity\b[^{]*?(?:public\s+|protected\s+|private\s+)?(?:abstract\s+)?class\s+(\w+)",
    re.DOTALL,
)

# @Table(name = "TABLE_NAME") — handles various whitespace and attribute orderings
_RE_TABLE = re.compile(
    r'@Table\s*\([^)]*?name\s*=\s*"([^"]+)"',
    re.DOTALL,
)

# @SecondaryTable(name = "TABLE_NAME")
_RE_SECONDARY_TABLE = re.compile(
    r'@SecondaryTable\s*\([^)]*?name\s*=\s*"([^"]+)"',
    re.DOTALL,
)

# @JoinTable(name = "TABLE_NAME") — both class-level and field-level
_RE_JOIN_TABLE = re.compile(
    r'@JoinTable\s*\([^)]*?name\s*=\s*"([^"]+)"',
    re.DOTALL,
)

# @CollectionTable(name = "TABLE_NAME")
_RE_COLLECTION_TABLE = re.compile(
    r'@CollectionTable\s*\([^)]*?name\s*=\s*"([^"]+)"',
    re.DOTALL,
)

# @NamedQuery(... query = "...")
_RE_NAMED_QUERY = re.compile(
    r'@NamedQuery\s*\([^)]*?query\s*=\s*"([^"]+)"',
    re.DOTALL,
)

# @NamedNativeQuery(... query = "...")
_RE_NAMED_NATIVE_QUERY = re.compile(
    r'@NamedNativeQuery\s*\([^)]*?query\s*=\s*"([^"]+)"',
    re.DOTALL,
)

# createQuery("...") / createNativeQuery("...")
_RE_CREATE_QUERY = re.compile(
    r'createQuery\s*\(\s*"([^"]+)"',
)
_RE_CREATE_NATIVE_QUERY = re.compile(
    r'createNativeQuery\s*\(\s*"([^"]+)"',
)

# Class name extraction for context
_RE_CLASS_DECL = re.compile(
    r"(?:public\s+|protected\s+|private\s+)?(?:abstract\s+|final\s+)?class\s+(\w+)",
)

# Method name extraction for context
_RE_METHOD_DECL = re.compile(
    r"(?:public|protected|private)\s+[\w<>\[\],\s]+\s+(\w+)\s*\(",
)

# @Inheritance strategy
_RE_INHERITANCE = re.compile(
    r"@Inheritance\s*\(\s*strategy\s*=\s*InheritanceType\.(\w+)",
)


class JpaRegexAnalyzer:
    """Regex-based JPA pattern extraction as supplement/fallback."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, source_code: str, file_path: str) -> FileAnalysisResult:
        """Extract JPA table mappings using regex patterns.

        Always returns a result (never None), even if empty.
        """
        # Package
        pkg_match = _RE_PACKAGE.search(source_code)
        package_name = pkg_match.group(1) if pkg_match else ""

        # Imports
        imports: list[str] = []
        has_javax = bool(_RE_JAVAX_IMPORT.search(source_code))
        has_jakarta = bool(_RE_JAKARTA_IMPORT.search(source_code))
        has_hibernate = bool(_RE_HIBERNATE_IMPORT.search(source_code))

        if has_javax:
            imports.append("javax.persistence")
        if has_jakarta:
            imports.append("jakarta.persistence")
        if has_hibernate:
            imports.append("org.hibernate")

        # Check if this file uses JPA at all
        if not (has_javax or has_jakarta or has_hibernate):
            return FileAnalysisResult(
                source_file=file_path,
                package_name=package_name,
                imports=imports,
            )

        framework = self._detect_framework(has_javax, has_jakarta, has_hibernate)
        mappings: list[RawMapping] = []

        # Find the primary class name for context
        class_name = self._find_primary_class(source_code)

        # @Table(name="...")
        for m in _RE_TABLE.finditer(source_code):
            mappings.append(RawMapping(
                table_name=m.group(1),
                class_or_method=class_name,
                access_type="RW",
                framework=framework,
                annotation="@Table",
            ))

        # @Entity without @Table -> class name is table name
        entity_classes = set()
        table_names_found = {m.table_name for m in mappings}
        for m in _RE_ENTITY_CLASS.finditer(source_code):
            entity_name = m.group(1)
            entity_classes.add(entity_name)
            # Only add if we didn't already find a @Table for this
            if entity_name not in table_names_found and not table_names_found:
                mappings.append(RawMapping(
                    table_name=entity_name,
                    class_or_method=entity_name,
                    access_type="RW",
                    framework=framework,
                    annotation="@Entity",
                ))

        # @SecondaryTable
        for m in _RE_SECONDARY_TABLE.finditer(source_code):
            mappings.append(RawMapping(
                table_name=m.group(1),
                class_or_method=class_name,
                access_type="RW",
                framework=framework,
                annotation="@SecondaryTable",
            ))

        # @JoinTable
        for m in _RE_JOIN_TABLE.finditer(source_code):
            mappings.append(RawMapping(
                table_name=m.group(1),
                class_or_method=class_name,
                access_type="RW",
                framework=framework,
                annotation="@JoinTable",
            ))

        # @CollectionTable
        for m in _RE_COLLECTION_TABLE.finditer(source_code):
            mappings.append(RawMapping(
                table_name=m.group(1),
                class_or_method=class_name,
                access_type="RW",
                framework=framework,
                annotation="@CollectionTable",
            ))

        # @NamedQuery
        for m in _RE_NAMED_QUERY.finditer(source_code):
            query = m.group(1)
            refs = self._sql_parser.parse(query, is_jpql=True)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_method=class_name,
                    access_type=ref.access_type,
                    framework=framework,
                    annotation="@NamedQuery",
                ))

        # @NamedNativeQuery
        for m in _RE_NAMED_NATIVE_QUERY.finditer(source_code):
            query = m.group(1)
            refs = self._sql_parser.parse(query, is_jpql=False)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_method=class_name,
                    access_type=ref.access_type,
                    framework=framework,
                    annotation="@NamedNativeQuery",
                ))

        # createQuery("...")
        for m in _RE_CREATE_QUERY.finditer(source_code):
            query = m.group(1)
            method_ctx = self._find_enclosing_method(source_code, m.start())
            location = f"{class_name}.{method_ctx}" if method_ctx else class_name
            refs = self._sql_parser.parse(query, is_jpql=True)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_method=location,
                    access_type=ref.access_type,
                    framework=framework,
                    annotation="createQuery",
                ))

        # createNativeQuery("...")
        for m in _RE_CREATE_NATIVE_QUERY.finditer(source_code):
            query = m.group(1)
            method_ctx = self._find_enclosing_method(source_code, m.start())
            location = f"{class_name}.{method_ctx}" if method_ctx else class_name
            refs = self._sql_parser.parse(query, is_jpql=False)
            for ref in refs:
                mappings.append(RawMapping(
                    table_name=ref.table_name,
                    class_or_method=location,
                    access_type=ref.access_type,
                    framework=framework,
                    annotation="createNativeQuery",
                ))

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=imports,
            mappings=mappings,
        )

    def _detect_framework(
        self, has_javax: bool, has_jakarta: bool, has_hibernate: bool,
    ) -> str:
        has_jpa = has_javax or has_jakarta
        if has_jpa and has_hibernate:
            return "JPA/Hibernate"
        if has_hibernate:
            return "Hibernate"
        return "JPA"

    def _find_primary_class(self, source_code: str) -> str:
        """Find the first public/main class name in the source."""
        # Prefer public class
        m = re.search(r"public\s+(?:abstract\s+)?class\s+(\w+)", source_code)
        if m:
            return m.group(1)
        m = _RE_CLASS_DECL.search(source_code)
        return m.group(1) if m else "Unknown"

    def _find_enclosing_method(self, source_code: str, position: int) -> str | None:
        """Find the method name that encloses the given position."""
        # Search backward from position for the nearest method declaration
        preceding = source_code[:position]
        matches = list(_RE_METHOD_DECL.finditer(preceding))
        if matches:
            return matches[-1].group(1)
        return None
