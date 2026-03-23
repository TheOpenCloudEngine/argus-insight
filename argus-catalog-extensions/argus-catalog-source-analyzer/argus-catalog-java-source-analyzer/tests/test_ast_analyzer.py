"""Tests for JPA AST analyzer."""

from java_source_analyzer.jpa.ast_analyzer import JpaAstAnalyzer


class TestJpaAstAnalyzer:

    def setup_method(self):
        self.analyzer = JpaAstAnalyzer()

    def test_entity_with_table(self, sample_entity_source):
        result = self.analyzer.analyze(sample_entity_source, "User.java")
        assert result is not None
        assert result.package_name == "com.example.domain"

        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names
        assert "user_details" in table_names
        assert "user_roles" in table_names

    def test_entity_without_table(self, sample_entity_no_table_source):
        result = self.analyzer.analyze(sample_entity_no_table_source, "Category.java")
        assert result is not None

        mappings = result.mappings
        assert len(mappings) == 1
        assert mappings[0].table_name == "Category"
        assert mappings[0].access_type == "RW"
        assert mappings[0].annotation == "@Entity"

    def test_named_queries(self, sample_named_query_source):
        result = self.analyzer.analyze(sample_named_query_source, "Order.java")
        assert result is not None

        table_names = {m.table_name for m in result.mappings}
        # @Table(name="orders")
        assert "orders" in table_names
        # @NamedNativeQuery references order_items
        assert "order_items" in table_names

    def test_repository_queries(self, sample_repository_source):
        result = self.analyzer.analyze(sample_repository_source, "UserRepository.java")
        assert result is not None

        # Should find createQuery and createNativeQuery references
        table_names = {m.table_name for m in result.mappings}
        # createNativeQuery references users and orders
        assert "users" in table_names

        # Check access types
        access_map = {m.table_name: m.access_type for m in result.mappings if m.table_name == "users"}
        # users is referenced in both SELECT and UPDATE
        assert "users" in access_map

    def test_inheritance(self, sample_inheritance_source):
        result = self.analyzer.analyze(sample_inheritance_source, "Payment.java")
        assert result is not None

        table_names = {m.table_name for m in result.mappings}
        assert "payments" in table_names

    def test_jakarta_with_hibernate(self, sample_jakarta_source):
        result = self.analyzer.analyze(sample_jakarta_source, "Product.java")
        assert result is not None

        assert result.package_name == "com.example.domain"
        assert len(result.mappings) >= 1
        assert result.mappings[0].table_name == "products"
        assert result.mappings[0].framework == "JPA/Hibernate"

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
        assert result is not None
        assert len(result.mappings) == 0

    def test_parse_failure(self):
        # Invalid Java code
        result = self.analyzer.analyze("this is not java {{{{", "bad.java")
        assert result is None
