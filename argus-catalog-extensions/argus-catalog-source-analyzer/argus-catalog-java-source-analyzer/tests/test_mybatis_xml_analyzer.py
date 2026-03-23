"""Tests for MyBatis XML analyzer."""

from pathlib import Path

from java_source_analyzer.mybatis.xml_analyzer import MyBatisXmlAnalyzer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestMyBatisXmlAnalyzer:

    def setup_method(self):
        self.analyzer = MyBatisXmlAnalyzer()

    def test_basic_mapper(self):
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        assert result.package_name == "com.example.mapper"
        assert len(result.mappings) > 0

        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names

        # Check all frameworks are MyBatis
        assert all(m.framework == "MyBatis" for m in result.mappings)

    def test_select_tables(self):
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        # findById: SELECT FROM users -> R
        find_by_id = [m for m in result.mappings if "findById" in m.class_or_method]
        assert any(m.table_name == "users" and m.access_type == "R" for m in find_by_id)

    def test_insert(self):
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        insert_mappings = [m for m in result.mappings if "insert" in m.class_or_method]
        assert any(m.table_name == "users" and m.access_type == "W" for m in insert_mappings)

    def test_update(self):
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        update_mappings = [m for m in result.mappings if "updateEmail" in m.class_or_method]
        assert any(m.table_name == "users" and m.access_type == "W" for m in update_mappings)

    def test_delete(self):
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        delete_mappings = [m for m in result.mappings if "deleteById" in m.class_or_method]
        assert any(m.table_name == "users" and m.access_type == "W" for m in delete_mappings)

    def test_join_tables(self):
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        table_names = {m.table_name for m in result.mappings}
        # findWithOrders joins users and orders
        assert "orders" in table_names
        # findUserRoles joins users, user_roles, roles
        assert "roles" in table_names
        assert "user_roles" in table_names

    def test_dynamic_sql(self):
        xml = (FIXTURES_DIR / "sample_mybatis_dynamic.xml").read_text()
        result = self.analyzer.analyze(xml, "ProductMapper.xml")

        table_names = {m.table_name for m in result.mappings}
        assert "products" in table_names

    def test_dynamic_sql_insert(self):
        xml = (FIXTURES_DIR / "sample_mybatis_dynamic.xml").read_text()
        result = self.analyzer.analyze(xml, "ProductMapper.xml")

        insert_mappings = [m for m in result.mappings if "batchInsert" in m.class_or_method]
        assert any(m.table_name == "products" and m.access_type == "W" for m in insert_mappings)

    def test_method_context(self):
        """Each mapping should include the statement id as method context."""
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        methods = {m.class_or_method for m in result.mappings}
        assert any("findById" in m for m in methods)
        assert any("insert" in m for m in methods)

    def test_annotation_field(self):
        """Annotation field should indicate the XML tag."""
        xml = (FIXTURES_DIR / "sample_mybatis_mapper.xml").read_text()
        result = self.analyzer.analyze(xml, "UserMapper.xml")

        annotations = {m.annotation for m in result.mappings}
        assert "<select>" in annotations
        assert "<insert>" in annotations
