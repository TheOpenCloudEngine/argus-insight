"""Detect Java version and Java EE version from build files (pom.xml, build.gradle)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from java_source_analyzer.models import BuildInfo

logger = logging.getLogger(__name__)

# Gradle patterns
_RE_SOURCE_COMPAT = re.compile(
    r'sourceCompatibility\s*=\s*["\']?([^"\';\s]+)',
)
_RE_TARGET_COMPAT = re.compile(
    r'targetCompatibility\s*=\s*["\']?([^"\';\s]+)',
)
_RE_JAVA_VERSION_ENUM = re.compile(
    r'JavaVersion\.VERSION_(\d+)',
)
_RE_JAVA_TOOLCHAIN = re.compile(
    r'languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)',
)
_RE_GRADLE_JAVAX = re.compile(
    r'["\']javax\.persistence[:\']',
)
_RE_GRADLE_JAKARTA = re.compile(
    r'["\']jakarta\.persistence[:\']',
)
_RE_GRADLE_HIBERNATE = re.compile(
    r'["\']org\.hibernate[:\']',
)

# Maven namespace
_NS = {"m": "http://maven.apache.org/POM/4.0.0"}


class BuildDetector:
    """Detects Java version and Java EE version from project build files."""

    def detect(self, source_directory: str | Path) -> BuildInfo:
        """Search for build files and extract version information.

        Walks upward from source_directory (max 5 levels) looking for
        pom.xml or build.gradle.
        """
        source_dir = Path(source_directory).resolve()
        build_info = BuildInfo()

        # Search upward for build files
        current = source_dir
        for _ in range(6):  # current + 5 parents
            pom = current / "pom.xml"
            if pom.is_file():
                build_info = self._parse_pom(pom)
                if build_info.java_version != "unknown":
                    return build_info

            gradle = current / "build.gradle"
            gradle_kts = current / "build.gradle.kts"
            for gf in (gradle, gradle_kts):
                if gf.is_file():
                    build_info = self._parse_gradle(gf)
                    if build_info.java_version != "unknown":
                        return build_info

            parent = current.parent
            if parent == current:
                break
            current = parent

        return build_info

    def _parse_pom(self, pom_path: Path) -> BuildInfo:
        """Parse pom.xml for Java/EE version information."""
        info = BuildInfo()
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
        except ET.ParseError:
            logger.warning("Failed to parse pom.xml: %s", pom_path)
            return info

        # Detect namespace
        ns = _NS if root.tag.startswith("{") else {"m": ""}
        prefix = "m:" if ns["m"] else ""

        # Extract properties for Java version
        props = root.find(f"{prefix}properties", ns) if ns["m"] else root.find("properties")
        if props is not None:
            for prop_name in (
                "maven.compiler.source",
                "maven.compiler.target",
                "maven.compiler.release",
                "java.version",
            ):
                el = props.find(f"{prefix}{prop_name}", ns) if ns["m"] else props.find(prop_name)
                if el is not None and el.text:
                    info.java_version = self._normalize_java_version(el.text.strip())
                    break

        # Check compiler plugin configuration
        if info.java_version == "unknown":
            info.java_version = self._find_compiler_plugin_version(root, ns, prefix)

        # Scan dependencies for JPA/Hibernate
        self._detect_dependencies_pom(root, info, ns, prefix)

        return info

    def _find_compiler_plugin_version(
        self, root: ET.Element, ns: dict, prefix: str,
    ) -> str:
        """Look for maven-compiler-plugin configuration."""
        for plugin in root.iter(f"{{{ns['m']}}}plugin" if ns["m"] else "plugin"):
            artifact_id = plugin.find(
                f"{prefix}artifactId", ns,
            ) if ns["m"] else plugin.find("artifactId")
            if artifact_id is not None and artifact_id.text == "maven-compiler-plugin":
                config = plugin.find(
                    f"{prefix}configuration", ns,
                ) if ns["m"] else plugin.find("configuration")
                if config is not None:
                    for tag in ("release", "source", "target"):
                        el = config.find(
                            f"{prefix}{tag}", ns,
                        ) if ns["m"] else config.find(tag)
                        if el is not None and el.text:
                            return self._normalize_java_version(el.text.strip())
        return "unknown"

    def _detect_dependencies_pom(
        self, root: ET.Element, info: BuildInfo, ns: dict, prefix: str,
    ) -> None:
        """Detect javax/jakarta persistence and Hibernate from pom dependencies."""
        for dep in root.iter(f"{{{ns['m']}}}dependency" if ns["m"] else "dependency"):
            group_el = dep.find(
                f"{prefix}groupId", ns,
            ) if ns["m"] else dep.find("groupId")
            if group_el is None or not group_el.text:
                continue
            group_id = group_el.text.strip()

            if group_id == "javax.persistence" or group_id.startswith("javax.persistence"):
                info.java_ee_version = "Java EE (JPA 2.x)"
            elif group_id == "jakarta.persistence" or group_id.startswith("jakarta.persistence"):
                info.java_ee_version = "Jakarta EE (JPA 3.x+)"

            # Also check artifactId for javax.persistence-api / jakarta.persistence-api
            artifact_el = dep.find(
                f"{prefix}artifactId", ns,
            ) if ns["m"] else dep.find("artifactId")
            if artifact_el is not None and artifact_el.text:
                artifact = artifact_el.text.strip()
                if "javax.persistence" in artifact:
                    info.java_ee_version = "Java EE (JPA 2.x)"
                elif "jakarta.persistence" in artifact:
                    info.java_ee_version = "Jakarta EE (JPA 3.x+)"

            # Check for Hibernate
            if "hibernate" in group_id.lower():
                info.has_hibernate = True
                # hibernate-core 6.x+ uses Jakarta
                if info.java_ee_version == "unknown":
                    artifact_el = dep.find(
                        f"{prefix}artifactId", ns,
                    ) if ns["m"] else dep.find("artifactId")
                    version_el = dep.find(
                        f"{prefix}version", ns,
                    ) if ns["m"] else dep.find("version")
                    if version_el is not None and version_el.text:
                        ver = version_el.text.strip()
                        if ver.startswith("6") or ver.startswith("7"):
                            info.java_ee_version = "Jakarta EE (JPA 3.x+)"
                        else:
                            info.java_ee_version = "Java EE (JPA 2.x)"

            # Spring Boot starter data jpa
            if artifact_el is not None and artifact_el.text:
                artifact = artifact_el.text.strip()
                if artifact == "spring-boot-starter-data-jpa":
                    info.has_hibernate = True
                    if info.java_ee_version == "unknown":
                        # Spring Boot 3.x+ uses Jakarta
                        version_el = dep.find(
                            f"{prefix}version", ns,
                        ) if ns["m"] else dep.find("version")
                        if version_el is not None and version_el.text:
                            ver = version_el.text.strip()
                            if ver.startswith("3") or ver.startswith("4"):
                                info.java_ee_version = "Jakarta EE (JPA 3.x+)"
                            else:
                                info.java_ee_version = "Java EE (JPA 2.x)"

    def _parse_gradle(self, gradle_path: Path) -> BuildInfo:
        """Parse build.gradle for Java/EE version information."""
        info = BuildInfo()
        try:
            content = gradle_path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Failed to read gradle file: %s", gradle_path)
            return info

        # Java version from sourceCompatibility
        for pattern in (_RE_SOURCE_COMPAT, _RE_TARGET_COMPAT, _RE_JAVA_VERSION_ENUM, _RE_JAVA_TOOLCHAIN):
            m = pattern.search(content)
            if m:
                info.java_version = self._normalize_java_version(m.group(1))
                break

        # Dependencies
        if _RE_GRADLE_JAVAX.search(content):
            info.java_ee_version = "Java EE (JPA 2.x)"
        if _RE_GRADLE_JAKARTA.search(content):
            info.java_ee_version = "Jakarta EE (JPA 3.x+)"
        if _RE_GRADLE_HIBERNATE.search(content):
            info.has_hibernate = True

        return info

    @staticmethod
    def _normalize_java_version(version: str) -> str:
        """Normalize Java version strings like '1.8' -> '8', '11' -> '11'."""
        version = version.strip()
        if version.startswith("1."):
            return version[2:]
        # Handle JavaVersion.VERSION_17 style
        if version.startswith("VERSION_"):
            return version[8:]
        return version
