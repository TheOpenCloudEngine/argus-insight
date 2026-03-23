"""Tests for SQL parser."""

from java_source_analyzer.jpa.sql_parser import SqlParser


class TestSqlParser:

    def setup_method(self):
        self.parser = SqlParser()

    def test_simple_select(self):
        refs = self.parser.parse("SELECT * FROM users")
        assert len(refs) == 1
        assert refs[0].table_name == "users"
        assert refs[0].access_type == "R"

    def test_select_with_join(self):
        refs = self.parser.parse(
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        tables = {r.table_name: r.access_type for r in refs}
        assert "users" in tables
        assert "orders" in tables
        assert tables["users"] == "R"
        assert tables["orders"] == "R"

    def test_insert(self):
        refs = self.parser.parse("INSERT INTO audit_log (msg) VALUES ('test')")
        assert len(refs) == 1
        assert refs[0].table_name == "audit_log"
        assert refs[0].access_type == "W"

    def test_update(self):
        refs = self.parser.parse("UPDATE users SET active = false WHERE id = 1")
        assert len(refs) == 1
        assert refs[0].table_name == "users"
        assert refs[0].access_type == "W"

    def test_delete(self):
        refs = self.parser.parse("DELETE FROM users WHERE id = 1")
        assert len(refs) == 1
        assert refs[0].table_name == "users"
        assert refs[0].access_type == "W"

    def test_insert_select(self):
        refs = self.parser.parse(
            "INSERT INTO archive_orders SELECT * FROM orders WHERE status = 'closed'"
        )
        tables = {r.table_name: r.access_type for r in refs}
        assert tables["archive_orders"] == "W"
        assert tables["orders"] == "R"

    def test_empty_string(self):
        assert self.parser.parse("") == []
        assert self.parser.parse("   ") == []

    def test_schema_qualified_table(self):
        refs = self.parser.parse("SELECT * FROM myschema.users")
        assert len(refs) == 1
        assert refs[0].table_name == "myschema.users"

    def test_jpql_select(self):
        refs = self.parser.parse("SELECT o FROM Order o WHERE o.status = :status")
        assert len(refs) >= 1
        table_names = [r.table_name for r in refs]
        assert "Order" in table_names
