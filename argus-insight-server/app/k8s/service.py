"""Kubernetes service layer — business logic between router and client."""

from __future__ import annotations

import fnmatch
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.k8s.client import K8sClient
from app.k8s.schemas import (
    ClusterInfo,
    ClusterOverview,
    K8sResource,
    K8sResourceList,
    NamespacePodCount,
    NamespaceOverview,
    NamespaceResourceUsage,
    NodeResourceInfo,
    PodStatusBreakdown,
    ResourceCount,
)
from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)


# ── Cluster Overview Cache ────────────────────────────────────────

_overview_cache: ClusterOverview | None = None
_overview_cache_time: float = 0


async def _get_k8s_config(session: AsyncSession) -> dict[str, str]:
    """Read all k8s config from the database."""
    result = await session.execute(
        select(ArgusConfiguration).where(ArgusConfiguration.category == "k8s")
    )
    rows = {r.config_key: r.config_value for r in result.scalars().all()}
    return rows


async def _make_client(session: AsyncSession) -> K8sClient:
    cfg = await _get_k8s_config(session)
    kubeconfig = cfg.get("k8s_kubeconfig_path", "/etc/rancher/k3s/k3s.yaml")
    context = cfg.get("k8s_context", "")
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


def _pod_status_breakdown(items: list[dict]) -> PodStatusBreakdown:
    breakdown = PodStatusBreakdown()
    for pod in items:
        phase = (pod.get("status") or {}).get("phase", "Unknown")
        if phase == "Running":
            breakdown.running += 1
        elif phase == "Succeeded":
            breakdown.succeeded += 1
        elif phase == "Pending":
            breakdown.pending += 1
        elif phase == "Failed":
            breakdown.failed += 1
        else:
            breakdown.unknown += 1
    return breakdown


def _namespace_pod_counts(items: list[dict]) -> list[NamespacePodCount]:
    ns_map: dict[str, int] = {}
    for pod in items:
        ns = (pod.get("metadata") or {}).get("namespace", "default")
        ns_map[ns] = ns_map.get(ns, 0) + 1
    counts = [NamespacePodCount(namespace=ns, count=c) for ns, c in ns_map.items()]
    counts.sort(key=lambda x: x.count, reverse=True)
    return counts


def _extract_node_resources(
    node_items: list[dict],
    pod_items: list[dict] | None = None,
    metrics: list[dict] | None = None,
) -> list[NodeResourceInfo]:
    metrics_map: dict[str, dict] = {}
    if metrics:
        for m in metrics:
            metrics_map[m["name"]] = m

    # Count running pods per node
    node_pod_counts: dict[str, int] = {}
    if pod_items:
        for pod in pod_items:
            phase = (pod.get("status") or {}).get("phase", "")
            node_name = (pod.get("spec") or {}).get("nodeName", "")
            if node_name and phase in ("Running", "Pending"):
                node_pod_counts[node_name] = node_pod_counts.get(node_name, 0) + 1

    result = []
    for node in node_items:
        metadata = node.get("metadata") or {}
        status = node.get("status") or {}
        capacity = status.get("capacity") or {}
        allocatable = status.get("allocatable") or {}
        conditions = status.get("conditions") or []
        is_ready = any(
            c.get("type") == "Ready" and c.get("status") == "True"
            for c in conditions
        )
        name = metadata.get("name", "")
        node_metrics = metrics_map.get(name, {})
        result.append(NodeResourceInfo(
            name=name,
            cpu_capacity=capacity.get("cpu", "0"),
            cpu_allocatable=allocatable.get("cpu", "0"),
            cpu_usage=node_metrics.get("cpu_usage", "0"),
            memory_capacity=capacity.get("memory", "0"),
            memory_allocatable=allocatable.get("memory", "0"),
            memory_usage=node_metrics.get("memory_usage", "0"),
            pods_capacity=capacity.get("pods", "0"),
            pods_allocatable=allocatable.get("pods", "0"),
            pods_running=node_pod_counts.get(name, 0),
            ready=is_ready,
        ))
    return result


def _parse_cpu_nanocores(value: str) -> int:
    """Parse CPU value to nanocores."""
    if not value or value == "0":
        return 0
    if value.endswith("n"):
        return int(value[:-1])
    if value.endswith("u"):
        return int(value[:-1]) * 1000
    if value.endswith("m"):
        return int(value[:-1]) * 1_000_000
    return int(float(value) * 1_000_000_000)


def _parse_memory_bytes(value: str) -> int:
    """Parse memory value to bytes."""
    if not value or value == "0":
        return 0
    if value.endswith("Ki"):
        return int(value[:-2]) * 1024
    if value.endswith("Mi"):
        return int(value[:-2]) * 1024 * 1024
    if value.endswith("Gi"):
        return int(value[:-2]) * 1024 * 1024 * 1024
    if value.endswith("Ti"):
        return int(value[:-2]) * 1024 * 1024 * 1024 * 1024
    return int(value)


def _format_cpu_cores(nanocores: int) -> str:
    """Format nanocores to cores string."""
    cores = nanocores / 1_000_000_000
    if cores >= 10:
        return f"{cores:.1f}"
    return f"{cores:.2f}"


def _format_memory_mi(mem_bytes: int) -> str:
    """Format bytes to MiB or GiB string."""
    mi = mem_bytes / (1024 * 1024)
    if mi >= 1024:
        return f"{mi / 1024:.1f}Gi"
    return f"{int(mi)}Mi"


def _aggregate_namespace_resource_usage(
    pod_metrics: list[dict],
    pod_items: list[dict] | None = None,
) -> list[NamespaceResourceUsage]:
    """Aggregate CPU and memory usage by namespace from pod metrics."""
    # Aggregate actual usage from metrics
    ns_map: dict[str, dict] = {}
    for pod in pod_metrics:
        ns = (pod.get("metadata") or {}).get("namespace", "default")
        containers = pod.get("containers") or []
        if ns not in ns_map:
            ns_map[ns] = {"cpu": 0, "memory": 0, "cpu_req": 0, "mem_req": 0, "pods": 0}
        ns_map[ns]["pods"] += 1
        for c in containers:
            usage = c.get("usage") or {}
            ns_map[ns]["cpu"] += _parse_cpu_nanocores(usage.get("cpu", "0"))
            ns_map[ns]["memory"] += _parse_memory_bytes(usage.get("memory", "0"))

    # Aggregate requested resources from pod specs
    if pod_items:
        for pod in pod_items:
            phase = (pod.get("status") or {}).get("phase", "")
            if phase not in ("Running", "Pending"):
                continue
            ns = (pod.get("metadata") or {}).get("namespace", "default")
            if ns not in ns_map:
                ns_map[ns] = {"cpu": 0, "memory": 0, "cpu_req": 0, "mem_req": 0, "pods": 0}
            for c in (pod.get("spec") or {}).get("containers") or []:
                requests = (c.get("resources") or {}).get("requests") or {}
                ns_map[ns]["cpu_req"] += _parse_cpu_nanocores(requests.get("cpu", "0"))
                ns_map[ns]["mem_req"] += _parse_memory_bytes(requests.get("memory", "0"))

    result = []
    for ns, data in ns_map.items():
        result.append(NamespaceResourceUsage(
            namespace=ns,
            cpu_usage=_format_cpu_cores(data["cpu"]),
            cpu_requested=_format_cpu_cores(data["cpu_req"]),
            memory_usage=_format_memory_mi(data["memory"]),
            memory_requested=_format_memory_mi(data["mem_req"]),
            pod_count=data["pods"],
        ))
    result.sort(key=lambda x: float(x.cpu_usage), reverse=True)
    return result


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


def _filter_pods_by_pattern(items: list[dict], pattern: str) -> list[dict]:
    """Filter pod items by name pattern (fnmatch glob)."""
    if not pattern or pattern == "*":
        return items
    return [
        p for p in items
        if fnmatch.fnmatch((p.get("metadata") or {}).get("name", ""), pattern)
    ]


def _filter_pod_metrics_by_pattern(items: list[dict], pattern: str) -> list[dict]:
    """Filter pod metrics by name pattern (fnmatch glob)."""
    if not pattern or pattern == "*":
        return items
    return [
        p for p in items
        if fnmatch.fnmatch((p.get("metadata") or {}).get("name", ""), pattern)
    ]


async def get_cluster_overview(session: AsyncSession) -> ClusterOverview:
    """Aggregate cluster-wide overview data with server-side caching."""
    global _overview_cache, _overview_cache_time

    # Read monitoring settings
    cfg = await _get_k8s_config(session)
    cache_ttl = max(int(cfg.get("k8s_monitoring_cache_ttl", "60")), 60)
    pod_filter = cfg.get("k8s_monitoring_pod_filter", "argus-*")

    # Return cached result if still valid
    now = time.monotonic()
    if _overview_cache is not None and (now - _overview_cache_time) < cache_ttl:
        return _overview_cache

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

        # Fetch all resource lists
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

        # Fetch metrics (best-effort, returns [] if unavailable)
        node_metrics = await k8s.get_node_metrics()
        pod_metrics_raw = await k8s.get_pod_metrics()

        pod_data = await k8s.list_resources("pods")
        deploy_data = await k8s.list_resources("deployments")
        svc_data = await k8s.list_resources("services")
        sts_data = await k8s.list_resources("statefulsets")
        ds_data = await k8s.list_resources("daemonsets")
        job_data = await k8s.list_resources("jobs")
        cj_data = await k8s.list_resources("cronjobs")
        event_data = await k8s.list_resources("events")

        # All pods (unfiltered) for cluster-wide counts
        all_pod_items = pod_data.get("items", [])

        # Filtered pods/metrics for namespace resource usage
        filtered_pod_items = _filter_pods_by_pattern(all_pod_items, pod_filter)
        filtered_pod_metrics = _filter_pod_metrics_by_pattern(pod_metrics_raw, pod_filter)

        overview = ClusterOverview(
            cluster=cluster_info,
            nodes=ResourceCount(
                total=len(node_items), ready=nodes_ready, not_ready=nodes_not_ready,
            ),
            pods=_count_pods(all_pod_items),
            deployments=_count_deployments(deploy_data.get("items", [])),
            services=_count_simple(svc_data.get("items", [])),
            statefulsets=_count_statefulsets(sts_data.get("items", [])),
            daemonsets=_count_daemonsets(ds_data.get("items", [])),
            jobs=_count_jobs(job_data.get("items", [])),
            cronjobs=_count_simple(cj_data.get("items", [])),
            namespaces=namespaces,
            recent_events=_format_events(event_data.get("items", [])),
            pod_status_breakdown=_pod_status_breakdown(all_pod_items),
            namespace_pod_counts=_namespace_pod_counts(all_pod_items),
            node_resources=_extract_node_resources(
                node_items, all_pod_items, node_metrics,
            ),
            namespace_resource_usage=_aggregate_namespace_resource_usage(
                filtered_pod_metrics, filtered_pod_items,
            ),
        )

        # Update cache
        _overview_cache = overview
        _overview_cache_time = now
        logger.debug(
            "Cluster overview cached (ttl=%ds, pod_filter=%s)", cache_ttl, pod_filter,
        )

        return overview
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
