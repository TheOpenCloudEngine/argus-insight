"""Tests for sync engine."""

from unittest.mock import MagicMock, patch

from app.core.models import GroupInfo, UserInfo
from app.sync.engine import SyncEngine


class TestSyncEngine:
    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.RangerClient")
    def test_sync_creates_new_users(self, mock_ranger_cls, mock_create_source, mock_settings):
        mock_settings.ranger_url = "http://localhost:6080"
        mock_settings.sync_source = "file"

        # Setup source mock
        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_source.get_users.return_value = [
            UserInfo(name="jdoe", first_name="John", group_names=["dev"]),
        ]
        mock_source.get_groups.return_value = [
            GroupInfo(name="dev", member_names=["jdoe"]),
        ]
        mock_create_source.return_value = mock_source

        # Setup Ranger client mock
        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = True
        mock_ranger.list_users.return_value = []
        mock_ranger.list_groups.return_value = []
        mock_ranger.get_user_by_name.return_value = None
        mock_ranger.get_group_by_name.return_value = None
        mock_ranger.create_user.return_value = {"id": 1, "name": "jdoe"}
        mock_ranger.create_group.return_value = {"id": 1, "name": "dev"}
        mock_ranger.add_user_to_group.return_value = {"id": 1}
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.users_total == 1
        assert result.users_created == 1
        assert result.groups_total == 1
        assert result.groups_created == 1
        assert result.success is True
        mock_ranger.create_user.assert_called_once()
        mock_ranger.create_group.assert_called_once()

    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.RangerClient")
    def test_sync_skips_unchanged_users(self, mock_ranger_cls, mock_create_source, mock_settings):
        mock_settings.ranger_url = "http://localhost:6080"
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_source.get_users.return_value = [
            UserInfo(name="jdoe", first_name="John"),
        ]
        mock_source.get_groups.return_value = []
        mock_create_source.return_value = mock_source

        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = True
        mock_ranger.list_users.return_value = []
        mock_ranger.list_groups.return_value = []
        mock_ranger.get_user_by_name.return_value = {
            "id": 1,
            "name": "jdoe",
            "firstName": "John",
            "lastName": "",
            "emailAddress": "",
            "description": "",
            "groupNameList": [],
        }
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.users_skipped == 1
        assert result.users_created == 0
        assert result.users_updated == 0

    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.RangerClient")
    def test_sync_fails_on_connection_error(
        self, mock_ranger_cls, mock_create_source, mock_settings
    ):
        mock_settings.ranger_url = "http://localhost:6080"
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_create_source.return_value = mock_source

        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = False
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.success is False
        assert len(result.errors) > 0

    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.RangerClient")
    def test_sync_updates_changed_users(self, mock_ranger_cls, mock_create_source, mock_settings):
        mock_settings.ranger_url = "http://localhost:6080"
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_source.get_users.return_value = [
            UserInfo(
                name="jdoe",
                first_name="John",
                last_name="Doe",
                email="newemail@example.com",
            ),
        ]
        mock_source.get_groups.return_value = []
        mock_create_source.return_value = mock_source

        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = True
        mock_ranger.list_users.return_value = []
        mock_ranger.list_groups.return_value = []
        mock_ranger.get_user_by_name.return_value = {
            "id": 1,
            "name": "jdoe",
            "firstName": "John",
            "lastName": "",
            "emailAddress": "old@example.com",
            "description": "",
            "groupNameList": [],
        }
        mock_ranger.update_user.return_value = {"id": 1, "name": "jdoe"}
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.users_updated == 1
        mock_ranger.update_user.assert_called_once()
