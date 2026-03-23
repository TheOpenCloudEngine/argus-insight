"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_entity_source():
    return (FIXTURES_DIR / "sample_entity.java").read_text()


@pytest.fixture
def sample_entity_no_table_source():
    return (FIXTURES_DIR / "sample_entity_no_table.java").read_text()


@pytest.fixture
def sample_named_query_source():
    return (FIXTURES_DIR / "sample_named_query.java").read_text()


@pytest.fixture
def sample_repository_source():
    return (FIXTURES_DIR / "sample_repository.java").read_text()


@pytest.fixture
def sample_inheritance_source():
    return (FIXTURES_DIR / "sample_inheritance.java").read_text()


@pytest.fixture
def sample_jakarta_source():
    return (FIXTURES_DIR / "sample_jakarta.java").read_text()
