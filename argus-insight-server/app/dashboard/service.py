"""Dashboard service.

Aggregates data from multiple agents to provide a unified dashboard view.
"""

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.schemas import AgentStatus
from app.agent.service import list_agents
from app.dashboard.schemas import (
    AdminDashboardResponse,
    AgentSummary,
    DashboardOverview,
    RecentActivityItem,
    RecentVocItem,
    WorkspaceStatItem,
)

logger = logging.getLogger(__name__)


def get_agent_summary() -> AgentSummary:
    """Get a summary of agent statuses."""
    agents = list_agents()
    return AgentSummary(
        total=len(agents),
        online=sum(1 for a in agents if a.status == AgentStatus.ONLINE),
        offline=sum(1 for a in agents if a.status == AgentStatus.OFFLINE),
        unknown=sum(1 for a in agents if a.status == AgentStatus.UNKNOWN),
    )


def get_overview() -> DashboardOverview:
    """Get the full dashboard overview."""
    return DashboardOverview(
        agents=get_agent_summary(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_cpu(val: str | None) -> float:
    """Parse K8s CPU value (e.g., '500m', '2') to cores."""
    if not val:
        return 0.0
    val = val.strip()
    if val.endswith("m"):
        return float(val[:-1]) / 1000
    return float(val)


def _parse_memory_gi(val: str | None) -> float:
    """Parse K8s memory value (e.g., '512Mi', '2Gi') to GiB."""
    if not val:
        return 0.0
    val = val.strip()
    m = re.match(r"^([\d.]+)\s*(Gi|Mi|Ti|Ki|G|M|T|K)?$", val, re.IGNORECASE)
    if not m:
        return 0.0
    n = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in ("gi", "g"):
        return n
    if unit in ("mi", "m"):
        return n / 1024
    if unit in ("ti", "t"):
        return n * 1024
    return n


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

async def get_admin_overview(session: AsyncSession) -> AdminDashboardResponse:
    """Aggregate admin dashboard data from DB only (zero K8s calls)."""
    from workspace_provisioner.models import (
        ArgusWorkspace,
        ArgusWorkspaceAuditLog,
        ArgusWorkspaceService,
    )
    from app.usermgr.models import ArgusUser
    from app.voc.models import ArgusVocIssue

    # ── Workspaces ────────────────────────────────────────
    ws_rows = (await session.execute(
        select(
            ArgusWorkspace.id,
            ArgusWorkspace.name,
            ArgusWorkspace.display_name,
            ArgusWorkspace.status,
            ArgusWorkspace.k8s_namespace,
        ).where(ArgusWorkspace.status != "deleted")
    )).all()
    workspaces_total = len(ws_rows)
    workspaces_active = sum(1 for r in ws_rows if r.status == "active")

    # ── Users ─────────────────────────────────────────────
    users_total = (await session.execute(
        select(func.count(ArgusUser.id))
    )).scalar() or 0
    users_active = (await session.execute(
        select(func.count(ArgusUser.id)).where(ArgusUser.status == "active")
    )).scalar() or 0

    # ── Services ──────────────────────────────────────────
    all_services = (await session.execute(
        select(ArgusWorkspaceService)
    )).scalars().all()
    services_total = len(all_services)
    services_running = sum(1 for s in all_services if s.status == "running")

    # ── Aggregate resources from K8s pods (1 list_pods per active ws) ──
    cluster_cpu_req = 0.0
    cluster_cpu_lim = 0.0
    cluster_mem_req = 0.0
    cluster_mem_lim = 0.0
    cluster_storage = 0.0

    # Per-workspace service counts from DB
    ws_svc_counts: dict[int, int] = {}
    for svc in all_services:
        ws_svc_counts[svc.workspace_id] = ws_svc_counts.get(svc.workspace_id, 0) + 1

    # Fetch pod resources from K8s for workspaces that have services
    ws_resources: dict[int, dict] = {}
    active_ws = [r for r in ws_rows if r.status in ("active", "failed") and ws_svc_counts.get(r.id, 0) > 0]

    if active_ws:
        from app.k8s.service import _make_client
        k8s = await _make_client(session)
        try:
            for ws_row in active_ws:
                ns = ws_row.k8s_namespace or f"argus-ws-{ws_row.name}"
                try:
                    pod_data = await k8s.list_resources("pods", namespace=ns)
                    pvc_data = await k8s.list_resources(
                        "persistentvolumeclaims", namespace=ns,
                    )
                except Exception:
                    continue

                ws_cpu_req = 0.0
                ws_cpu_lim = 0.0
                ws_mem_req = 0.0
                ws_mem_lim = 0.0
                ws_storage = 0.0

                for pod in pod_data.get("items", []):
                    for c in pod.get("spec", {}).get("containers", []):
                        res = c.get("resources", {})
                        ws_cpu_req += _parse_cpu(res.get("requests", {}).get("cpu"))
                        ws_cpu_lim += _parse_cpu(res.get("limits", {}).get("cpu"))
                        ws_mem_req += _parse_memory_gi(
                            res.get("requests", {}).get("memory"),
                        )
                        ws_mem_lim += _parse_memory_gi(
                            res.get("limits", {}).get("memory"),
                        )

                for pvc in pvc_data.get("items", []):
                    cap = pvc.get("status", {}).get("capacity", {}).get("storage")
                    ws_storage += _parse_memory_gi(cap)

                ws_resources[ws_row.id] = {
                    "cpu_req": ws_cpu_req,
                    "cpu_lim": ws_cpu_lim,
                    "mem_req": ws_mem_req,
                    "mem_lim": ws_mem_lim,
                    "storage": ws_storage,
                }
                cluster_cpu_req += ws_cpu_req
                cluster_cpu_lim += ws_cpu_lim
                cluster_mem_req += ws_mem_req
                cluster_mem_lim += ws_mem_lim
                cluster_storage += ws_storage
        finally:
            await k8s.close()

    # Build workspace stats
    workspace_stats = []
    for r in ws_rows:
        wr = ws_resources.get(r.id, {})
        workspace_stats.append(WorkspaceStatItem(
            id=r.id,
            name=r.name,
            display_name=r.display_name,
            status=r.status,
            service_count=ws_svc_counts.get(r.id, 0),
            cpu_used=round(wr.get("cpu_req", 0.0), 2),
            memory_used_gb=round(wr.get("mem_req", 0.0), 2),
        ))

    # ── VOC (current month) ─────────────────────────────────
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    voc_all = (await session.execute(select(ArgusVocIssue))).scalars().all()
    voc_open = sum(1 for v in voc_all if v.status in ("open", "in_progress"))
    voc_critical = sum(1 for v in voc_all if v.priority == "critical" and v.status in ("open", "in_progress"))

    # Distribution counts: this month only
    voc_month = [v for v in voc_all if v.created_at and v.created_at >= month_start]
    voc_by_status: dict[str, int] = {}
    voc_by_category: dict[str, int] = {}
    voc_by_priority: dict[str, int] = {}
    for v in voc_month:
        voc_by_status[v.status] = voc_by_status.get(v.status, 0) + 1
        voc_by_category[v.category] = voc_by_category.get(v.category, 0) + 1
        voc_by_priority[v.priority] = voc_by_priority.get(v.priority, 0) + 1

    # Recent VOC (5)
    recent_voc_rows = (await session.execute(
        select(ArgusVocIssue).order_by(ArgusVocIssue.created_at.desc()).limit(5)
    )).scalars().all()
    recent_voc = [
        RecentVocItem(
            id=v.id, title=v.title, category=v.category,
            priority=v.priority, status=v.status,
            workspace_name=v.workspace_name,
            author_username=v.author_username,
            created_at=v.created_at,
        )
        for v in recent_voc_rows
    ]

    # ── Recent Activity (10) ──────────────────────────────
    activity_rows = (await session.execute(
        select(ArgusWorkspaceAuditLog)
        .order_by(ArgusWorkspaceAuditLog.created_at.desc())
        .limit(10)
    )).scalars().all()
    recent_activity = [
        RecentActivityItem(
            action=a.action,
            actor_username=a.actor_username,
            workspace_name=a.workspace_name,
            detail=a.detail,
            created_at=a.created_at,
        )
        for a in activity_rows
    ]

    return AdminDashboardResponse(
        workspaces_total=workspaces_total,
        workspaces_active=workspaces_active,
        users_total=users_total,
        users_active=users_active,
        services_total=services_total,
        services_running=services_running,
        voc_open=voc_open,
        voc_critical=voc_critical,
        cluster_cpu_used=round(cluster_cpu_req, 2),
        cluster_cpu_limit=round(cluster_cpu_lim, 2),
        cluster_memory_used_gb=round(cluster_mem_req, 2),
        cluster_memory_limit_gb=round(cluster_mem_lim, 2),
        cluster_storage_gb=round(cluster_storage, 2),
        workspace_stats=workspace_stats,
        voc_by_status=voc_by_status,
        voc_by_category=voc_by_category,
        voc_by_priority=voc_by_priority,
        recent_voc=recent_voc,
        recent_activity=recent_activity,
    )
