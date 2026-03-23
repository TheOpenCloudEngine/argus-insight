"""Tests for SQLAlchemy analyzers."""

from tests.conftest import load_fixture
from python_source_analyzer.sqlalchemy_analyzer.ast_analyzer import SqlAlchemyAstAnalyzer
from python_source_analyzer.sqlalchemy_analyzer.regex_analyzer import SqlAlchemyRegexAnalyzer


class TestSqlAlchemyAstORM:

    def setup_method(self):
        self.analyzer = SqlAlchemyAstAnalyzer()
        self.source = load_fixture("sample_sqlalchemy_orm.py")

    def test_tablename_extraction(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names
        assert "roles" in table_names
        assert "orders" in table_names

    def test_core_table(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "user_roles" in table_names

    def test_access_type(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        for m in result.mappings:
            assert m.access_type == "RW"

    def test_framework(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        assert all(m.framework == "SQLAlchemy" for m in result.mappings)


class TestSqlAlchemyAstCore:

    def setup_method(self):
        self.analyzer = SqlAlchemyAstAnalyzer()
        self.source = load_fixture("sample_sqlalchemy_core.py")

    def test_core_tables(self):
        result = self.analyzer.analyze(self.source, "core.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "products" in table_names
        assert "categories" in table_names

    def test_text_sql(self):
        result = self.analyzer.analyze(self.source, "core.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        # text("SELECT ... FROM products p JOIN categories c ...")
        assert "products" in table_names
        assert "categories" in table_names

    def test_dml_functions(self):
        result = self.analyzer.analyze(self.source, "core.py")
        assert result is not None
        # select(products) -> R, insert(products) -> W, etc.
        product_mappings = [m for m in result.mappings if m.table_name == "products"]
        access_types = {m.access_type for m in product_mappings}
        assert "RW" in access_types or ("R" in access_types and "W" in access_types)


class TestSqlAlchemyRegex:

    def setup_method(self):
        self.regex = SqlAlchemyRegexAnalyzer()

    def test_orm_tablename(self):
        source = load_fixture("sample_sqlalchemy_orm.py")
        result = self.regex.analyze(source, "models.py")
        table_names = {m.table_name for m in result.mappings}
        assert "users" in table_names
        assert "roles" in table_names

    def test_core_table(self):
        source = load_fixture("sample_sqlalchemy_core.py")
        result = self.regex.analyze(source, "core.py")
        table_names = {m.table_name for m in result.mappings}
        assert "products" in table_names

    def test_non_sa_file(self):
        source = "def hello(): print('hello')"
        result = self.regex.analyze(source, "hello.py")
        assert len(result.mappings) == 0
