"""Kubernetes service layer — business logic between router and client."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.k8s.client import K8sClient
from app.k8s.schemas import (
    ClusterInfo,
    ClusterOverview,
    K8sResource,
    K8sResourceList,
    NamespaceOverview,
    ResourceCount,
)
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)


async def _get_k8s_config(session: AsyncSession) -> tuple[str, str]:
    """Read kubeconfig_path and context from the database."""
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "k8s")
    )
    rows = {r.config_key: r.config_value for r in result.scalars().all()}
    kubeconfig = rows.get("k8s_kubeconfig_path", "/etc/rancher/k3s/k3s.yaml")
    context = rows.get("k8s_context", "")
    return kubeconfig, context


async def _make_client(session: AsyncSession) -> K8sClient:
    kubeconfig, context = await _get_k8s_config(session)
    return K8sClient(kubeconfig, context)


# ── Cluster Overview ──────────────────────────────────────────────


def _count_pods(items: list[dict]) -> ResourceCount:
    total = len(items)
    ready = 0
    not_ready = 0
    warning = 0
    for pod in items:
        phase = (pod.get("status") or {}).get("phase", "")
        if phase == "Running" or phase == "Succeeded":
            ready += 1
        elif phase == "Pending":
            warning += 1
        else:
            not_ready += 1
    return ResourceCount(total=total, ready=ready, not_ready=not_ready, warning=warning)


def _count_deployments(items: list[dict]) -> ResourceCount:
    total = len(items)
    ready = 0
    not_ready = 0
    for d in items:
        status = d.get("status") or {}
        desired = (d.get("spec") or {}).get("replicas", 0) or 0
        available = status.get("availableReplicas", 0) or 0
        if available >= desired and desired > 0:
            ready += 1
        else:
            not_ready += 1
    return ResourceCount(total=total, ready=ready, not_ready=not_ready)


def _count_statefulsets(items: list[dict]) -> ResourceCount:
    total = len(items)
    ready = 0
    not_ready = 0
    for s in items:
        status = s.get("status") or {}
        desired = (s.get("spec") or {}).get("replicas", 0) or 0
        ready_replicas = status.get("readyReplicas", 0) or 0
        if ready_replicas >= desired and desired > 0:
            ready += 1
        else:
            not_ready += 1
    return ResourceCount(total=total, ready=ready, not_ready=not_ready)


def _count_daemonsets(items: list[dict]) -> ResourceCount:
    total = len(items)
    ready = 0
    not_ready = 0
    for d in items:
        status = d.get("status") or {}
        desired = status.get("desiredNumberScheduled", 0) or 0
        num_ready = status.get("numberReady", 0) or 0
        if num_ready >= desired and desired > 0:
            ready += 1
        else:
            not_ready += 1
    return ResourceCount(total=total, ready=ready, not_ready=not_ready)


def _count_jobs(items: list[dict]) -> ResourceCount:
    total = len(items)
    ready = 0
    not_ready = 0
    warning = 0
    for j in items:
        status = j.get("status") or {}
        conditions = status.get("conditions") or []
        succeeded = status.get("succeeded", 0) or 0
        failed = status.get("failed", 0) or 0
        complete = any(c.get("type") == "Complete" and c.get("status") == "True"
                       for c in conditions)
        if complete or succeeded > 0:
            ready += 1
        elif failed > 0:
            not_ready += 1
        else:
            warning += 1
    return ResourceCount(total=total, ready=ready, not_ready=not_ready, warning=warning)


def _count_simple(items: list[dict]) -> ResourceCount:
    return ResourceCount(total=len(items), ready=len(items))


def _format_events(items: list[dict], limit: int = 20) -> list[dict]:
    """Format events for frontend display, sorted by lastTimestamp descending."""
    events = []
    for e in items:
        metadata = e.get("metadata") or {}
        involved = e.get("involvedObject") or {}
        events.append({
            "name": metadata.get("name", ""),
            "namespace": metadata.get("namespace", ""),
            "type": e.get("type", "Normal"),
            "reason": e.get("reason", ""),
            "message": e.get("message", ""),
            "source": (e.get("source") or {}).get("component", ""),
            "involved_kind": involved.get("kind", ""),
            "involved_name": involved.get("name", ""),
            "first_timestamp": e.get("firstTimestamp", ""),
            "last_timestamp": e.get("lastTimestamp", ""),
            "count": e.get("count", 1),
        })
    events.sort(key=lambda x: x.get("last_timestamp") or "", reverse=True)
    return events[:limit]


async def get_cluster_overview(session: AsyncSession) -> ClusterOverview:
    """Aggregate cluster-wide overview data."""
    k8s = await _make_client(session)
    try:
        # Get cluster info
        try:
            info = await k8s.get_cluster_info()
            cluster_info = ClusterInfo(
                version=info.get("git_version", ""),
                platform=info.get("platform", ""),
                connected=True,
            )
        except Exception as e:
            logger.warning("Failed to get cluster info: %s", e)
            return ClusterOverview(
                cluster=ClusterInfo(connected=False, error=str(e)),
            )

        # Fetch all resource lists in parallel-ish (sequential for simplicity)
        ns_data = await k8s.list_resources("namespaces")
        ns_items = ns_data.get("items", [])
        namespaces = [
            (n.get("metadata") or {}).get("name", "") for n in ns_items
        ]
        cluster_info.namespace_count = len(namespaces)

        node_data = await k8s.list_resources("nodes")
        node_items = node_data.get("items", [])
        cluster_info.node_count = len(node_items)

        # Count nodes ready/not-ready
        nodes_ready = 0
        nodes_not_ready = 0
        for node in node_items:
            conditions = (node.get("status") or {}).get("conditions") or []
            is_ready = any(
                c.get("type") == "Ready" and c.get("status") == "True"
                for c in conditions
            )
            if is_ready:
                nodes_ready += 1
            else:
                nodes_not_ready += 1

        pod_data = await k8s.list_resources("pods")
        deploy_data = await k8s.list_resources("deployments")
        svc_data = await k8s.list_resources("services")
        sts_data = await k8s.list_resources("statefulsets")
        ds_data = await k8s.list_resources("daemonsets")
        job_data = await k8s.list_resources("jobs")
        cj_data = await k8s.list_resources("cronjobs")
        event_data = await k8s.list_resources("events")

        return ClusterOverview(
            cluster=cluster_info,
            nodes=ResourceCount(
                total=len(node_items), ready=nodes_ready, not_ready=nodes_not_ready,
            ),
            pods=_count_pods(pod_data.get("items", [])),
            deployments=_count_deployments(deploy_data.get("items", [])),
            services=_count_simple(svc_data.get("items", [])),
            statefulsets=_count_statefulsets(sts_data.get("items", [])),
            daemonsets=_count_daemonsets(ds_data.get("items", [])),
            jobs=_count_jobs(job_data.get("items", [])),
            cronjobs=_count_simple(cj_data.get("items", [])),
            namespaces=namespaces,
            recent_events=_format_events(event_data.get("items", [])),
        )
    finally:
        await k8s.close()


async def get_namespace_overview(
    session: AsyncSession, namespace: str,
) -> NamespaceOverview:
    """Aggregate overview data for a single namespace."""
    k8s = await _make_client(session)
    try:
        pod_data = await k8s.list_resources("pods", namespace=namespace)
        deploy_data = await k8s.list_resources("deployments", namespace=namespace)
        svc_data = await k8s.list_resources("services", namespace=namespace)
        sts_data = await k8s.list_resources("statefulsets", namespace=namespace)
        ds_data = await k8s.list_resources("daemonsets", namespace=namespace)
        job_data = await k8s.list_resources("jobs", namespace=namespace)
        event_data = await k8s.list_resources("events", namespace=namespace)

        return NamespaceOverview(
            namespace=namespace,
            pods=_count_pods(pod_data.get("items", [])),
            deployments=_count_deployments(deploy_data.get("items", [])),
            services=_count_simple(svc_data.get("items", [])),
            statefulsets=_count_statefulsets(sts_data.get("items", [])),
            daemonsets=_count_daemonsets(ds_data.get("items", [])),
            jobs=_count_jobs(job_data.get("items", [])),
            recent_events=_format_events(event_data.get("items", [])),
        )
    finally:
        await k8s.close()


# ── Generic CRUD ──────────────────────────────────────────────────


async def list_resources(
    session: AsyncSession,
    resource: str,
    namespace: str | None = None,
    label_selector: str = "",
    field_selector: str = "",
    limit: int | None = None,
    continue_token: str = "",
) -> K8sResourceList:
    """List resources of a given type."""
    k8s = await _make_client(session)
    try:
        data = await k8s.list_resources(
            resource,
            namespace=namespace,
            label_selector=label_selector,
            field_selector=field_selector,
            limit=limit,
            continue_token=continue_token,
        )
        items = data.get("items", [])
        return K8sResourceList(
            kind=data.get("kind", ""),
            api_version=data.get("apiVersion", ""),
            items=items,
            total=len(items),
        )
    finally:
        await k8s.close()


async def get_resource(
    session: AsyncSession, resource: str, name: str, namespace: str | None = None,
) -> K8sResource:
    """Get a single resource."""
    k8s = await _make_client(session)
    try:
        data = await k8s.get_resource(resource, name, namespace)
        return K8sResource(
            kind=data.get("kind", ""),
            api_version=data.get("apiVersion", ""),
            metadata=data.get("metadata", {}),
            spec=data.get("spec"),
            status=data.get("status"),
            data=data.get("data"),
        )
    finally:
        await k8s.close()


async def create_resource(
    session: AsyncSession, resource: str, body: dict, namespace: str | None = None,
) -> dict:
    """Create a resource."""
    k8s = await _make_client(session)
    try:
        return await k8s.create_resource(resource, body, namespace)
    finally:
        await k8s.close()


async def update_resource(
    session: AsyncSession, resource: str, name: str, body: dict,
    namespace: str | None = None,
) -> dict:
    """Replace (full update) a resource."""
    k8s = await _make_client(session)
    try:
        return await k8s.replace_resource(resource, name, body, namespace)
    finally:
        await k8s.close()


async def delete_resource(
    session: AsyncSession, resource: str, name: str, namespace: str | None = None,
) -> dict:
    """Delete a resource."""
    k8s = await _make_client(session)
    try:
        return await k8s.delete_resource(resource, name, namespace)
    finally:
        await k8s.close()


async def scale_resource(
    session: AsyncSession, resource: str, name: str, namespace: str, replicas: int,
) -> dict:
    """Scale a deployment or statefulset."""
    k8s = await _make_client(session)
    try:
        return await k8s.scale_resource(resource, name, namespace, replicas)
    finally:
        await k8s.close()


# ── Supported resources metadata ─────────────────────────────────


def get_supported_resources() -> list[dict]:
    """Return metadata about all supported resource types."""
    from app.k8s.client import _RESOURCE_MAP
    result = []
    for name, (_, namespaced, _, api_version) in sorted(_RESOURCE_MAP.items()):
        result.append({
            "name": name,
            "namespaced": namespaced,
            "api_version": api_version,
        })
    return result
