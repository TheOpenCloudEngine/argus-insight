"""Kubernetes API response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ClusterInfo(BaseModel):
    """Cluster-level information."""

    version: str = ""
    platform: str = ""
    node_count: int = 0
    namespace_count: int = 0
    connected: bool = False
    error: str = ""


class ResourceCount(BaseModel):
    """Count of resources with status breakdown."""

    total: int = 0
    ready: int = 0
    not_ready: int = 0
    warning: int = 0


class PodStatusBreakdown(BaseModel):
    """Pod phase breakdown for charts."""

    running: int = 0
    succeeded: int = 0
    pending: int = 0
    failed: int = 0
    unknown: int = 0


class NamespacePodCount(BaseModel):
    """Pod count per namespace for distribution chart."""

    namespace: str
    count: int = 0


class NodeResourceInfo(BaseModel):
    """Node resource capacity and usage info."""

    name: str
    cpu_capacity: str = ""
    cpu_allocatable: str = ""
    cpu_usage: str = ""
    memory_capacity: str = ""
    memory_allocatable: str = ""
    memory_usage: str = ""
    pods_capacity: str = ""
    pods_allocatable: str = ""
    pods_running: int = 0
    ready: bool = False


class NamespaceResourceUsage(BaseModel):
    """CPU and memory usage per namespace."""

    namespace: str
    cpu_usage: str = "0"
    cpu_requested: str = "0"
    memory_usage: str = "0"
    memory_requested: str = "0"
    pod_count: int = 0


class ClusterOverview(BaseModel):
    """Cluster overview data for the dashboard."""

    cluster: ClusterInfo = ClusterInfo()
    nodes: ResourceCount = ResourceCount()
    pods: ResourceCount = ResourceCount()
    deployments: ResourceCount = ResourceCount()
    services: ResourceCount = ResourceCount()
    statefulsets: ResourceCount = ResourceCount()
    daemonsets: ResourceCount = ResourceCount()
    jobs: ResourceCount = ResourceCount()
    cronjobs: ResourceCount = ResourceCount()
    namespaces: list[str] = []
    recent_events: list[dict] = []
    pod_status_breakdown: PodStatusBreakdown = PodStatusBreakdown()
    namespace_pod_counts: list[NamespacePodCount] = []
    node_resources: list[NodeResourceInfo] = []
    namespace_resource_usage: list[NamespaceResourceUsage] = []


class NamespaceOverview(BaseModel):
    """Per-namespace overview."""

    namespace: str
    pods: ResourceCount = ResourceCount()
    deployments: ResourceCount = ResourceCount()
    services: ResourceCount = ResourceCount()
    statefulsets: ResourceCount = ResourceCount()
    daemonsets: ResourceCount = ResourceCount()
    jobs: ResourceCount = ResourceCount()
    recent_events: list[dict] = []


class K8sResourceList(BaseModel):
    """Generic list of Kubernetes resources."""

    kind: str
    api_version: str
    items: list[dict]
    total: int = 0


class K8sResource(BaseModel):
    """Single Kubernetes resource."""

    kind: str
    api_version: str
    metadata: dict
    spec: dict | None = None
    status: dict | None = None
    data: dict | None = None  # for ConfigMap/Secret


class WatchEvent(BaseModel):
    """Watch event from the Kubernetes API."""

    type: str  # ADDED, MODIFIED, DELETED
    object: dict
