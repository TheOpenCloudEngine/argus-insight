"""Tests for Django ORM analyzers."""

from tests.conftest import load_fixture
from python_source_analyzer.django_analyzer.ast_analyzer import DjangoAstAnalyzer
from python_source_analyzer.django_analyzer.regex_analyzer import DjangoRegexAnalyzer


class TestDjangoAstModels:

    def setup_method(self):
        self.analyzer = DjangoAstAnalyzer()
        self.source = load_fixture("sample_django_models.py")

    def test_explicit_db_table(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "authors" in table_names
        assert "books" in table_names

    def test_auto_table_name(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        # Review has no db_table -> auto-named "review"
        assert "review" in table_names

    def test_abstract_model_skipped(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "abstractbase" not in table_names

    def test_framework(self):
        result = self.analyzer.analyze(self.source, "models.py")
        assert result is not None
        assert all(m.framework == "Django ORM" for m in result.mappings)


class TestDjangoAstViews:

    def setup_method(self):
        self.analyzer = DjangoAstAnalyzer()
        self.source = load_fixture("sample_django_views.py")

    def test_cursor_execute(self):
        result = self.analyzer.analyze(self.source, "views.py")
        assert result is not None
        table_names = {m.table_name for m in result.mappings}
        assert "authors" in table_names
        assert "books" in table_names

    def test_update_query(self):
        result = self.analyzer.analyze(self.source, "views.py")
        assert result is not None
        write_mappings = [m for m in result.mappings if m.access_type == "W"]
        assert any(m.table_name == "reviews" for m in write_mappings)


class TestDjangoRegex:

    def setup_method(self):
        self.regex = DjangoRegexAnalyzer()

    def test_model_classes(self):
        source = load_fixture("sample_django_models.py")
        result = self.regex.analyze(source, "models.py")
        table_names = {m.table_name for m in result.mappings}
        assert "authors" in table_names
        assert "books" in table_names

    def test_cursor_execute(self):
        source = load_fixture("sample_django_views.py")
        result = self.regex.analyze(source, "views.py")
        table_names = {m.table_name for m in result.mappings}
        assert "authors" in table_names

    def test_non_django_file(self):
        source = "def hello(): print('hello')"
        result = self.regex.analyze(source, "hello.py")
        assert len(result.mappings) == 0
