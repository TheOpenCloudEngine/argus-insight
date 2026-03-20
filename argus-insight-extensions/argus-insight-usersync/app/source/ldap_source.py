"""LDAP/Active Directory source - reads users and groups from LDAP directory."""

import logging
import re

from app.core.config import settings
from app.core.models import GroupInfo, UserInfo
from app.source.base import SyncSource

logger = logging.getLogger(__name__)


def _extract_cn(dn: str) -> str:
    """Extract CN value from a distinguished name."""
    match = re.match(r"(?i)cn=([^,]+)", dn)
    return match.group(1) if match else dn


class LdapSource(SyncSource):
    """Sync source that reads from LDAP/Active Directory."""

    def __init__(self) -> None:
        # Import here to allow the module to be loaded even without python-ldap
        try:
            import ldap  # noqa: F401

            self._ldap = ldap
        except ImportError:
            raise ImportError(
                "python-ldap is required for LDAP sync source. "
                "Install with: pip install python-ldap"
            )

    def get_source_type(self) -> str:
        return "ldap"

    def _connect(self):
        """Create and bind an LDAP connection."""
        conn = self._ldap.initialize(settings.ldap_url)
        conn.set_option(self._ldap.OPT_REFERRALS, 0)
        conn.set_option(self._ldap.OPT_PROTOCOL_VERSION, 3)

        if settings.ldap_use_ssl and settings.ldap_tls_ca_cert:
            conn.set_option(self._ldap.OPT_X_TLS_CACERTFILE, settings.ldap_tls_ca_cert)
            conn.set_option(self._ldap.OPT_X_TLS_REQUIRE_CERT, self._ldap.OPT_X_TLS_DEMAND)

        if settings.ldap_referral == "ignore":
            conn.set_option(self._ldap.OPT_REFERRALS, 0)

        if settings.ldap_bind_dn:
            conn.simple_bind_s(settings.ldap_bind_dn, settings.ldap_bind_password)
        else:
            conn.simple_bind_s("", "")

        return conn

    def _paged_search(self, conn, base_dn: str, search_filter: str, attrs: list[str]):
        """Perform a paged LDAP search to handle large directories."""
        page_size = settings.ldap_page_size
        page_control = self._ldap.controls.SimplePagedResultsControl(
            criticality=True, size=page_size, cookie=""
        )

        all_results = []

        while True:
            msgid = conn.search_ext(
                base_dn,
                self._ldap.SCOPE_SUBTREE,
                search_filter,
                attrs,
                serverctrls=[page_control],
            )
            _rtype, rdata, _rmsgid, serverctrls = conn.result3(msgid)
            all_results.extend(rdata)

            # Find the paged results control in response
            pctrls = [
                c
                for c in serverctrls
                if c.controlType == self._ldap.controls.SimplePagedResultsControl.controlType
            ]

            if pctrls:
                cookie = pctrls[0].cookie
                if cookie:
                    page_control.cookie = cookie
                else:
                    break
            else:
                break

        return all_results

    def get_users(self) -> list[UserInfo]:
        """Fetch users from LDAP directory."""
        users: list[UserInfo] = []
        user_filter = set(settings.sync_user_filter)
        name_attr = settings.ldap_user_name_attr
        group_attr = settings.ldap_user_group_name_attr

        attrs = [name_attr, "givenName", "sn", "mail", "description", group_attr]

        try:
            conn = self._connect()
            results = self._paged_search(
                conn,
                settings.ldap_user_search_base,
                settings.ldap_user_search_filter,
                attrs,
            )

            for dn, entry in results:
                if dn is None:
                    continue

                username = self._get_attr(entry, name_attr)
                if not username:
                    continue
                if user_filter and username not in user_filter:
                    continue

                # Get group memberships from memberOf attribute
                group_dns = entry.get(group_attr, [])
                group_names = []
                for g in group_dns:
                    if isinstance(g, bytes):
                        g = g.decode("utf-8", errors="replace")
                    group_names.append(_extract_cn(g))

                users.append(
                    UserInfo(
                        name=username,
                        first_name=self._get_attr(entry, "givenName"),
                        last_name=self._get_attr(entry, "sn"),
                        email=self._get_attr(entry, "mail"),
                        description=self._get_attr(entry, "description"),
                        group_names=group_names,
                    )
                )

            conn.unbind_s()
        except Exception:
            logger.exception("Failed to fetch users from LDAP")
            raise

        logger.info("LDAP source: found %d users", len(users))
        return users

    def get_groups(self) -> list[GroupInfo]:
        """Fetch groups from LDAP directory."""
        groups: list[GroupInfo] = []
        group_filter = set(settings.sync_group_filter)
        name_attr = settings.ldap_group_name_attr
        member_attr = settings.ldap_group_member_attr

        attrs = [name_attr, "description", member_attr]

        try:
            conn = self._connect()
            results = self._paged_search(
                conn,
                settings.ldap_group_search_base,
                settings.ldap_group_search_filter,
                attrs,
            )

            for dn, entry in results:
                if dn is None:
                    continue

                group_name = self._get_attr(entry, name_attr)
                if not group_name:
                    continue
                if group_filter and group_name not in group_filter:
                    continue

                # Parse member DNs to extract usernames
                member_dns = entry.get(member_attr, [])
                member_names = []
                for m in member_dns:
                    if isinstance(m, bytes):
                        m = m.decode("utf-8", errors="replace")
                    member_names.append(_extract_cn(m))

                groups.append(
                    GroupInfo(
                        name=group_name,
                        description=self._get_attr(entry, "description"),
                        member_names=member_names,
                    )
                )

            conn.unbind_s()
        except Exception:
            logger.exception("Failed to fetch groups from LDAP")
            raise

        logger.info("LDAP source: found %d groups", len(groups))
        return groups

    @staticmethod
    def _get_attr(entry: dict, attr_name: str) -> str:
        """Get a single string value from an LDAP entry."""
        values = entry.get(attr_name, [])
        if not values:
            return ""
        val = values[0]
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return str(val)
