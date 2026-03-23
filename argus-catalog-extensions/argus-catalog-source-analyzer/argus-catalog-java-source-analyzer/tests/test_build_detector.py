"""Tests for build detector."""

from pathlib import Path

from java_source_analyzer.build_detector import BuildDetector

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestBuildDetector:

    def setup_method(self):
        self.detector = BuildDetector()

    def test_pom_java17_jakarta(self):
        info = self.detector._parse_pom(FIXTURES_DIR / "pom_java17.xml")
        assert info.java_version == "17"
        assert info.java_ee_version == "Jakarta EE (JPA 3.x+)"
        assert info.has_hibernate is True

    def test_pom_java11_javax(self):
        info = self.detector._parse_pom(FIXTURES_DIR / "pom_java11.xml")
        # java.version property with ${} reference — we detect the property value
        assert info.java_ee_version == "Java EE (JPA 2.x)"
        assert info.has_hibernate is True

    def test_detect_from_directory_with_pom(self, tmp_path):
        """detect() finds pom.xml in the given directory."""
        import shutil
        shutil.copy(FIXTURES_DIR / "pom_java17.xml", tmp_path / "pom.xml")
        info = self.detector.detect(tmp_path)
        assert info.java_version == "17"
        assert info.java_ee_version == "Jakarta EE (JPA 3.x+)"

    def test_normalize_java_version(self):
        assert BuildDetector._normalize_java_version("1.8") == "8"
        assert BuildDetector._normalize_java_version("11") == "11"
        assert BuildDetector._normalize_java_version("17") == "17"
        assert BuildDetector._normalize_java_version("VERSION_17") == "17"
