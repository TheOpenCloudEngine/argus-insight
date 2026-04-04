"""Business logic for resource profile management and quota enforcement."""

import logging
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.resource_profile.models import ArgusResourceProfile
from app.resource_profile.resource_utils import parse_cpu, parse_memory_to_mib
from app.resource_profile.schemas import (
    ResourceProfileCreateRequest,
    ResourceProfileResponse,
    ResourceProfileUpdateRequest,
    ServiceResourceItem,
    WorkspaceResourceUsageResponse,
)

logger = logging.getLogger(__name__)


def _gb_to_mib(gb: float) -> int:
    """Convert GB to MiB (1 GB = 1024 MiB)."""
    return int(Decimal(str(gb)) * 1024)


def _mib_to_gb(mib: int) -> float:
    """Convert MiB to GB (1024 MiB = 1 GB)."""
    return round(mib / 1024, 2)


def _profile_to_response(p: ArgusResourceProfile) -> ResourceProfileResponse:
    return ResourceProfileResponse(
        id=p.id,
        name=p.name,
        display_name=p.display_name,
        description=p.description,
        cpu_cores=float(p.cpu_cores),
        memory_gb=_mib_to_gb(p.memory_mb),
        is_default=p.is_default,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ── Profile CRUD ──────────────────────────────────────────────────


async def create_resource_profile(
    session: AsyncSession,
    req: ResourceProfileCreateRequest,
) -> ResourceProfileResponse:
    """Create a new resource profile."""
    if req.is_default:
        await _clear_default(session)

    profile = ArgusResourceProfile(
        name=req.name,
        display_name=req.name,  # display_name deprecated, use name
        description=req.description,
        cpu_cores=Decimal(str(req.cpu_cores)),
        memory_mb=_gb_to_mib(req.memory_gb),
        is_default=req.is_default,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    logger.info("Resource profile created: %s (id=%d)", profile.name, profile.id)
    return _profile_to_response(profile)


async def list_resource_profiles(session: AsyncSession) -> list[ResourceProfileResponse]:
    """List all resource profiles ordered by name."""
    result = await session.execute(
        select(ArgusResourceProfile).order_by(ArgusResourceProfile.name)
    )
    return [_profile_to_response(p) for p in result.scalars().all()]


async def get_resource_profile(
    session: AsyncSession, profile_id: int
) -> ResourceProfileResponse | None:
    """Get a single resource profile by ID."""
    result = await session.execute(
        select(ArgusResourceProfile).where(ArgusResourceProfile.id == profile_id)
    )
    p = result.scalars().first()
    return _profile_to_response(p) if p else None


async def update_resource_profile(
    session: AsyncSession,
    profile_id: int,
    req: ResourceProfileUpdateRequest,
) -> ResourceProfileResponse | None:
    """Update a resource profile."""
    result = await session.execute(
        select(ArgusResourceProfile).where(ArgusResourceProfile.id == profile_id)
    )
    profile = result.scalars().first()
    if not profile:
        return None

    if req.name is not None:
        profile.name = req.name
        profile.display_name = req.name  # keep in sync
    if req.description is not None:
        profile.description = req.description
    if req.cpu_cores is not None:
        profile.cpu_cores = Decimal(str(req.cpu_cores))
    if req.memory_gb is not None:
        profile.memory_mb = _gb_to_mib(req.memory_gb)
    if req.is_default is not None:
        if req.is_default:
            await _clear_default(session)
        profile.is_default = req.is_default

    await session.commit()
    await session.refresh(profile)
    logger.info("Resource profile updated: %s (id=%d)", profile.name, profile.id)
    return _profile_to_response(profile)


async def delete_resource_profile(session: AsyncSession, profile_id: int) -> bool:
    """Delete a resource profile. Returns True if deleted."""
    result = await session.execute(
        select(ArgusResourceProfile).where(ArgusResourceProfile.id == profile_id)
    )
    profile = result.scalars().first()
    if not profile:
        return False
    await session.delete(profile)
    await session.commit()
    logger.info("Resource profile deleted: %s (id=%d)", profile.name, profile.id)
    return True


async def _clear_default(session: AsyncSession) -> None:
    """Clear is_default flag on all profiles."""
    await session.execute(
        update(ArgusResourceProfile)
        .where(ArgusResourceProfile.is_default.is_(True))
        .values(is_default=False)
    )


# ── Workspace Profile Assignment ──────────────────────────────────


async def assign_profile_to_workspace(
    session: AsyncSession, workspace_id: int, profile_id: int | None
) -> bool:
    """Assign a resource profile to a workspace. Returns True if workspace exists."""
    from workspace_provisioner.models import ArgusWorkspace

    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        return False
    ws.resource_profile_id = profile_id
    await session.commit()
    logger.info("Workspace %d assigned profile_id=%s", workspace_id, profile_id)

    # Update K8s ResourceQuota if workspace has an active namespace
    if profile_id and ws.status == "active":
        namespace = ws.k8s_namespace or f"argus-ws-{ws.name}"
        profile = await get_resource_profile(session, profile_id)
        if profile:
            try:
                from workspace_provisioner.workflow.steps.app_deploy import apply_resource_quota
                import asyncio
                await apply_resource_quota(namespace, profile.cpu_cores, profile.memory_gb * 1024)
                logger.info("ResourceQuota updated: workspace=%d namespace=%s cpu=%s mem=%sGi",
                            workspace_id, namespace, profile.cpu_cores, profile.memory_gb)
            except Exception as e:
                logger.warning("Failed to update ResourceQuota for workspace %d: %s", workspace_id, e)

    return True


async def get_default_profile_id(session: AsyncSession) -> int | None:
    """Get the ID of the default resource profile, if any."""
    result = await session.execute(
        select(ArgusResourceProfile.id).where(ArgusResourceProfile.is_default.is_(True))
    )
    row = result.scalars().first()
    return row


# ── Resource Usage & Quota Check ──────────────────────────────────


async def get_workspace_resource_usage(
    session: AsyncSession, workspace_id: int
) -> WorkspaceResourceUsageResponse | None:
    """Calculate resource usage for a workspace and compare against profile limits."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        return None

    # Load profile
    profile_resp = None
    if ws.resource_profile_id:
        profile_resp = await get_resource_profile(session, ws.resource_profile_id)

    # Sum service resources
    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
            ArgusWorkspaceService.status == "running",
        )
    )
    services = svc_result.scalars().all()

    total_cpu = Decimal("0")
    total_memory_mib = 0
    service_items: list[ServiceResourceItem] = []

    for svc in services:
        cpu, mem_mib = _extract_service_resources(svc.metadata_json)
        total_cpu += cpu
        total_memory_mib += mem_mib
        service_items.append(
            ServiceResourceItem(
                plugin_name=svc.plugin_name,
                display_name=svc.display_name,
                service_id=svc.service_id,
                cpu_cores=float(cpu),
                memory_gb=_mib_to_gb(mem_mib),
            )
        )

    return WorkspaceResourceUsageResponse(
        profile=profile_resp,
        cpu_used=float(total_cpu),
        cpu_limit=profile_resp.cpu_cores if profile_resp else None,
        memory_used_gb=_mib_to_gb(total_memory_mib),
        memory_limit_gb=profile_resp.memory_gb if profile_resp else None,
        services=service_items,
    )


async def check_resource_quota(
    session: AsyncSession,
    workspace_id: int,
    additional_cpu: str,
    additional_memory: str,
) -> tuple[bool, dict]:
    """Check if adding resources would exceed the workspace's profile quota.

    Returns:
        (allowed, details) where allowed is True if within quota.
    """
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws or not ws.resource_profile_id:
        return True, {"reason": "no_profile_assigned"}

    # Load profile
    p_result = await session.execute(
        select(ArgusResourceProfile).where(
            ArgusResourceProfile.id == ws.resource_profile_id
        )
    )
    profile = p_result.scalars().first()
    if not profile:
        return True, {"reason": "profile_not_found"}

    # Current usage
    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
            ArgusWorkspaceService.status == "running",
        )
    )
    services = svc_result.scalars().all()

    current_cpu = Decimal("0")
    current_memory_mib = 0
    for svc in services:
        cpu, mem = _extract_service_resources(svc.metadata_json)
        current_cpu += cpu
        current_memory_mib += mem

    add_cpu = parse_cpu(additional_cpu)
    add_mem = parse_memory_to_mib(additional_memory)

    new_cpu = current_cpu + add_cpu
    new_memory_mib = current_memory_mib + add_mem

    cpu_ok = new_cpu <= Decimal(str(profile.cpu_cores))
    mem_ok = new_memory_mib <= profile.memory_mb

    details = {
        "cpu_current": float(current_cpu),
        "cpu_requested": float(add_cpu),
        "cpu_total": float(new_cpu),
        "cpu_limit": float(profile.cpu_cores),
        "memory_current_gb": _mib_to_gb(current_memory_mib),
        "memory_requested_gb": _mib_to_gb(add_mem),
        "memory_total_gb": _mib_to_gb(new_memory_mib),
        "memory_limit_gb": _mib_to_gb(profile.memory_mb),
    }

    if not cpu_ok or not mem_ok:
        reasons = []
        if not cpu_ok:
            reasons.append("cpu_exceeded")
        if not mem_ok:
            reasons.append("memory_exceeded")
        details["reasons"] = reasons
        return False, details

    return True, details


def _extract_service_resources(metadata: dict | None) -> tuple[Decimal, int]:
    """Extract CPU (cores) and memory (MiB) from service metadata."""
    if not metadata:
        return Decimal("0"), 0
    resources = metadata.get("resources")
    if not resources:
        return Decimal("0"), 0
    cpu = parse_cpu(resources.get("cpu_limit", "0"))
    mem = parse_memory_to_mib(resources.get("memory_limit", "0"))
    return cpu, mem
