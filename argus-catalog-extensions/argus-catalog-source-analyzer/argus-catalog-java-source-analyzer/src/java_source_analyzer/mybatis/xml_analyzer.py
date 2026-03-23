"""MyBatis XML mapper analyzer.

Parses MyBatis XML mapper files (*Mapper.xml, *-mapper.xml) to extract
SQL statements from <select>, <insert>, <update>, <delete> tags and
identifies referenced tables.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from java_source_analyzer.jpa.sql_parser import SqlParser
from java_source_analyzer.models import FileAnalysisResult, RawMapping

logger = logging.getLogger(__name__)

FRAMEWORK = "MyBatis"

# Tags that contain SQL statements
_SQL_TAGS = {"select", "insert", "update", "delete"}

# Access type by tag name
_TAG_ACCESS: dict[str, str] = {
    "select": "R",
    "insert": "W",
    "update": "W",
    "delete": "W",
}

# Regex to strip MyBatis dynamic SQL tags from text content
_RE_MYBATIS_TAGS = re.compile(
    r"</?(?:if|choose|when|otherwise|where|set|trim|foreach|bind|include|selectKey)"
    r"[^>]*?>",
    re.IGNORECASE | re.DOTALL,
)

# Regex to strip #{...} and ${...} parameter placeholders
_RE_PARAM_HASH = re.compile(r"#\{[^}]*\}")
_RE_PARAM_DOLLAR = re.compile(r"\$\{[^}]*\}")

# Regex to extract namespace from <mapper namespace="...">
_RE_NAMESPACE = re.compile(r'namespace\s*=\s*"([^"]+)"')


class MyBatisXmlAnalyzer:
    """Parses MyBatis XML mapper files to extract table mappings."""

    def __init__(self) -> None:
        self._sql_parser = SqlParser()

    def analyze(self, xml_content: str, file_path: str) -> FileAnalysisResult:
        """Parse a MyBatis XML mapper file and extract table mappings.

        Args:
            xml_content: Content of the XML mapper file.
            file_path: Relative path of the XML file.

        Returns:
            FileAnalysisResult with discovered table mappings.
        """
        mappings: list[RawMapping] = []
        namespace = ""

        # Try XML parsing first
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            logger.debug("XML parse failed for %s, falling back to regex", file_path)
            return self._analyze_with_regex(xml_content, file_path)

        # Extract namespace
        namespace = root.attrib.get("namespace", "")

        # Extract SQL fragments for <include> resolution
        sql_fragments = self._extract_sql_fragments(root)

        # Process SQL statement tags
        for tag_name in _SQL_TAGS:
            for element in root.iter(tag_name):
                stmt_id = element.attrib.get("id", "")
                raw_sql = self._extract_element_text(element)

                # Resolve <include> references
                raw_sql = self._resolve_includes(raw_sql, sql_fragments)

                # Clean MyBatis dynamic SQL
                clean_sql = self._clean_mybatis_sql(raw_sql)

                if not clean_sql.strip():
                    continue

                # Determine class/method context
                class_name = namespace.rsplit(".", 1)[-1] if namespace else Path(file_path).stem
                location = f"{class_name}.{stmt_id}" if stmt_id else class_name

                # Parse SQL for tables
                refs = self._sql_parser.parse(clean_sql)

                if refs:
                    for ref in refs:
                        # Override access type based on tag if sql_parser returns generic
                        access = self._resolve_access(tag_name, ref.access_type)
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_method=location,
                            access_type=access,
                            framework=FRAMEWORK,
                            annotation=f"<{tag_name}>",
                        ))
                else:
                    # SQL parser couldn't extract tables, try regex on the raw SQL
                    regex_refs = self._extract_tables_regex(clean_sql, tag_name)
                    for table_name, access in regex_refs:
                        mappings.append(RawMapping(
                            table_name=table_name,
                            class_or_method=location,
                            access_type=access,
                            framework=FRAMEWORK,
                            annotation=f"<{tag_name}>",
                        ))

        # Extract package from namespace
        package_name = namespace.rsplit(".", 1)[0] if "." in namespace else ""

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=[],
            mappings=mappings,
        )

    def _extract_sql_fragments(self, root: ET.Element) -> dict[str, str]:
        """Extract <sql id="..."> fragments for include resolution."""
        fragments: dict[str, str] = {}
        for sql_el in root.iter("sql"):
            frag_id = sql_el.attrib.get("id", "")
            if frag_id:
                fragments[frag_id] = self._extract_element_text(sql_el)
        return fragments

    def _extract_element_text(self, element: ET.Element) -> str:
        """Extract all text content from an XML element, including nested elements."""
        parts: list[str] = []
        if element.text:
            parts.append(element.text)
        for child in element:
            # Include tag text for dynamic SQL processing
            child_text = self._extract_element_text(child)
            if child_text:
                parts.append(child_text)
            if child.tail:
                parts.append(child.tail)
        return " ".join(parts)

    def _resolve_includes(self, sql: str, fragments: dict[str, str]) -> str:
        """Replace <include refid="..."/> references with fragment content."""
        # Simple pattern for include references left as text after ET parsing
        include_pattern = re.compile(r'<include\s+refid\s*=\s*"([^"]+)"\s*/?\s*>')
        for _ in range(5):  # Max 5 rounds of resolution for nested includes
            match = include_pattern.search(sql)
            if not match:
                break
            ref_id = match.group(1)
            replacement = fragments.get(ref_id, "")
            sql = sql[:match.start()] + replacement + sql[match.end():]
        return sql

    def _clean_mybatis_sql(self, raw_sql: str) -> str:
        """Remove MyBatis dynamic SQL tags and parameter placeholders to get plain SQL."""
        # Strip MyBatis XML tags
        sql = _RE_MYBATIS_TAGS.sub(" ", raw_sql)
        # Replace #{param} with placeholder value
        sql = _RE_PARAM_HASH.sub("?", sql)
        # Replace ${param} with placeholder (could be table name, but often unsafe)
        sql = _RE_PARAM_DOLLAR.sub("__DYNAMIC__", sql)
        # Normalize whitespace
        sql = " ".join(sql.split())
        return sql.strip()

    def _resolve_access(self, tag_name: str, parser_access: str) -> str:
        """Resolve access type: use tag-based access as default."""
        tag_access = _TAG_ACCESS.get(tag_name, "R")
        if parser_access == "W" or tag_access == "W":
            return parser_access  # Trust the SQL parser for write operations
        return tag_access

    def _extract_tables_regex(
        self, sql: str, tag_name: str,
    ) -> list[tuple[str, str]]:
        """Fallback regex extraction when SQL parser fails."""
        access = _TAG_ACCESS.get(tag_name, "R")
        tables: list[tuple[str, str]] = []
        seen: set[str] = set()

        # FROM table_name
        for m in re.finditer(r"\bFROM\s+([\w.]+)", sql, re.IGNORECASE):
            name = m.group(1)
            if name.upper() not in _SQL_KEYWORDS and name not in seen:
                tables.append((name, "R"))
                seen.add(name)

        # JOIN table_name
        for m in re.finditer(r"\bJOIN\s+([\w.]+)", sql, re.IGNORECASE):
            name = m.group(1)
            if name.upper() not in _SQL_KEYWORDS and name not in seen:
                tables.append((name, "R"))
                seen.add(name)

        # INSERT INTO table_name
        for m in re.finditer(r"\bINSERT\s+INTO\s+([\w.]+)", sql, re.IGNORECASE):
            name = m.group(1)
            if name not in seen:
                tables.append((name, "W"))
                seen.add(name)

        # UPDATE table_name
        for m in re.finditer(r"\bUPDATE\s+([\w.]+)", sql, re.IGNORECASE):
            name = m.group(1)
            if name.upper() not in _SQL_KEYWORDS and name not in seen:
                tables.append((name, "W"))
                seen.add(name)

        # DELETE FROM table_name
        for m in re.finditer(r"\bDELETE\s+FROM\s+([\w.]+)", sql, re.IGNORECASE):
            name = m.group(1)
            if name not in seen:
                tables.append((name, "W"))
                seen.add(name)

        return tables

    def _analyze_with_regex(self, xml_content: str, file_path: str) -> FileAnalysisResult:
        """Fallback: analyze XML content with regex when ET parsing fails."""
        mappings: list[RawMapping] = []

        # Extract namespace
        ns_match = _RE_NAMESPACE.search(xml_content)
        namespace = ns_match.group(1) if ns_match else ""
        package_name = namespace.rsplit(".", 1)[0] if "." in namespace else ""
        class_name = namespace.rsplit(".", 1)[-1] if namespace else Path(file_path).stem

        # Match SQL statement tags
        for tag_name in _SQL_TAGS:
            pattern = re.compile(
                rf'<{tag_name}\s[^>]*id\s*=\s*"([^"]+)"[^>]*>(.*?)</{tag_name}>',
                re.DOTALL | re.IGNORECASE,
            )
            for m in pattern.finditer(xml_content):
                stmt_id = m.group(1)
                raw_sql = m.group(2)
                clean_sql = self._clean_mybatis_sql(raw_sql)
                location = f"{class_name}.{stmt_id}" if stmt_id else class_name

                refs = self._sql_parser.parse(clean_sql)
                if refs:
                    for ref in refs:
                        access = self._resolve_access(tag_name, ref.access_type)
                        mappings.append(RawMapping(
                            table_name=ref.table_name,
                            class_or_method=location,
                            access_type=access,
                            framework=FRAMEWORK,
                            annotation=f"<{tag_name}>",
                        ))
                else:
                    regex_refs = self._extract_tables_regex(clean_sql, tag_name)
                    for table_name, access in regex_refs:
                        mappings.append(RawMapping(
                            table_name=table_name,
                            class_or_method=location,
                            access_type=access,
                            framework=FRAMEWORK,
                            annotation=f"<{tag_name}>",
                        ))

        return FileAnalysisResult(
            source_file=file_path,
            package_name=package_name,
            imports=[],
            mappings=mappings,
        )


_SQL_KEYWORDS = {
    "SELECT", "WHERE", "SET", "VALUES", "INTO", "AS", "ON",
    "AND", "OR", "NOT", "NULL", "IN", "EXISTS", "BETWEEN",
    "LIKE", "ORDER", "GROUP", "HAVING", "LIMIT", "OFFSET",
    "UNION", "EXCEPT", "INTERSECT", "DUAL",
}
