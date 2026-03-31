"""Kubernetes API client using kubernetes_asyncio."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from kubernetes_asyncio import client as k8s_client
from kubernetes_asyncio import config as k8s_config
from kubernetes_asyncio import watch as k8s_watch
from kubernetes_asyncio.client import ApiException

logger = logging.getLogger(__name__)

# Mapping from resource type to (API class factory, namespaced, list method, group/version)
_RESOURCE_MAP: dict[str, tuple[str, bool, str, str]] = {
    # Core v1
    "pods": ("CoreV1Api", True, "list_namespaced_pod", "v1"),
    "services": ("CoreV1Api", True, "list_namespaced_service", "v1"),
    "configmaps": ("CoreV1Api", True, "list_namespaced_config_map", "v1"),
    "secrets": ("CoreV1Api", True, "list_namespaced_secret", "v1"),
    "persistentvolumeclaims": ("CoreV1Api", True, "list_namespaced_persistent_volume_claim", "v1"),
    "events": ("CoreV1Api", True, "list_namespaced_event", "v1"),
    "endpoints": ("CoreV1Api", True, "list_namespaced_endpoints", "v1"),
    "serviceaccounts": ("CoreV1Api", True, "list_namespaced_service_account", "v1"),
    "replicationcontrollers": (
        "CoreV1Api", True, "list_namespaced_replication_controller", "v1",
    ),
    # Cluster-scoped core
    "namespaces": ("CoreV1Api", False, "list_namespace", "v1"),
    "nodes": ("CoreV1Api", False, "list_node", "v1"),
    "persistentvolumes": ("CoreV1Api", False, "list_persistent_volume", "v1"),
    # Apps v1
    "deployments": ("AppsV1Api", True, "list_namespaced_deployment", "apps/v1"),
    "statefulsets": ("AppsV1Api", True, "list_namespaced_stateful_set", "apps/v1"),
    "daemonsets": ("AppsV1Api", True, "list_namespaced_daemon_set", "apps/v1"),
    "replicasets": ("AppsV1Api", True, "list_namespaced_replica_set", "apps/v1"),
    # Batch v1
    "jobs": ("BatchV1Api", True, "list_namespaced_job", "batch/v1"),
    "cronjobs": ("BatchV1Api", True, "list_namespaced_cron_job", "batch/v1"),
    # Networking v1
    "ingresses": ("NetworkingV1Api", True, "list_namespaced_ingress", "networking.k8s.io/v1"),
    "networkpolicies": (
        "NetworkingV1Api", True, "list_namespaced_network_policy", "networking.k8s.io/v1",
    ),
    "ingressclasses": (
        "NetworkingV1Api", False, "list_ingress_class", "networking.k8s.io/v1",
    ),
    # Storage v1
    "storageclasses": ("StorageV1Api", False, "list_storage_class", "storage.k8s.io/v1"),
    # RBAC v1
    "clusterroles": (
        "RbacAuthorizationV1Api", False, "list_cluster_role", "rbac.authorization.k8s.io/v1",
    ),
    "clusterrolebindings": (
        "RbacAuthorizationV1Api", False, "list_cluster_role_binding",
        "rbac.authorization.k8s.io/v1",
    ),
    "roles": (
        "RbacAuthorizationV1Api", True, "list_namespaced_role", "rbac.authorization.k8s.io/v1",
    ),
    "rolebindings": (
        "RbacAuthorizationV1Api", True, "list_namespaced_role_binding",
        "rbac.authorization.k8s.io/v1",
    ),
}

# Read/Get methods mapping
_READ_MAP: dict[str, tuple[str, str]] = {
    "pods": ("CoreV1Api", "read_namespaced_pod"),
    "services": ("CoreV1Api", "read_namespaced_service"),
    "configmaps": ("CoreV1Api", "read_namespaced_config_map"),
    "secrets": ("CoreV1Api", "read_namespaced_secret"),
    "persistentvolumeclaims": ("CoreV1Api", "read_namespaced_persistent_volume_claim"),
    "events": ("CoreV1Api", "read_namespaced_event"),
    "endpoints": ("CoreV1Api", "read_namespaced_endpoints"),
    "serviceaccounts": ("CoreV1Api", "read_namespaced_service_account"),
    "namespaces": ("CoreV1Api", "read_namespace"),
    "nodes": ("CoreV1Api", "read_node"),
    "persistentvolumes": ("CoreV1Api", "read_persistent_volume"),
    "deployments": ("AppsV1Api", "read_namespaced_deployment"),
    "statefulsets": ("AppsV1Api", "read_namespaced_stateful_set"),
    "daemonsets": ("AppsV1Api", "read_namespaced_daemon_set"),
    "replicasets": ("AppsV1Api", "read_namespaced_replica_set"),
    "jobs": ("BatchV1Api", "read_namespaced_job"),
    "cronjobs": ("BatchV1Api", "read_namespaced_cron_job"),
    "ingresses": ("NetworkingV1Api", "read_namespaced_ingress"),
    "networkpolicies": ("NetworkingV1Api", "read_namespaced_network_policy"),
    "storageclasses": ("StorageV1Api", "read_storage_class"),
    "clusterroles": ("RbacAuthorizationV1Api", "read_cluster_role"),
    "clusterrolebindings": ("RbacAuthorizationV1Api", "read_cluster_role_binding"),
    "roles": ("RbacAuthorizationV1Api", "read_namespaced_role"),
    "rolebindings": ("RbacAuthorizationV1Api", "read_namespaced_role_binding"),
}

# Create methods mapping
_CREATE_MAP: dict[str, tuple[str, str]] = {
    "pods": ("CoreV1Api", "create_namespaced_pod"),
    "services": ("CoreV1Api", "create_namespaced_service"),
    "configmaps": ("CoreV1Api", "create_namespaced_config_map"),
    "secrets": ("CoreV1Api", "create_namespaced_secret"),
    "persistentvolumeclaims": ("CoreV1Api", "create_namespaced_persistent_volume_claim"),
    "serviceaccounts": ("CoreV1Api", "create_namespaced_service_account"),
    "namespaces": ("CoreV1Api", "create_namespace"),
    "deployments": ("AppsV1Api", "create_namespaced_deployment"),
    "statefulsets": ("AppsV1Api", "create_namespaced_stateful_set"),
    "daemonsets": ("AppsV1Api", "create_namespaced_daemon_set"),
    "jobs": ("BatchV1Api", "create_namespaced_job"),
    "cronjobs": ("BatchV1Api", "create_namespaced_cron_job"),
    "ingresses": ("NetworkingV1Api", "create_namespaced_ingress"),
    "roles": ("RbacAuthorizationV1Api", "create_namespaced_role"),
    "rolebindings": ("RbacAuthorizationV1Api", "create_namespaced_role_binding"),
}

# Delete methods mapping
_DELETE_MAP: dict[str, tuple[str, str]] = {
    "pods": ("CoreV1Api", "delete_namespaced_pod"),
    "services": ("CoreV1Api", "delete_namespaced_service"),
    "configmaps": ("CoreV1Api", "delete_namespaced_config_map"),
    "secrets": ("CoreV1Api", "delete_namespaced_secret"),
    "persistentvolumeclaims": ("CoreV1Api", "delete_namespaced_persistent_volume_claim"),
    "serviceaccounts": ("CoreV1Api", "delete_namespaced_service_account"),
    "namespaces": ("CoreV1Api", "delete_namespace"),
    "nodes": ("CoreV1Api", "delete_node"),
    "persistentvolumes": ("CoreV1Api", "delete_persistent_volume"),
    "deployments": ("AppsV1Api", "delete_namespaced_deployment"),
    "statefulsets": ("AppsV1Api", "delete_namespaced_stateful_set"),
    "daemonsets": ("AppsV1Api", "delete_namespaced_daemon_set"),
    "replicasets": ("AppsV1Api", "delete_namespaced_replica_set"),
    "jobs": ("BatchV1Api", "delete_namespaced_job"),
    "cronjobs": ("BatchV1Api", "delete_namespaced_cron_job"),
    "ingresses": ("NetworkingV1Api", "delete_namespaced_ingress"),
    "storageclasses": ("StorageV1Api", "delete_storage_class"),
    "roles": ("RbacAuthorizationV1Api", "delete_namespaced_role"),
    "rolebindings": ("RbacAuthorizationV1Api", "delete_namespaced_role_binding"),
}

# Patch methods mapping
_PATCH_MAP: dict[str, tuple[str, str]] = {
    "pods": ("CoreV1Api", "patch_namespaced_pod"),
    "services": ("CoreV1Api", "patch_namespaced_service"),
    "configmaps": ("CoreV1Api", "patch_namespaced_config_map"),
    "secrets": ("CoreV1Api", "patch_namespaced_secret"),
    "namespaces": ("CoreV1Api", "patch_namespace"),
    "nodes": ("CoreV1Api", "patch_node"),
    "deployments": ("AppsV1Api", "patch_namespaced_deployment"),
    "statefulsets": ("AppsV1Api", "patch_namespaced_stateful_set"),
    "daemonsets": ("AppsV1Api", "patch_namespaced_daemon_set"),
    "jobs": ("BatchV1Api", "patch_namespaced_job"),
    "cronjobs": ("BatchV1Api", "patch_namespaced_cron_job"),
    "ingresses": ("NetworkingV1Api", "patch_namespaced_ingress"),
}


def _is_namespaced(resource: str) -> bool:
    """Return True if the resource type is namespace-scoped."""
    info = _RESOURCE_MAP.get(resource)
    if info is None:
        raise ValueError(f"Unknown resource type: {resource}")
    return info[1]


def _get_api_version(resource: str) -> str:
    """Return the API version string for the resource type."""
    info = _RESOURCE_MAP.get(resource)
    if info is None:
        raise ValueError(f"Unknown resource type: {resource}")
    return info[3]


class K8sClient:
    """Async Kubernetes API client that loads config from a kubeconfig file."""

    def __init__(self, kubeconfig_path: str, context: str = ""):
        self._kubeconfig_path = kubeconfig_path
        self._context = context or None
        self._api_client: k8s_client.ApiClient | None = None

    async def _ensure_client(self) -> k8s_client.ApiClient:
        if self._api_client is None:
            await k8s_config.load_kube_config(
                config_file=self._kubeconfig_path,
                context=self._context,
            )
            self._api_client = k8s_client.ApiClient()
        return self._api_client

    async def close(self) -> None:
        if self._api_client:
            await self._api_client.close()
            self._api_client = None

    def _get_api(self, api_class_name: str) -> object:
        """Get an API instance by class name."""
        cls = getattr(k8s_client, api_class_name)
        return cls(self._api_client)

    # ── Cluster Info ──────────────────────────────────────────────

    async def get_cluster_info(self) -> dict:
        """Get cluster version and platform info."""
        await self._ensure_client()
        api = k8s_client.VersionApi(self._api_client)
        info = await api.get_code()
        return {
            "version": f"{info.major}.{info.minor}",
            "platform": info.platform,
            "git_version": info.git_version,
        }

    # ── Node Metrics ─────────────────────────────────────────────

    async def get_node_metrics(self) -> list[dict]:
        """Fetch node metrics from metrics.k8s.io API. Returns [] if unavailable."""
        await self._ensure_client()
        try:
            api = k8s_client.CustomObjectsApi(self._api_client)
            result = await api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
            )
            items = result.get("items", [])
            metrics = []
            for item in items:
                metadata = item.get("metadata", {})
                usage = item.get("usage", {})
                metrics.append({
                    "name": metadata.get("name", ""),
                    "cpu_usage": usage.get("cpu", "0"),
                    "memory_usage": usage.get("memory", "0"),
                })
            return metrics
        except Exception as e:
            logger.debug("Node metrics unavailable: %s", e)
            return []

    async def get_pod_metrics(self) -> list[dict]:
        """Fetch pod metrics from metrics.k8s.io API. Returns [] if unavailable."""
        await self._ensure_client()
        try:
            api = k8s_client.CustomObjectsApi(self._api_client)
            result = await api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods",
            )
            return result.get("items", [])
        except Exception as e:
            logger.debug("Pod metrics unavailable: %s", e)
            return []

    # ── List Resources ────────────────────────────────────────────

    async def list_resources(
        self,
        resource: str,
        namespace: str | None = None,
        label_selector: str = "",
        field_selector: str = "",
        limit: int | None = None,
        continue_token: str = "",
    ) -> dict:
        """List Kubernetes resources. Returns the raw API response as dict."""
        await self._ensure_client()
        info = _RESOURCE_MAP.get(resource)
        if info is None:
            raise ValueError(f"Unknown resource type: {resource}")

        api_class_name, namespaced, list_method, api_version = info
        api = self._get_api(api_class_name)
        method = getattr(api, list_method)

        kwargs: dict = {}
        if label_selector:
            kwargs["label_selector"] = label_selector
        if field_selector:
            kwargs["field_selector"] = field_selector
        if limit:
            kwargs["limit"] = limit
        if continue_token:
            kwargs["_continue"] = continue_token

        if namespaced and namespace:
            result = await method(namespace, **kwargs)
        elif namespaced and not namespace:
            # List across all namespaces
            all_ns_method_name = list_method.replace("_namespaced_", "_")
            if list_method.startswith("list_namespaced_"):
                all_ns_method_name = list_method.replace(
                    "list_namespaced_", "list_"
                ) + "_for_all_namespaces"
            all_ns_method = getattr(api, all_ns_method_name, None)
            if all_ns_method:
                result = await all_ns_method(**kwargs)
            else:
                result = await method("default", **kwargs)
        else:
            result = await method(**kwargs)

        return self._api_client.sanitize_for_serialization(result)

    # ── Get Single Resource ───────────────────────────────────────

    async def get_resource(
        self, resource: str, name: str, namespace: str | None = None,
    ) -> dict:
        """Get a single Kubernetes resource by name."""
        await self._ensure_client()
        info = _READ_MAP.get(resource)
        if info is None:
            raise ValueError(f"Cannot read resource type: {resource}")

        api_class_name, read_method = info
        api = self._get_api(api_class_name)
        method = getattr(api, read_method)

        namespaced = _is_namespaced(resource)
        if namespaced and namespace:
            result = await method(name, namespace)
        elif namespaced:
            result = await method(name, "default")
        else:
            result = await method(name)

        return self._api_client.sanitize_for_serialization(result)

    # ── Create Resource ───────────────────────────────────────────

    async def create_resource(
        self, resource: str, body: dict, namespace: str | None = None,
    ) -> dict:
        """Create a Kubernetes resource."""
        await self._ensure_client()
        info = _CREATE_MAP.get(resource)
        if info is None:
            raise ValueError(f"Cannot create resource type: {resource}")

        api_class_name, create_method = info
        api = self._get_api(api_class_name)
        method = getattr(api, create_method)

        namespaced = _is_namespaced(resource)
        if namespaced and namespace:
            result = await method(namespace, body)
        elif namespaced:
            ns = body.get("metadata", {}).get("namespace", "default")
            result = await method(ns, body)
        else:
            result = await method(body)

        return self._api_client.sanitize_for_serialization(result)

    # ── Delete Resource ───────────────────────────────────────────

    async def delete_resource(
        self, resource: str, name: str, namespace: str | None = None,
    ) -> dict:
        """Delete a Kubernetes resource."""
        await self._ensure_client()
        info = _DELETE_MAP.get(resource)
        if info is None:
            raise ValueError(f"Cannot delete resource type: {resource}")

        api_class_name, delete_method = info
        api = self._get_api(api_class_name)
        method = getattr(api, delete_method)

        namespaced = _is_namespaced(resource)
        if namespaced and namespace:
            result = await method(name, namespace)
        elif namespaced:
            result = await method(name, "default")
        else:
            result = await method(name)

        return self._api_client.sanitize_for_serialization(result)

    # ── Patch/Update Resource ─────────────────────────────────────

    async def patch_resource(
        self, resource: str, name: str, body: dict, namespace: str | None = None,
    ) -> dict:
        """Patch (update) a Kubernetes resource."""
        await self._ensure_client()
        info = _PATCH_MAP.get(resource)
        if info is None:
            raise ValueError(f"Cannot patch resource type: {resource}")

        api_class_name, patch_method = info
        api = self._get_api(api_class_name)
        method = getattr(api, patch_method)

        namespaced = _is_namespaced(resource)
        if namespaced and namespace:
            result = await method(name, namespace, body)
        elif namespaced:
            result = await method(name, "default", body)
        else:
            result = await method(name, body)

        return self._api_client.sanitize_for_serialization(result)

    # ── Replace Resource (full update) ────────────────────────────

    async def replace_resource(
        self, resource: str, name: str, body: dict, namespace: str | None = None,
    ) -> dict:
        """Replace (full update) a Kubernetes resource via PUT."""
        await self._ensure_client()
        # Replace methods follow the pattern: replace_namespaced_X or replace_X
        info = _READ_MAP.get(resource)
        if info is None:
            raise ValueError(f"Cannot replace resource type: {resource}")

        api_class_name, read_method = info
        replace_method = read_method.replace("read_", "replace_")
        api = self._get_api(api_class_name)
        method = getattr(api, replace_method, None)
        if method is None:
            raise ValueError(f"Replace not supported for: {resource}")

        namespaced = _is_namespaced(resource)
        if namespaced and namespace:
            result = await method(name, namespace, body)
        elif namespaced:
            ns = body.get("metadata", {}).get("namespace", "default")
            result = await method(name, ns, body)
        else:
            result = await method(name, body)

        return self._api_client.sanitize_for_serialization(result)

    # ── Watch Resources (async generator) ─────────────────────────

    async def watch_resources(
        self,
        resource: str,
        namespace: str | None = None,
        resource_version: str = "",
        label_selector: str = "",
        timeout_seconds: int = 0,
    ) -> AsyncIterator[dict]:
        """Watch resource changes. Yields dicts with 'type' and 'object'."""
        await self._ensure_client()
        info = _RESOURCE_MAP.get(resource)
        if info is None:
            raise ValueError(f"Unknown resource type: {resource}")

        api_class_name, namespaced, list_method, api_version = info
        api = self._get_api(api_class_name)

        # For watching all namespaces of a namespaced resource
        if namespaced and not namespace:
            method_name = list_method.replace(
                "list_namespaced_", "list_"
            ) + "_for_all_namespaces"
            method = getattr(api, method_name, None)
            if method is None:
                method = getattr(api, list_method)
                namespace = "default"
        elif namespaced:
            method = getattr(api, list_method)
        else:
            method = getattr(api, list_method)

        w = k8s_watch.Watch()
        kwargs: dict = {}
        if resource_version:
            kwargs["resource_version"] = resource_version
        if label_selector:
            kwargs["label_selector"] = label_selector
        if timeout_seconds:
            kwargs["timeout_seconds"] = timeout_seconds

        if namespaced and namespace:
            stream = w.stream(method, namespace, **kwargs)
        else:
            stream = w.stream(method, **kwargs)

        try:
            async for event in stream:
                obj = event.get("object")
                if obj and hasattr(obj, "to_dict"):
                    obj = self._api_client.sanitize_for_serialization(obj)
                yield {
                    "type": event.get("type", "UNKNOWN"),
                    "object": obj,
                }
        finally:
            w.stop()

    # ── Pod Logs ──────────────────────────────────────────────────

    async def get_pod_logs(
        self,
        name: str,
        namespace: str,
        container: str | None = None,
        follow: bool = False,
        tail_lines: int | None = 100,
        since_seconds: int | None = None,
        timestamps: bool = True,
    ) -> AsyncIterator[str]:
        """Stream pod logs as lines."""
        await self._ensure_client()
        api = k8s_client.CoreV1Api(self._api_client)

        kwargs: dict = {"timestamps": timestamps}
        if container:
            kwargs["container"] = container
        if tail_lines is not None:
            kwargs["tail_lines"] = tail_lines
        if since_seconds is not None:
            kwargs["since_seconds"] = since_seconds

        if follow:
            kwargs["follow"] = True
            resp = await api.read_namespaced_pod_log(
                name, namespace, **kwargs, _preload_content=False,
            )
            async for line in resp.content:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                yield line.rstrip("\n")
            resp.close()
        else:
            logs = await api.read_namespaced_pod_log(name, namespace, **kwargs)
            if logs:
                for line in logs.strip().split("\n"):
                    yield line

    # ── Scale Deployment/StatefulSet ──────────────────────────────

    async def scale_resource(
        self, resource: str, name: str, namespace: str, replicas: int,
    ) -> dict:
        """Scale a deployment or statefulset."""
        body = {"spec": {"replicas": replicas}}
        return await self.patch_resource(resource, name, body, namespace)

    # ── Resource metadata helpers ─────────────────────────────────

    @staticmethod
    def is_namespaced(resource: str) -> bool:
        return _is_namespaced(resource)

    @staticmethod
    def get_api_version(resource: str) -> str:
        return _get_api_version(resource)

    @staticmethod
    def supported_resources() -> list[str]:
        return sorted(_RESOURCE_MAP.keys())
