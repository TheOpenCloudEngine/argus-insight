"""Tests for MyBatis annotation analyzer."""

from pathlib import Path

from java_source_analyzer.mybatis.annotation_analyzer import MyBatisAnnotationAnalyzer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestMyBatisAnnotationAnalyzer:

    def setup_method(self):
        self.analyzer = MyBatisAnnotationAnalyzer()

    def _load_fixture(self):
        return (FIXTURES_DIR / "sample_mybatis_annotation.java").read_text()

    def test_ast_select(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_ast(source, "OrderMapper.java")
        assert result is not None

        table_names = {m.table_name for m in result.mappings}
        assert "orders" in table_names

    def test_ast_insert(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_ast(source, "OrderMapper.java")
        assert result is not None

        insert_mappings = [m for m in result.mappings if m.access_type == "W" and "insert" in m.class_or_method.lower()]
        assert any(m.table_name == "orders" for m in insert_mappings)

    def test_ast_update(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_ast(source, "OrderMapper.java")
        assert result is not None

        update_mappings = [m for m in result.mappings if "updateStatus" in m.class_or_method]
        assert any(m.table_name == "orders" and m.access_type == "W" for m in update_mappings)

    def test_ast_delete(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_ast(source, "OrderMapper.java")
        assert result is not None

        delete_mappings = [m for m in result.mappings if "deleteById" in m.class_or_method]
        assert any(m.table_name == "orders" and m.access_type == "W" for m in delete_mappings)

    def test_ast_join(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_ast(source, "OrderMapper.java")
        assert result is not None

        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names  # from JOIN in findByStatusWithUser

    def test_ast_framework(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_ast(source, "OrderMapper.java")
        assert result is not None
        assert all(m.framework == "MyBatis" for m in result.mappings)

    def test_regex_select(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_regex(source, "OrderMapper.java")

        table_names = {m.table_name for m in result.mappings}
        assert "orders" in table_names

    def test_regex_insert(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_regex(source, "OrderMapper.java")

        insert_mappings = [m for m in result.mappings if m.access_type == "W"]
        assert any(m.table_name == "orders" for m in insert_mappings)

    def test_regex_multi_string_annotation(self):
        source = self._load_fixture()
        result = self.analyzer.analyze_regex(source, "OrderMapper.java")

        table_names = {m.table_name for m in result.mappings}
        # Multi-string @Select with order_items
        assert "order_items" in table_names

    def test_non_mybatis_file(self):
        source = """
        package com.example.service;

        public class UserService {
            public void doSomething() {}
        }
        """
        result = self.analyzer.analyze_regex(source, "UserService.java")
        assert len(result.mappings) == 0

    def test_ast_non_mybatis_returns_empty(self):
        source = """
        package com.example.service;

        public class UserService {
            public void doSomething() {}
        }
        """
        result = self.analyzer.analyze_ast(source, "UserService.java")
        assert result is not None
        assert len(result.mappings) == 0
