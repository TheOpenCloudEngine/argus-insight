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
    def test_get_user_by_name_found(self, ranger_client):
        mock_response = httpx.Response(
            200,
            json={"id": 1, "name": "jdoe", "firstName": "John"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            user = ranger_client.get_user_by_name("jdoe")

            assert user is not None
            assert user["name"] == "jdoe"
            mock_client.get.assert_called_once_with("/service/xusers/users/userName/jdoe")

    def test_get_user_by_name_not_found(self, ranger_client):
        mock_response = httpx.Response(
            404,
            json={},
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            user = ranger_client.get_user_by_name("nonexistent")
            assert user is None

    def test_get_user_by_name_uses_cache(self, ranger_client):
        ranger_client._user_cache["cached_user"] = {"id": 99, "name": "cached_user"}

        user = ranger_client.get_user_by_name("cached_user")
        assert user["id"] == 99

    def test_create_user(self, ranger_client):
        mock_response = httpx.Response(
            200,
            json={"id": 10, "name": "newuser"},
            request=httpx.Request("POST", "http://test"),
        )
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            user = ranger_client.create_user(
                name="newuser",
                first_name="New",
                last_name="User",
                email="new@example.com",
                group_names=["dev"],
            )

            assert user["id"] == 10
            assert "newuser" in ranger_client._user_cache

    def test_get_group_by_name_found(self, ranger_client):
        mock_response = httpx.Response(
            200,
            json={"id": 5, "name": "dev"},
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            group = ranger_client.get_group_by_name("dev")

            assert group is not None
            assert group["name"] == "dev"

    def test_create_group(self, ranger_client):
        mock_response = httpx.Response(
            200,
            json={"id": 20, "name": "newgroup"},
            request=httpx.Request("POST", "http://test"),
        )
        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get.return_value = mock_client

            group = ranger_client.create_group(name="newgroup", description="New group")

            assert group["id"] == 20
            assert "newgroup" in ranger_client._group_cache

    def test_list_users_pagination(self, ranger_client):
        page1_response = httpx.Response(
            200,
            json={
                "vXUsers": [{"id": 1, "name": "user1"}, {"id": 2, "name": "user2"}],
                "totalCount": 3,
            },
            request=httpx.Request("GET", "http://test"),
        )
        page2_response = httpx.Response(
            200,
            json={
                "vXUsers": [{"id": 3, "name": "user3"}],
                "totalCount": 3,
            },
            request=httpx.Request("GET", "http://test"),
        )

        with patch.object(ranger_client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.get.side_effect = [page1_response, page2_response]
            mock_get.return_value = mock_client

            users = ranger_client.list_users(page_size=2)

            assert len(users) == 3
            assert users[2]["name"] == "user3"

    def test_check_connection_success(self, ranger_client):
        mock_response = httpx.Response(
            200,
            json=[],
            request=httpx.Request("GET", "http://test"),
        )
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
