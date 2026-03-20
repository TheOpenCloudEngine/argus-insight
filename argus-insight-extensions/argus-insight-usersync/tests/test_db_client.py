"""Tests for database client."""

from unittest.mock import MagicMock, patch

from app.db.client import DatabaseClient


class TestDatabaseClient:
    @patch("app.db.client.settings")
    @patch("app.db.client.create_engine")
    def test_check_connection_success(self, mock_create_engine, mock_settings):
        mock_settings.db_type = "postgresql"
        mock_settings.db_host = "localhost"
        mock_settings.db_port = 5432
        mock_settings.db_name = "argus"
        mock_settings.db_username = "argus"
        mock_settings.db_password = "argus"

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_create_engine.return_value = mock_engine

        client = DatabaseClient()
        assert client.check_connection() is True
        client.close()

    @patch("app.db.client.settings")
    @patch("app.db.client.create_engine")
    def test_check_connection_failure(self, mock_create_engine, mock_settings):
        mock_settings.db_type = "postgresql"
        mock_settings.db_host = "localhost"
        mock_settings.db_port = 5432
        mock_settings.db_name = "argus"
        mock_settings.db_username = "argus"
        mock_settings.db_password = "argus"

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection refused")
        mock_create_engine.return_value = mock_engine

        client = DatabaseClient()
        assert client.check_connection() is False
        client.close()

    @patch("app.db.client.settings")
    @patch("app.db.client.create_engine")
    def test_load_existing_users(self, mock_create_engine, mock_settings):
        mock_settings.db_type = "postgresql"
        mock_settings.db_host = "localhost"
        mock_settings.db_port = 5432
        mock_settings.db_name = "argus"
        mock_settings.db_username = "argus"
        mock_settings.db_password = "argus"

        mock_row1 = MagicMock()
        mock_row1.id = 1
        mock_row1.username = "jdoe"
        mock_row1.email = "jdoe@example.com"
        mock_row1.first_name = "John"
        mock_row1.last_name = "Doe"
        mock_row1.status = "active"

        mock_row2 = MagicMock()
        mock_row2.id = 2
        mock_row2.username = "jsmith"
        mock_row2.email = "jsmith@example.com"
        mock_row2.first_name = "Jane"
        mock_row2.last_name = "Smith"
        mock_row2.status = "active"

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [mock_row1, mock_row2]
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_create_engine.return_value = mock_engine

        client = DatabaseClient()
        result = client.load_existing_users()

        assert "jdoe" in result
        assert result["jdoe"]["email"] == "jdoe@example.com"
        assert "jsmith" in result
        assert len(result) == 2
        client.close()

    def test_deactivate_removed_users_no_removals(self):
        client = DatabaseClient()
        existing = {
            "jdoe": {"id": 1, "status": "active"},
            "jsmith": {"id": 2, "status": "active"},
        }
        source_usernames = {"jdoe", "jsmith"}
        count = client.deactivate_removed_users(source_usernames, existing)
        assert count == 0
