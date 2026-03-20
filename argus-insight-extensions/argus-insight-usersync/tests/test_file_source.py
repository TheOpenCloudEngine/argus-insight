"""Tests for file sync source."""

from unittest.mock import patch

from app.source.file_source import FileSource


class TestFileSourceCSV:
    def test_read_users_csv(self, sample_users_csv):
        with patch("app.source.file_source.settings") as mock_settings:
            mock_settings.file_users_path = str(sample_users_csv)
            mock_settings.file_format = "csv"
            mock_settings.sync_user_filter = []

            source = FileSource()
            users = source.get_users()

            assert len(users) == 3
            assert users[0].name == "jdoe"
            assert users[0].first_name == "John"
            assert users[0].email == "jdoe@example.com"
            assert "dev" in users[0].group_names
            assert "admin" in users[0].group_names

    def test_read_groups_csv(self, sample_groups_csv):
        with patch("app.source.file_source.settings") as mock_settings:
            mock_settings.file_groups_path = str(sample_groups_csv)
            mock_settings.file_format = "csv"
            mock_settings.sync_group_filter = []

            source = FileSource()
            groups = source.get_groups()

            assert len(groups) == 3
            assert groups[0].name == "dev"
            assert "jdoe" in groups[0].member_names
            assert "jsmith" in groups[0].member_names

    def test_read_users_with_filter(self, sample_users_csv):
        with patch("app.source.file_source.settings") as mock_settings:
            mock_settings.file_users_path = str(sample_users_csv)
            mock_settings.file_format = "csv"
            mock_settings.sync_user_filter = ["jdoe"]

            source = FileSource()
            users = source.get_users()

            assert len(users) == 1
            assert users[0].name == "jdoe"

    def test_missing_file_returns_empty(self, tmp_path):
        with patch("app.source.file_source.settings") as mock_settings:
            mock_settings.file_users_path = str(tmp_path / "nonexistent.csv")
            mock_settings.file_format = "csv"
            mock_settings.sync_user_filter = []

            source = FileSource()
            users = source.get_users()

            assert users == []


class TestFileSourceJSON:
    def test_read_users_json(self, sample_users_json):
        with patch("app.source.file_source.settings") as mock_settings:
            mock_settings.file_users_path = str(sample_users_json)
            mock_settings.file_format = "json"
            mock_settings.sync_user_filter = []

            source = FileSource()
            users = source.get_users()

            assert len(users) == 2
            assert users[0].name == "jdoe"
            assert users[0].group_names == ["dev", "admin"]

    def test_read_groups_json(self, sample_groups_json):
        with patch("app.source.file_source.settings") as mock_settings:
            mock_settings.file_groups_path = str(sample_groups_json)
            mock_settings.file_format = "json"
            mock_settings.sync_group_filter = []

            source = FileSource()
            groups = source.get_groups()

            assert len(groups) == 2
            assert groups[0].name == "dev"
            assert groups[0].member_names == ["jdoe", "jsmith"]

    def test_source_type(self):
        source = FileSource()
        assert source.get_source_type() == "file"
