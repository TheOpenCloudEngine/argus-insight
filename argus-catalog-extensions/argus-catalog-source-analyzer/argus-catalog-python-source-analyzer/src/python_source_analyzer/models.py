"""Data models for Python source analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TableMapping:
    """Single record of a discovered table mapping."""

    project_name: str
    source_file: str
    module_path: str  # Python module path (e.g., "myapp.models")
    class_or_function: str
    python_version: str
    framework: str  # "SQLAlchemy", "Django ORM", "DB-API", etc.
    table_name: str
    access_type: str  # "R", "W", "RW"


@dataclass
class RawMapping:
    """Intermediate mapping before enrichment."""

    table_name: str
    class_or_function: str
    access_type: str  # "R", "W", "RW"
    framework: str = ""
    pattern: str = ""  # source pattern that produced this mapping


@dataclass
class FileAnalysisResult:
    """All mappings found in a single Python file."""

    source_file: str
    module_path: str
    imports: list[str] = field(default_factory=list)
    mappings: list[RawMapping] = field(default_factory=list)


@dataclass
class ProjectInfo:
    """Python project version info from pyproject.toml / setup.py."""

    python_version: str = "unknown"


@dataclass
class SqlTableRef:
    """A table reference extracted from a SQL string."""

    table_name: str
    access_type: str  # "R" or "W"
