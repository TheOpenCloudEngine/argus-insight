"""Tests for Ranger Admin REST client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ranger.client import RangerClient


@pytest.fixture
def ranger_client():
    with patch("app.ranger.client.settings") as mock_settings:
        mock_settings.ranger_url = "http://localhost:6080"
        mock_settings.ranger_username = "admin"
        mock_settings.ranger_password = "admin"
        mock_settings.ranger_timeout = 10
        mock_settings.ranger_ssl_verify = False
        client = RangerClient()
        yield client
        client.close()


class TestRangerClient:
    def test_check_connection_success(self, ranger_client):
        mock_response = httpx.Response(200, json=[], request=httpx.Request("GET", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            assert ranger_client.check_connection() is True

    def test_check_connection_failure(self, ranger_client):
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_get.return_value = mock_client

            assert ranger_client.check_connection() is False

    def test_load_existing_group_users(self, ranger_client):
        mock_response = httpx.Response(
            200,
            json={"dev": ["jdoe", "jsmith"], "admin": ["admin"]},
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            result = ranger_client.load_existing_group_users()

            assert result == {"dev": {"jdoe", "jsmith"}, "admin": {"admin"}}
            mock_client.get.assert_called_once_with("/service/xusers/ugsync/groupusers")

    def test_bulk_sync_users(self, ranger_client):
        mock_response = httpx.Response(200, text="3", request=httpx.Request("POST", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            users = [
                ranger_client.build_vx_user("user1"),
                ranger_client.build_vx_user("user2"),
                ranger_client.build_vx_user("user3"),
            ]
            count = ranger_client.bulk_sync_users(users)

            assert count == 3
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/service/xusers/ugsync/users"
            assert len(call_args[1]["json"]["vXUsers"]) == 3

    def test_bulk_sync_users_empty(self, ranger_client):
        count = ranger_client.bulk_sync_users([])
        assert count == 0

    def test_bulk_sync_groups(self, ranger_client):
        mock_response = httpx.Response(200, text="2", request=httpx.Request("POST", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            groups = [
                ranger_client.build_vx_group("dev"),
                ranger_client.build_vx_group("admin"),
            ]
            count = ranger_client.bulk_sync_groups(groups)

            assert count == 2
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/service/xusers/ugsync/groups"

    def test_bulk_sync_group_users(self, ranger_client):
        mock_response = httpx.Response(200, text="1", request=httpx.Request("POST", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            infos = [{"groupName": "dev", "addUsers": ["newuser"], "delUsers": ["olduser"]}]
            count = ranger_client.bulk_sync_group_users(infos)

            assert count == 1
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/service/xusers/ugsync/groupusers"

    def test_mark_users_invisible(self, ranger_client):
        mock_response = httpx.Response(200, text="ok", request=httpx.Request("POST", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            ranger_client.mark_users_invisible(["deleted_user"])

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/service/xusers/ugsync/users/visibility"
            assert call_args[1]["json"]["deleted_user"] == 0

    def test_mark_groups_invisible(self, ranger_client):
        mock_response = httpx.Response(200, text="ok", request=httpx.Request("POST", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            ranger_client.mark_groups_invisible(["old_group"])

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/service/xusers/ugsync/groups/visibility"

    def test_build_vx_user(self):
        vx = RangerClient.build_vx_user(
            name="jdoe",
            first_name="John",
            last_name="Doe",
            email="jdoe@example.com",
            group_names=["dev"],
            sync_source="LDAP",
        )
        assert vx["name"] == "jdoe"
        assert vx["firstName"] == "John"
        assert vx["userSource"] == 1
        assert vx["status"] == 1
        assert vx["isVisible"] == 1
        assert vx["syncSource"] == "LDAP"
        assert vx["groupNameList"] == ["dev"]
        assert vx["userRoleList"] == ["ROLE_USER"]

    def test_build_vx_group(self):
        vx = RangerClient.build_vx_group(name="dev", description="Development", sync_source="Unix")
        assert vx["name"] == "dev"
        assert vx["groupSource"] == 1
        assert vx["groupType"] == 1
        assert vx["syncSource"] == "Unix"

    def test_build_audit_info(self):
        audit = RangerClient.build_audit_info(
            sync_source="Unix",
            num_new_users=5,
            num_new_groups=2,
        )
        assert audit["syncSource"] == "Unix"
        assert audit["noOfNewUsers"] == 5
        assert audit["noOfNewGroups"] == 2
        assert "eventTime" in audit

    def test_post_audit_info(self, ranger_client):
        mock_response = httpx.Response(200, text="ok", request=httpx.Request("POST", "http://test"))
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            audit = {"syncSource": "Unix", "noOfNewUsers": 1}
            ranger_client.post_audit_info(audit)

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/service/xusers/ugsync/auditinfo"
