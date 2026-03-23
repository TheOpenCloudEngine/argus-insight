"""Integration tests for PythonSourceScanner."""

import tempfile
from pathlib import Path

from python_source_analyzer.scanner import PythonSourceScanner

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPythonSourceScanner:

    def test_scan_fixtures(self):
        scanner = PythonSourceScanner("test-project", FIXTURES_DIR)
        mappings = scanner.scan()

        assert len(mappings) > 0
        table_names = {m.table_name for m in mappings}
        # SQLAlchemy
        assert "users" in table_names
        assert "orders" in table_names
        # Django
        assert "authors" in table_names
        assert "books" in table_names
        # DB-API
        assert "tasks" in table_names

        assert all(m.project_name == "test-project" for m in mappings)

    def test_scan_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = PythonSourceScanner("empty", tmpdir)
            assert scanner.scan() == []

    def test_scan_nonexistent(self):
        scanner = PythonSourceScanner("test", "/nonexistent")
        assert scanner.scan() == []

    def test_output_fields(self):
        scanner = PythonSourceScanner("my-project", FIXTURES_DIR)
        mappings = scanner.scan()

        frameworks = set()
        for m in mappings:
            assert m.project_name == "my-project"
            assert m.source_file
            assert m.class_or_function
            assert m.table_name
            assert m.access_type in ("R", "W", "RW")
            frameworks.add(m.framework)

        # Should have found multiple frameworks
        assert len(frameworks) >= 2
