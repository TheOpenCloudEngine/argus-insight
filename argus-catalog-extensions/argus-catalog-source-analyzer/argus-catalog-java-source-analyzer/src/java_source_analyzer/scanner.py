"""Top-level orchestrator that scans a Java project directory for table mappings."""

from __future__ import annotations

import logging
from pathlib import Path

from java_source_analyzer.build_detector import BuildDetector
from java_source_analyzer.jpa.ast_analyzer import JpaAstAnalyzer
from java_source_analyzer.jpa.merger import ResultMerger
from java_source_analyzer.jpa.regex_analyzer import JpaRegexAnalyzer
from java_source_analyzer.jdbc.ast_analyzer import JdbcAstAnalyzer
from java_source_analyzer.jdbc.merger import JdbcResultMerger
from java_source_analyzer.jdbc.regex_analyzer import JdbcRegexAnalyzer
from java_source_analyzer.mybatis.annotation_analyzer import MyBatisAnnotationAnalyzer
from java_source_analyzer.mybatis.merger import MyBatisResultMerger
from java_source_analyzer.mybatis.xml_analyzer import MyBatisXmlAnalyzer
from java_source_analyzer.models import BuildInfo, FileAnalysisResult, RawMapping, TableMapping

logger = logging.getLogger(__name__)

# Directories to skip during scanning
_SKIP_DIRS = {
    "target", "build", "out", ".git", ".svn", ".idea", ".gradle",
    "node_modules", "__pycache__", ".settings", "bin",
}


class JavaSourceScanner:
    """Orchestrates scanning of a Java project directory."""

    def __init__(self, project_name: str, source_directory: str | Path) -> None:
        self.project_name = project_name
        self.source_directory = Path(source_directory).resolve()
        self.build_detector = BuildDetector()
        # JPA
        self.jpa_ast_analyzer = JpaAstAnalyzer()
        self.jpa_regex_analyzer = JpaRegexAnalyzer()
        self.jpa_merger = ResultMerger()
        # MyBatis
        self.mybatis_xml_analyzer = MyBatisXmlAnalyzer()
        self.mybatis_anno_analyzer = MyBatisAnnotationAnalyzer()
        self.mybatis_merger = MyBatisResultMerger()
        # JDBC
        self.jdbc_ast_analyzer = JdbcAstAnalyzer()
        self.jdbc_regex_analyzer = JdbcRegexAnalyzer()
        self.jdbc_merger = JdbcResultMerger()

    def scan(self) -> list[TableMapping]:
        """Scan all .java and MyBatis XML files and return table mappings.

        Returns a list of TableMapping records enriched with build info.
        """
        if not self.source_directory.is_dir():
            logger.error("Directory not found: %s", self.source_directory)
            return []

        # Detect build info
        build_info = self.build_detector.detect(self.source_directory)
        logger.info(
            "Build info: Java %s, %s, Hibernate=%s",
            build_info.java_version,
            build_info.java_ee_version,
            build_info.has_hibernate,
        )

        all_mappings: list[TableMapping] = []

        # --- Analyze Java files (JPA + MyBatis annotations) ---
        java_files = self._find_files("*.java")
        parse_warnings = 0

        for java_file in java_files:
            source_code = self._read_file(java_file)
            if source_code is None:
                continue

            relative_path = str(java_file.relative_to(self.source_directory))

            # JPA analysis
            jpa_ast = self.jpa_ast_analyzer.analyze(source_code, relative_path)
            jpa_regex = self.jpa_regex_analyzer.analyze(source_code, relative_path)
            if jpa_ast is None and jpa_regex.mappings:
                parse_warnings += 1
            jpa_merged = self.jpa_merger.merge(jpa_ast, jpa_regex)

            # MyBatis annotation analysis
            mybatis_ast = self.mybatis_anno_analyzer.analyze_ast(source_code, relative_path)
            mybatis_regex = self.mybatis_anno_analyzer.analyze_regex(source_code, relative_path)
            mybatis_merged = self.mybatis_merger.merge(mybatis_ast, mybatis_regex)

            # JDBC analysis
            jdbc_ast = self.jdbc_ast_analyzer.analyze(source_code, relative_path)
            jdbc_regex = self.jdbc_regex_analyzer.analyze(source_code, relative_path)
            jdbc_merged = self.jdbc_merger.merge(jdbc_ast, jdbc_regex)

            # Collect from all frameworks
            for raw in jpa_merged.mappings:
                all_mappings.append(self._enrich(raw, jpa_merged, build_info))
            for raw in mybatis_merged.mappings:
                all_mappings.append(self._enrich(raw, mybatis_merged, build_info))
            for raw in jdbc_merged.mappings:
                all_mappings.append(self._enrich(raw, jdbc_merged, build_info))

        # --- Analyze MyBatis XML mapper files ---
        xml_files = self._find_xml_mappers()
        for xml_file in xml_files:
            xml_content = self._read_file(xml_file)
            if xml_content is None:
                continue

            relative_path = str(xml_file.relative_to(self.source_directory))
            result = self.mybatis_xml_analyzer.analyze(xml_content, relative_path)

            for raw in result.mappings:
                all_mappings.append(self._enrich(raw, result, build_info))

        total_files = len(java_files) + len(xml_files)
        logger.info(
            "Analyzed %d files (%d Java, %d XML). Found %d table mappings. "
            "%d files had parse warnings.",
            total_files,
            len(java_files),
            len(xml_files),
            len(all_mappings),
            parse_warnings,
        )

        return all_mappings

    def _find_files(self, pattern: str) -> list[Path]:
        """Recursively find files matching pattern, skipping excluded directories."""
        files: list[Path] = []
        for path in self.source_directory.rglob(pattern):
            parts = path.relative_to(self.source_directory).parts
            if any(part in _SKIP_DIRS for part in parts):
                continue
            files.append(path)
        return sorted(files)

    def _find_xml_mappers(self) -> list[Path]:
        """Find MyBatis XML mapper files.

        Looks for XML files that contain MyBatis mapper patterns.
        Checks files in typical mapper locations and with mapper-like names.
        """
        candidates: list[Path] = []
        for xml_file in self._find_files("*.xml"):
            name_lower = xml_file.name.lower()
            # Common naming patterns
            if any(p in name_lower for p in ("mapper", "dao", "sqlmap", "mybatis")):
                candidates.append(xml_file)
                continue
            # Check in typical mapper directories
            rel_parts = xml_file.relative_to(self.source_directory).parts
            if any(p in ("mapper", "mappers", "mybatis", "sqlmap", "dao") for p in rel_parts):
                candidates.append(xml_file)
                continue

        # For remaining XML files, do a quick content check
        all_xml = self._find_files("*.xml")
        checked = set(str(c) for c in candidates)
        for xml_file in all_xml:
            if str(xml_file) in checked:
                continue
            # Quick check: read first 500 bytes
            try:
                with open(xml_file, "r", encoding="utf-8") as f:
                    header = f.read(500)
                if "mybatis" in header.lower() or '<mapper' in header:
                    candidates.append(xml_file)
            except (OSError, UnicodeDecodeError):
                pass

        return sorted(set(candidates))

    def _read_file(self, path: Path) -> str | None:
        """Read a file with encoding fallback."""
        for encoding in ("utf-8", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except OSError as e:
                logger.warning("Cannot read %s: %s", path, e)
                return None
        logger.warning("Cannot decode %s, skipping", path)
        return None

    def _enrich(
        self,
        raw: RawMapping,
        file_result: FileAnalysisResult,
        build_info: BuildInfo,
    ) -> TableMapping:
        """Enrich a RawMapping with project/build info to create a TableMapping."""
        framework = raw.framework
        if not framework:
            framework = self._detect_framework_from_imports(
                file_result.imports, build_info,
            )

        java_ee_version = self._detect_ee_version_from_imports(
            file_result.imports, build_info,
        )

        return TableMapping(
            project_name=self.project_name,
            source_file=file_result.source_file,
            package_name=file_result.package_name,
            class_or_method=raw.class_or_method,
            java_version=build_info.java_version,
            java_ee_version=java_ee_version,
            framework=framework,
            table_name=raw.table_name,
            access_type=raw.access_type,
        )

    def _detect_framework_from_imports(
        self, imports: list[str], build_info: BuildInfo,
    ) -> str:
        has_jpa = any(
            i.startswith("javax.persistence") or i.startswith("jakarta.persistence")
            for i in imports
        )
        has_hibernate = any(i.startswith("org.hibernate") for i in imports)
        has_mybatis = any(i.startswith("org.apache.ibatis") for i in imports)
        has_spring_jdbc = any(i.startswith("org.springframework.jdbc") for i in imports)
        has_raw_jdbc = any(i.startswith("java.sql") for i in imports)

        if has_spring_jdbc:
            return "Spring JDBC"
        if has_raw_jdbc:
            return "JDBC"
        if has_mybatis:
            return "MyBatis"
        if has_jpa and has_hibernate:
            return "JPA/Hibernate"
        if has_hibernate:
            return "Hibernate"
        if has_jpa:
            return "JPA"
        if build_info.has_hibernate:
            return "JPA/Hibernate"
        return "JPA"

    def _detect_ee_version_from_imports(
        self, imports: list[str], build_info: BuildInfo,
    ) -> str:
        for imp in imports:
            if imp.startswith("jakarta.persistence"):
                return "Jakarta EE (JPA 3.x+)"
            if imp.startswith("javax.persistence"):
                return "Java EE (JPA 2.x)"
        return build_info.java_ee_version
