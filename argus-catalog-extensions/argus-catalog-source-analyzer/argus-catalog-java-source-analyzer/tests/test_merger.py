"""Tests for result merger."""

from java_source_analyzer.jpa.merger import ResultMerger
from java_source_analyzer.models import FileAnalysisResult, RawMapping


class TestResultMerger:

    def setup_method(self):
        self.merger = ResultMerger()

    def test_ast_none_returns_regex(self):
        regex_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="Test", access_type="RW"),
            ],
        )
        result = self.merger.merge(None, regex_result)
        assert result is regex_result

    def test_deduplication(self):
        ast_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="User", access_type="RW",
                           framework="JPA", annotation="@Table"),
            ],
        )
        regex_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="User", access_type="RW",
                           framework="JPA", annotation="@Table"),
            ],
        )
        result = self.merger.merge(ast_result, regex_result)
        assert len(result.mappings) == 1

    def test_regex_adds_new_tables(self):
        ast_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="User", access_type="RW"),
            ],
        )
        regex_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="User", access_type="RW"),
                RawMapping(table_name="user_details", class_or_method="User", access_type="RW"),
            ],
        )
        result = self.merger.merge(ast_result, regex_result)
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names
        assert "user_details" in table_names

    def test_access_type_merge(self):
        ast_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="UserRepo", access_type="R"),
            ],
        )
        regex_result = FileAnalysisResult(
            source_file="Test.java",
            package_name="com.test",
            mappings=[
                RawMapping(table_name="users", class_or_method="UserRepo", access_type="W"),
            ],
        )
        result = self.merger.merge(ast_result, regex_result)
        assert len(result.mappings) == 1
        assert result.mappings[0].access_type == "RW"
