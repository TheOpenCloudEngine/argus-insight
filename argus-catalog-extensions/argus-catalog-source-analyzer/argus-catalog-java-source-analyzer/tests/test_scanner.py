"""Integration tests for JavaSourceScanner."""

import tempfile
from pathlib import Path

from java_source_analyzer.scanner import JavaSourceScanner

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestJavaSourceScanner:

    def test_scan_fixtures_directory(self):
        """Integration test: scan the test fixtures directory."""
        scanner = JavaSourceScanner("test-project", FIXTURES_DIR)
        mappings = scanner.scan()

        # Should find tables from all fixture files
        assert len(mappings) > 0

        table_names = {m.table_name for m in mappings}
        assert "users" in table_names
        assert "orders" in table_names
        assert "products" in table_names

        # All should have the project name
        assert all(m.project_name == "test-project" for m in mappings)

    def test_scan_empty_directory(self):
        """Scanning an empty directory returns no mappings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = JavaSourceScanner("empty", tmpdir)
            mappings = scanner.scan()
            assert mappings == []

    def test_scan_nonexistent_directory(self):
        """Scanning a nonexistent directory returns no mappings."""
        scanner = JavaSourceScanner("test", "/nonexistent/path")
        mappings = scanner.scan()
        assert mappings == []

    def test_output_fields_complete(self):
        """All output fields should be populated."""
        scanner = JavaSourceScanner("my-project", FIXTURES_DIR)
        mappings = scanner.scan()

        for m in mappings:
            assert m.project_name == "my-project"
            assert m.source_file  # not empty
            assert m.class_or_method  # not empty
            assert m.table_name  # not empty
            assert m.access_type in ("R", "W", "RW")
            assert m.framework in ("JPA", "Hibernate", "JPA/Hibernate", "MyBatis", "Spring JDBC", "JDBC")
