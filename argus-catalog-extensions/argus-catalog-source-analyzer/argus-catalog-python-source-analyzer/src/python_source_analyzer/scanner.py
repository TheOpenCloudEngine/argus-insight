"""Top-level orchestrator for Python source analysis."""

from __future__ import annotations

import logging
from pathlib import Path

from python_source_analyzer.dbapi_analyzer.ast_analyzer import DbApiAstAnalyzer
from python_source_analyzer.dbapi_analyzer.regex_analyzer import DbApiRegexAnalyzer
from python_source_analyzer.django_analyzer.ast_analyzer import DjangoAstAnalyzer
from python_source_analyzer.django_analyzer.regex_analyzer import DjangoRegexAnalyzer
from python_source_analyzer.merger import ResultMerger
from python_source_analyzer.models import FileAnalysisResult, ProjectInfo, RawMapping, TableMapping
from python_source_analyzer.project_detector import ProjectDetector
from python_source_analyzer.sqlalchemy_analyzer.ast_analyzer import SqlAlchemyAstAnalyzer
from python_source_analyzer.sqlalchemy_analyzer.regex_analyzer import SqlAlchemyRegexAnalyzer

logger = logging.getLogger(__name__)

_SKIP_DIRS = {
    "__pycache__", ".git", ".svn", ".tox", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env", ".eggs", "node_modules", "dist", "build",
    "*.egg-info",
}


class PythonSourceScanner:
    """Orchestrates scanning of a Python project directory."""

    def __init__(self, project_name: str, source_directory: str | Path) -> None:
        self.project_name = project_name
        self.source_directory = Path(source_directory).resolve()
        self.project_detector = ProjectDetector()
        self.merger = ResultMerger()
        # SQLAlchemy
        self.sa_ast = SqlAlchemyAstAnalyzer()
        self.sa_regex = SqlAlchemyRegexAnalyzer()
        # Django
        self.dj_ast = DjangoAstAnalyzer()
        self.dj_regex = DjangoRegexAnalyzer()
        # DB-API
        self.dbapi_ast = DbApiAstAnalyzer()
        self.dbapi_regex = DbApiRegexAnalyzer()

    def scan(self) -> list[TableMapping]:
        if not self.source_directory.is_dir():
            logger.error("Directory not found: %s", self.source_directory)
            return []

        project_info = self.project_detector.detect(self.source_directory)
        logger.info("Project info: Python %s", project_info.python_version)

        py_files = self._find_python_files()
        if not py_files:
            logger.info("No Python files found in %s", self.source_directory)
            return []

        all_mappings: list[TableMapping] = []
        parse_warnings = 0

        for py_file in py_files:
            source_code = self._read_file(py_file)
            if source_code is None:
                continue

            relative_path = str(py_file.relative_to(self.source_directory))
            module_path = self._to_module_path(py_file)

            # Run all framework analyzers
            results: list[FileAnalysisResult] = []

            for ast_analyzer, regex_analyzer in [
                (self.sa_ast, self.sa_regex),
                (self.dj_ast, self.dj_regex),
                (self.dbapi_ast, self.dbapi_regex),
            ]:
                ast_result = ast_analyzer.analyze(source_code, relative_path)
                regex_result = regex_analyzer.analyze(source_code, relative_path)
                if ast_result is None and regex_result.mappings:
                    parse_warnings += 1
                merged = self.merger.merge(ast_result, regex_result)
                if merged.mappings:
                    results.append(merged)

            # Enrich and collect
            for result in results:
                result.module_path = result.module_path or module_path
                for raw in result.mappings:
                    all_mappings.append(self._enrich(raw, result, project_info))

        logger.info(
            "Analyzed %d Python files. Found %d table mappings. %d parse warnings.",
            len(py_files), len(all_mappings), parse_warnings,
        )
        return all_mappings

    def _find_python_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.source_directory.rglob("*.py"):
            parts = path.relative_to(self.source_directory).parts
            if any(part in _SKIP_DIRS or part.endswith(".egg-info") for part in parts):
                continue
            files.append(path)
        return sorted(files)

    def _read_file(self, path: Path) -> str | None:
        for encoding in ("utf-8", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except OSError as e:
                logger.warning("Cannot read %s: %s", path, e)
                return None
        return None

    def _to_module_path(self, py_file: Path) -> str:
        """Convert file path to Python module path."""
        relative = py_file.relative_to(self.source_directory)
        parts = list(relative.parts)
        if parts and parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts:
            parts[-1] = parts[-1].removesuffix(".py")
        return ".".join(parts)

    def _enrich(
        self, raw: RawMapping, result: FileAnalysisResult, info: ProjectInfo,
    ) -> TableMapping:
        return TableMapping(
            project_name=self.project_name,
            source_file=result.source_file,
            module_path=result.module_path,
            class_or_function=raw.class_or_function,
            python_version=info.python_version,
            framework=raw.framework,
            table_name=raw.table_name,
            access_type=raw.access_type,
        )
