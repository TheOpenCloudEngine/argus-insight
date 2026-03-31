"""Impala runtime profile fetcher.

Retrieves the full text-based runtime profile for a given Impala query from
two possible sources:

1. **Impala daemon HTTP API** (preferred for in-flight / recent queries)
   ``GET http://<coordinator>:25000/query_profile?query_id=<qid>``

2. **Cloudera Manager REST API** (fallback for historical queries)
   ``GET /api/v{ver}/clusters/{c}/services/{s}/impalaQueries/{qid}``
   with ``?format=text`` to get the text profile.

The fetcher tries the daemon first (using the coordinator host stored in
ImpalaQueryHistory) and falls back to Cloudera Manager.
"""

from __future__ import annotations

import logging

import requests
import urllib3

logger = logging.getLogger(__name__)


class ImpalaProfileFetcher:
    """Fetches Impala runtime profiles from daemon or Cloudera Manager."""

    def __init__(
        self,
        cm_host: str = "localhost",
        cm_port: int = 7180,
        cm_username: str = "admin",
        cm_password: str = "admin",
        cluster_name: str = "cluster",
        service_name: str = "impala",
        api_version: int = 19,
        tls_enabled: bool = False,
        tls_verify: bool = True,
        daemon_http_port: int = 25000,
        daemon_tls_enabled: bool = False,
        fetch_timeout: int = 30,
    ) -> None:
        # Cloudera Manager settings
        scheme = "https" if tls_enabled else "http"
        self.cm_base_url = f"{scheme}://{cm_host}:{cm_port}/api/v{api_version}"
        self.cluster_name = cluster_name
        self.service_name = service_name
        self.cm_auth = (cm_username, cm_password)
        self.cm_verify = tls_verify if tls_enabled else True

        # Impala daemon settings
        self.daemon_http_port = daemon_http_port
        self.daemon_scheme = "https" if daemon_tls_enabled else "http"

        self.timeout = fetch_timeout

        if tls_enabled and not tls_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def fetch_profile(
        self,
        query_id: str,
        coordinator_host: str | None = None,
    ) -> str | None:
        """Fetch the runtime profile text for a query.

        Tries the Impala daemon HTTP API first (if coordinator_host is known),
        then falls back to the Cloudera Manager API.

        Returns the profile text or None if unavailable from both sources.
        """
        # Try daemon API first
        if coordinator_host:
            profile = self._fetch_from_daemon(coordinator_host, query_id)
            if profile:
                return profile
            logger.debug(
                "Daemon fetch failed for %s on %s, trying CM API",
                query_id, coordinator_host,
            )

        # Fallback to CM API
        return self._fetch_from_cm(query_id)

    def _fetch_from_daemon(self, host: str, query_id: str) -> str | None:
        """Fetch profile from Impala daemon's web UI endpoint."""
        url = (
            f"{self.daemon_scheme}://{host}:{self.daemon_http_port}"
            f"/query_profile"
        )
        try:
            resp = requests.get(
                url,
                params={"query_id": query_id, "format": "text"},
                timeout=self.timeout,
                verify=False if self.daemon_scheme == "https" else True,
            )
            if resp.status_code == 200:
                text = resp.text.strip()
                if text and "not found" not in text.lower():
                    return text
            return None
        except requests.RequestException as e:
            logger.debug("Failed to fetch profile from daemon %s: %s", host, e)
            return None

    def _fetch_from_cm(self, query_id: str) -> str | None:
        """Fetch profile from Cloudera Manager REST API."""
        url = (
            f"{self.cm_base_url}/clusters/{self.cluster_name}"
            f"/services/{self.service_name}/impalaQueries/{query_id}"
        )
        try:
            resp = requests.get(
                url,
                params={"format": "text"},
                auth=self.cm_auth,
                verify=self.cm_verify,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
                if data:
                    # CM returns JSON with a "profile" field containing the text
                    return data.get("profile") or data.get("runtimeProfile")
                # If response is plain text
                text = resp.text.strip()
                if text:
                    return text
            return None
        except requests.RequestException as e:
            logger.debug("Failed to fetch profile from CM for %s: %s", query_id, e)
            return None
