"""Data models for Java source analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AccessType(Enum):
    """Database access type."""

    R = "R"
    W = "W"
    RW = "RW"


@dataclass
class TableMapping:
    """Single record of a discovered table mapping.

    Each instance represents one table reference found in a Java source file.
    """

    project_name: str
    source_file: str
    package_name: str
    class_or_method: str
    java_version: str
    java_ee_version: str
    framework: str
    table_name: str
    access_type: str  # "R", "W", "RW"


@dataclass
class RawMapping:
    """Intermediate mapping before enrichment with build/project info."""

    table_name: str
    class_or_method: str
    access_type: str  # "R", "W", "RW"
    framework: str = ""
    annotation: str = ""  # source annotation/pattern that produced this mapping


@dataclass
class FileAnalysisResult:
    """All mappings found in a single Java file."""

    source_file: str
    package_name: str
    imports: list[str] = field(default_factory=list)
    mappings: list[RawMapping] = field(default_factory=list)


@dataclass
class BuildInfo:
    """Java/EE version info detected from build files."""

    java_version: str = "unknown"
    java_ee_version: str = "unknown"
    has_hibernate: bool = False


@dataclass
class SqlTableRef:
    """A table reference extracted from a SQL string."""

    table_name: str
    access_type: str  # "R" or "W"
