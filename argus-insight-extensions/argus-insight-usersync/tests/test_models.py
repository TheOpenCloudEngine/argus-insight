"""Tests for data models."""

from app.core.models import GroupInfo, SyncResult, UserInfo


class TestUserInfo:
    def test_equality_by_name(self):
        u1 = UserInfo(name="jdoe", first_name="John")
        u2 = UserInfo(name="jdoe", first_name="Jane")
        assert u1 == u2

    def test_inequality(self):
        u1 = UserInfo(name="jdoe")
        u2 = UserInfo(name="jsmith")
        assert u1 != u2

    def test_hash(self):
        u1 = UserInfo(name="jdoe")
        u2 = UserInfo(name="jdoe")
        assert hash(u1) == hash(u2)
        assert len({u1, u2}) == 1

    def test_default_fields(self):
        u = UserInfo(name="jdoe")
        assert u.first_name == ""
        assert u.last_name == ""
        assert u.email == ""
        assert u.group_names == []


class TestGroupInfo:
    def test_equality_by_name(self):
        g1 = GroupInfo(name="dev")
        g2 = GroupInfo(name="dev", description="Development")
        assert g1 == g2

    def test_default_members(self):
        g = GroupInfo(name="dev")
        assert g.member_names == []


class TestSyncResult:
    def test_success_when_no_errors(self):
        r = SyncResult(users_total=5, users_created=3)
        assert r.success is True

    def test_failure_when_errors_exist(self):
        r = SyncResult(errors=["something failed"])
        assert r.success is False
