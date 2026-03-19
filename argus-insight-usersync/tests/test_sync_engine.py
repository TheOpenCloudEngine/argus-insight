"""Tests for sync engine."""

from unittest.mock import MagicMock, patch

from app.core.models import GroupInfo, UserInfo
from app.sync.engine import SyncEngine


class TestSyncEngine:
    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.DatabaseClient")
    def test_sync_creates_and_updates_users(self, mock_db_cls, mock_create_source, mock_settings):
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_source.get_users.return_value = [
            UserInfo(name="jdoe", first_name="John", group_names=["dev"]),
        ]
        mock_source.get_groups.return_value = [
            GroupInfo(name="dev", member_names=["jdoe"]),
        ]
        mock_create_source.return_value = mock_source

        mock_db = MagicMock()
        mock_db.check_connection.return_value = True
        mock_db.load_existing_users.return_value = {}
        mock_db.sync_users.return_value = (1, 0)
        mock_db.deactivate_removed_users.return_value = 0
        mock_db_cls.return_value = mock_db

        engine = SyncEngine()
        result = engine.run()

        assert result.users_total == 1
        assert result.groups_total == 1
        assert result.success is True
        mock_db.sync_users.assert_called_once()
        mock_db.deactivate_removed_users.assert_called_once()

    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.DatabaseClient")
    def test_sync_fails_on_connection_error(self, mock_db_cls, mock_create_source, mock_settings):
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_create_source.return_value = mock_source

        mock_db = MagicMock()
        mock_db.check_connection.return_value = False
        mock_db_cls.return_value = mock_db

        engine = SyncEngine()
        result = engine.run()

        assert result.success is False
        assert len(result.errors) > 0

    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.DatabaseClient")
    def test_sync_deactivates_removed_users(self, mock_db_cls, mock_create_source, mock_settings):
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_source.get_users.return_value = [
            UserInfo(name="jdoe"),
        ]
        mock_source.get_groups.return_value = [
            GroupInfo(name="dev"),
        ]
        mock_create_source.return_value = mock_source

        mock_db = MagicMock()
        mock_db.check_connection.return_value = True
        mock_db.load_existing_users.return_value = {
            "jdoe": {
                "id": 1,
                "email": "jdoe@ext",
                "first_name": "jdoe",
                "last_name": "",
                "status": "active",
            },
            "removed_user": {
                "id": 2,
                "email": "rm@ext",
                "first_name": "removed_user",
                "last_name": "",
                "status": "active",
            },
        }
        mock_db.sync_users.return_value = (0, 0)
        mock_db.deactivate_removed_users.return_value = 1
        mock_db_cls.return_value = mock_db

        engine = SyncEngine()
        result = engine.run()

        assert result.success is True
        mock_db.deactivate_removed_users.assert_called_once()
        call_args = mock_db.deactivate_removed_users.call_args
        assert "jdoe" in call_args[0][0]
        assert "removed_user" not in call_args[0][0]


class TestBuildUserDicts:
    def test_combines_user_and_group_data(self):
        users = [
            UserInfo(
                name="jdoe",
                first_name="John",
                last_name="Doe",
                email="jdoe@example.com",
                group_names=["dev", "admin"],
            ),
            UserInfo(
                name="jsmith",
                first_name="Jane",
                last_name="Smith",
                email="jsmith@example.com",
                group_names=["dev"],
            ),
        ]
        groups = [
            GroupInfo(name="dev", member_names=["jdoe", "jsmith", "bob"]),
            GroupInfo(name="qa", member_names=["bob"]),
        ]

        result = SyncEngine._build_user_dicts(users, groups)
        usernames = {u["username"] for u in result}

        assert "jdoe" in usernames
        assert "jsmith" in usernames
        assert "bob" in usernames  # from group members
        assert len(result) == 3
