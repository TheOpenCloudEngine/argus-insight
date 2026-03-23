"""Detect Python version from project configuration files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from python_source_analyzer.models import ProjectInfo

logger = logging.getLogger(__name__)

_RE_REQUIRES_PYTHON = re.compile(r'requires-python\s*=\s*"([^"]+)"')
_RE_PYTHON_REQUIRES = re.compile(r"python_requires\s*=\s*['\"]([^'\"]+)['\"]")
_RE_CLASSIFIERS_VERSION = re.compile(
    r"Programming Language :: Python :: (\d+\.?\d*)",
)


class ProjectDetector:
    """Detects Python version from pyproject.toml, setup.py, or setup.cfg."""

    def detect(self, source_directory: str | Path) -> ProjectInfo:
        info = ProjectInfo()
        source_dir = Path(source_directory).resolve()

        current = source_dir
        for _ in range(6):
            for detector in (self._from_pyproject, self._from_setup_py, self._from_setup_cfg):
                result = detector(current)
                if result and result.python_version != "unknown":
                    return result

            parent = current.parent
            if parent == current:
                break
            current = parent

        return info

    def _from_pyproject(self, directory: Path) -> ProjectInfo | None:
        path = directory / "pyproject.toml"
        if not path.is_file():
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None

        m = _RE_REQUIRES_PYTHON.search(content)
        if m:
            return ProjectInfo(python_version=self._normalize(m.group(1)))
        return None

    def _from_setup_py(self, directory: Path) -> ProjectInfo | None:
        path = directory / "setup.py"
        if not path.is_file():
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None

        m = _RE_PYTHON_REQUIRES.search(content)
        if m:
            return ProjectInfo(python_version=self._normalize(m.group(1)))

        versions = _RE_CLASSIFIERS_VERSION.findall(content)
        if versions:
            return ProjectInfo(python_version=max(versions))
        return None

    def _from_setup_cfg(self, directory: Path) -> ProjectInfo | None:
        path = directory / "setup.cfg"
        if not path.is_file():
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None

        m = _RE_PYTHON_REQUIRES.search(content)
        if m:
            return ProjectInfo(python_version=self._normalize(m.group(1)))
        return None

    @staticmethod
    def _normalize(version_spec: str) -> str:
        """Extract version number from spec like '>=3.11' or '~=3.10'."""
        m = re.search(r"(\d+\.\d+)", version_spec)
        return m.group(1) if m else version_spec.strip()
