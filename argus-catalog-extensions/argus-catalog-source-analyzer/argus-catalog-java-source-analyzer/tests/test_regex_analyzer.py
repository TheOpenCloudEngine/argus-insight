"""Tests for JPA regex analyzer."""

from java_source_analyzer.jpa.regex_analyzer import JpaRegexAnalyzer


class TestJpaRegexAnalyzer:

    def setup_method(self):
        self.analyzer = JpaRegexAnalyzer()

    def test_entity_with_table(self, sample_entity_source):
        result = self.analyzer.analyze(sample_entity_source, "User.java")
        assert result.package_name == "com.example.domain"

        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names
        assert "user_details" in table_names
        assert "user_roles" in table_names

    def test_entity_without_table(self, sample_entity_no_table_source):
        result = self.analyzer.analyze(sample_entity_no_table_source, "Category.java")
        mappings = result.mappings
        assert len(mappings) >= 1
        table_names = {m.table_name for m in mappings}
        assert "Category" in table_names

    def test_named_native_query(self, sample_named_query_source):
        result = self.analyzer.analyze(sample_named_query_source, "Order.java")
        table_names = {m.table_name for m in result.mappings}
        assert "orders" in table_names

    def test_create_native_query(self, sample_repository_source):
        result = self.analyzer.analyze(sample_repository_source, "UserRepository.java")
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

    def test_framework_detection_javax(self, sample_entity_source):
        result = self.analyzer.analyze(sample_entity_source, "User.java")
        frameworks = {m.framework for m in result.mappings}
        assert "JPA" in frameworks

    def test_framework_detection_jakarta_hibernate(self, sample_jakarta_source):
        result = self.analyzer.analyze(sample_jakarta_source, "Product.java")
        frameworks = {m.framework for m in result.mappings}
        assert "JPA/Hibernate" in frameworks

    def test_non_jpa_file(self):
        source = """
        package com.example.util;

        public class StringHelper {
            public static String trim(String s) {
                return s.trim();
            }
        }
        """
        result = self.analyzer.analyze(source, "StringHelper.java")
        assert len(result.mappings) == 0

    def test_access_type_for_update(self, sample_repository_source):
        result = self.analyzer.analyze(sample_repository_source, "UserRepository.java")
        # Find UPDATE users mapping
        update_mappings = [
            m for m in result.mappings
            if m.table_name == "users" and m.access_type == "W"
        ]
        assert len(update_mappings) >= 1
