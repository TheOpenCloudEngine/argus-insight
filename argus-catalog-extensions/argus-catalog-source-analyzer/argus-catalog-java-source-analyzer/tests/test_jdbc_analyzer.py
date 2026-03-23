"""Tests for JDBC analyzers (AST + regex)."""

from pathlib import Path

from java_source_analyzer.jdbc.ast_analyzer import JdbcAstAnalyzer
from java_source_analyzer.jdbc.regex_analyzer import JdbcRegexAnalyzer
from java_source_analyzer.jdbc.merger import JdbcResultMerger

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name):
    return (FIXTURES_DIR / name).read_text()


class TestJdbcAstAnalyzerSpringJdbc:

    def setup_method(self):
        self.analyzer = JdbcAstAnalyzer()
        self.source = _load("sample_spring_jdbc.java")

    def test_query(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_query_for_list(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        assert result is not None
        orders_mappings = [m for m in result.mappings if m.table_name == "orders"]
        assert any(m.access_type == "R" for m in orders_mappings)

    def test_update_insert(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        assert result is not None
        insert_mappings = [
            m for m in result.mappings
            if "insert" in m.class_or_method.lower() and m.table_name == "users"
        ]
        assert any(m.access_type == "W" for m in insert_mappings)

    def test_batch_update(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "user_roles" in table_names

    def test_framework_detection(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        assert result is not None
        frameworks = {m.framework for m in result.mappings}
        assert "Spring JDBC" in frameworks

    def test_non_jdbc_file(self):
        source = """
        package com.example;
        public class Foo { public void bar() {} }
        """
        result = self.analyzer.analyze(source, "Foo.java")
        assert result is not None
        assert len(result.mappings) == 0


class TestJdbcAstAnalyzerRawJdbc:

    def setup_method(self):
        self.analyzer = JdbcAstAnalyzer()
        self.source = _load("sample_raw_jdbc.java")

    def test_execute_query(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_execute_update_delete(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        assert result is not None
        delete_mappings = [
            m for m in result.mappings
            if "deleteOldOrders" in m.class_or_method and m.table_name == "orders"
        ]
        assert any(m.access_type == "W" for m in delete_mappings)

    def test_prepare_statement(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_framework_is_jdbc(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        assert result is not None
        frameworks = {m.framework for m in result.mappings}
        assert "JDBC" in frameworks


class TestJdbcRegexAnalyzerSpringJdbc:

    def setup_method(self):
        self.analyzer = JdbcRegexAnalyzer()
        self.source = _load("sample_spring_jdbc.java")

    def test_query_tables(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names
        assert "orders" in table_names

    def test_insert(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        insert_mappings = [m for m in result.mappings if m.access_type == "W" and m.table_name == "users"]
        assert len(insert_mappings) >= 1

    def test_batch_update(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        table_names = {m.table_name for m in result.mappings}
        assert "user_roles" in table_names

    def test_execute(self):
        result = self.analyzer.analyze(self.source, "UserJdbcRepository.java")
        table_names = {m.table_name for m in result.mappings}
        assert "audit_log" in table_names


class TestJdbcRegexAnalyzerRawJdbc:

    def setup_method(self):
        self.analyzer = JdbcRegexAnalyzer()
        self.source = _load("sample_raw_jdbc.java")

    def test_execute_query(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_execute_update(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        delete_mappings = [m for m in result.mappings if m.table_name == "orders" and m.access_type == "W"]
        assert len(delete_mappings) >= 1

    def test_prepare_statement_with_join(self):
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        table_names = {m.table_name for m in result.mappings}
        assert "order_items" in table_names

    def test_sql_variable_assignment(self):
        """Should detect SQL in String sql = '...' patterns."""
        result = self.analyzer.analyze(self.source, "LegacyUserDao.java")
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names


class TestJdbcMerger:

    def test_deduplication(self):
        from java_source_analyzer.models import FileAnalysisResult, RawMapping

        ast_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="Dao.find", access_type="R",
                           framework="Spring JDBC"),
            ],
        )
        regex_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="Dao.find", access_type="R",
                           framework="Spring JDBC"),
                RawMapping(table_name="orders", class_or_method="Dao.find", access_type="R",
                           framework="Spring JDBC"),
            ],
        )
        merger = JdbcResultMerger()
        result = merger.merge(ast_result, regex_result)
        assert len(result.mappings) == 2
        table_names = {m.table_name for m in result.mappings}
        assert table_names == {"users", "orders"}
