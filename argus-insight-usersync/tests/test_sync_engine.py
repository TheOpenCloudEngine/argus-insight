"""Tests for sync engine."""

from unittest.mock import MagicMock, patch

from app.core.models import GroupInfo, UserInfo
from app.sync.engine import SyncEngine


class TestSyncEngine:
    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.RangerClient")
    def test_sync_pushes_users_and_groups(self, mock_ranger_cls, mock_create_source, mock_settings):
        mock_settings.ranger_url = "http://localhost:6080"
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

        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = True
        mock_ranger.load_existing_group_users.return_value = {}
        mock_ranger.bulk_sync_users.return_value = 1
        mock_ranger.bulk_sync_groups.return_value = 1
        mock_ranger.bulk_sync_group_users.return_value = 1
        mock_ranger.build_vx_user.return_value = {"name": "jdoe"}
        mock_ranger.build_vx_group.return_value = {"name": "dev"}
        mock_ranger.build_audit_info.return_value = {}
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.users_total == 1
        assert result.groups_total == 1
        assert result.success is True
        mock_ranger.bulk_sync_users.assert_called_once()
        mock_ranger.bulk_sync_groups.assert_called_once()
        mock_ranger.bulk_sync_group_users.assert_called_once()
        mock_ranger.post_audit_info.assert_called_once()

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
    def test_sync_computes_membership_deltas(
        self, mock_ranger_cls, mock_create_source, mock_settings
    ):
        mock_settings.ranger_url = "http://localhost:6080"
        mock_settings.sync_source = "file"

        mock_source = MagicMock()
        mock_source.get_source_type.return_value = "file"
        mock_source.get_users.return_value = [
            UserInfo(name="jdoe", group_names=["dev"]),
            UserInfo(name="newuser", group_names=["dev"]),
        ]
        mock_source.get_groups.return_value = [
            GroupInfo(name="dev", member_names=["jdoe", "newuser"]),
        ]
        mock_create_source.return_value = mock_source

        # Existing state: dev group has jdoe and olduser
        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = True
        mock_ranger.load_existing_group_users.return_value = {"dev": {"jdoe", "olduser"}}
        mock_ranger.bulk_sync_users.return_value = 2
        mock_ranger.bulk_sync_groups.return_value = 1
        mock_ranger.bulk_sync_group_users.return_value = 1
        mock_ranger.build_vx_user.side_effect = lambda **kw: {"name": kw["name"]}
        mock_ranger.build_vx_group.side_effect = lambda **kw: {"name": kw["name"]}
        mock_ranger.build_audit_info.return_value = {}
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.success is True

        # Verify group_users call has the delta
        call_args = mock_ranger.bulk_sync_group_users.call_args[0][0]
        dev_delta = [d for d in call_args if d["groupName"] == "dev"]
        assert len(dev_delta) == 1
        assert "newuser" in dev_delta[0]["addUsers"]
        assert "olduser" in dev_delta[0]["delUsers"]

    @patch("app.sync.engine.settings")
    @patch("app.sync.engine._create_source")
    @patch("app.sync.engine.RangerClient")
    def test_sync_marks_deleted_users_invisible(
        self, mock_ranger_cls, mock_create_source, mock_settings
    ):
        mock_settings.ranger_url = "http://localhost:6080"
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

        # Existing: user "removed_user" in group "old_group"
        mock_ranger = MagicMock()
        mock_ranger.check_connection.return_value = True
        mock_ranger.load_existing_group_users.return_value = {
            "dev": {"jdoe", "removed_user"},
            "old_group": {"removed_user"},
        }
        mock_ranger.bulk_sync_users.return_value = 1
        mock_ranger.bulk_sync_groups.return_value = 1
        mock_ranger.bulk_sync_group_users.return_value = 1
        mock_ranger.build_vx_user.side_effect = lambda **kw: {"name": kw["name"]}
        mock_ranger.build_vx_group.side_effect = lambda **kw: {"name": kw["name"]}
        mock_ranger.build_audit_info.return_value = {}
        mock_ranger_cls.return_value = mock_ranger

        engine = SyncEngine()
        result = engine.run()

        assert result.success is True
        # removed_user should be marked invisible
        mock_ranger.mark_users_invisible.assert_called_once()
        invisible_users = mock_ranger.mark_users_invisible.call_args[0][0]
        assert "removed_user" in invisible_users
        # old_group should be marked invisible
        mock_ranger.mark_groups_invisible.assert_called_once()
        invisible_groups = mock_ranger.mark_groups_invisible.call_args[0][0]
        assert "old_group" in invisible_groups


class TestBuildMembershipMap:
    def test_combines_user_and_group_data(self):
        users = [
            UserInfo(name="jdoe", group_names=["dev", "admin"]),
            UserInfo(name="jsmith", group_names=["dev"]),
        ]
        groups = [
            GroupInfo(name="dev", member_names=["jdoe", "jsmith", "bob"]),
            GroupInfo(name="qa", member_names=["bob"]),
        ]

        result = SyncEngine._build_source_membership_map(users, groups)

        assert result["dev"] == {"jdoe", "jsmith", "bob"}
        assert result["admin"] == {"jdoe"}
        assert result["qa"] == {"bob"}
