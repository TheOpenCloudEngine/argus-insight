"""Tests for DB-API analyzers."""

from tests.conftest import load_fixture
from python_source_analyzer.dbapi_analyzer.ast_analyzer import DbApiAstAnalyzer
from python_source_analyzer.dbapi_analyzer.regex_analyzer import DbApiRegexAnalyzer


class TestDbApiAstPsycopg2:

    def setup_method(self):
        self.analyzer = DbApiAstAnalyzer()
        self.source = load_fixture("sample_psycopg2.py")

    def test_select(self):
        result = self.analyzer.analyze(self.source, "repo.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_insert(self):
        result = self.analyzer.analyze(self.source, "repo.py")
        assert result is not None
        insert_mappings = [m for m in result.mappings if m.access_type == "W" and m.table_name == "users"]
        assert len(insert_mappings) >= 1

    def test_delete(self):
        result = self.analyzer.analyze(self.source, "repo.py")
        assert result is not None
        delete_mappings = [m for m in result.mappings if m.table_name == "users" and m.access_type == "W"]
        assert len(delete_mappings) >= 1

    def test_executemany(self):
        result = self.analyzer.analyze(self.source, "repo.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "audit_log" in table_names

    def test_framework_detection(self):
        result = self.analyzer.analyze(self.source, "repo.py")
        assert result is not None
        frameworks = {m.framework for m in result.mappings}
        assert any("psycopg2" in f for f in frameworks)

    def test_orders_table(self):
        result = self.analyzer.analyze(self.source, "repo.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "orders" in table_names


class TestDbApiAstSqlite3:

    def setup_method(self):
        self.analyzer = DbApiAstAnalyzer()
        self.source = load_fixture("sample_sqlite3.py")

    def test_select(self):
        result = self.analyzer.analyze(self.source, "tasks.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "tasks" in table_names

    def test_crud_access_types(self):
        result = self.analyzer.analyze(self.source, "tasks.py")
        assert result is not None
        task_mappings = [m for m in result.mappings if m.table_name == "tasks"]
        access_types = {m.access_type for m in task_mappings}
        assert "R" in access_types
        assert "W" in access_types

    def test_framework_detection(self):
        result = self.analyzer.analyze(self.source, "tasks.py")
        assert result is not None
        frameworks = {m.framework for m in result.mappings}
        assert any("sqlite3" in f for f in frameworks)


class TestDbApiRegexPsycopg2:

    def setup_method(self):
        self.regex = DbApiRegexAnalyzer()
        self.source = load_fixture("sample_psycopg2.py")

    def test_execute(self):
        result = self.regex.analyze(self.source, "repo.py")
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_executemany(self):
        result = self.regex.analyze(self.source, "repo.py")
        table_names = {m.table_name for m in result.mappings}
        assert "audit_log" in table_names

    def test_orders(self):
        result = self.regex.analyze(self.source, "repo.py")
        table_names = {m.table_name for m in result.mappings}
        assert "orders" in table_names


class TestDbApiRegexSqlite3:

    def setup_method(self):
        self.regex = DbApiRegexAnalyzer()
        self.source = load_fixture("sample_sqlite3.py")

    def test_tables(self):
        result = self.regex.analyze(self.source, "tasks.py")
        table_names = {m.table_name for m in result.mappings}
        assert "tasks" in table_names

    def test_non_dbapi_file(self):
        source = "def hello(): print('hello')"
        result = self.regex.analyze(source, "hello.py")
        assert len(result.mappings) == 0
