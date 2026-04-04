"""Workspace provisioning API endpoints.

Defines the FastAPI router for workspace lifecycle management.
All endpoints are prefixed with `/workspace` and tagged for OpenAPI grouping.

Endpoint summary:
- POST   /workspaces                          - Create workspace and trigger provisioning
- GET    /workspaces                          - List workspaces with pagination
- GET    /workspaces/{workspace_id}           - Get workspace details
- DELETE /workspaces/{workspace_id}           - Delete a workspace
- POST   /workspaces/{workspace_id}/members   - Add a member
- GET    /workspaces/{workspace_id}/members   - List members
- DELETE /workspaces/{workspace_id}/members/{member_id} - Remove a member
- GET    /workspaces/{workspace_id}/workflow   - Get provisioning workflow status
"""

import asyncio
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.auth import CurrentUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from workspace_provisioner import service
from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.schemas import (
    AuditLogResponse,
    ContainerInfo,
    PaginatedAuditLogResponse,
    ServiceEventResponse,
    ServiceLogSourcesResponse,
    ServiceLogsResponse,
    ActivityItem,
    ModelDeployRequest,
    ModelListResponse,
    ModelServingStatus,
    ModelVersionItem,
    ServiceHealthItem,
    StorageItem,
    WorkspaceDashboardResponse,
    WorkspaceServiceResponse,
    PaginatedWorkspaceResponse,
    WorkspaceCreateRequest,
    WorkspaceCredentialResponse,
    WorkspaceDeleteRequest,
    WorkspaceMemberAddRequest,
    WorkspaceMemberResponse,
    WorkspacePipelineResponse,
    WorkspaceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace", tags=["workspace"])

# GitLab client singleton - initialized by init_gitlab_client()
_gitlab_client: GitLabClient | None = None


def init_gitlab_client(url: str, private_token: str) -> None:
    """Initialize the GitLab client singleton.

    Called during application startup with configuration values.

    Args:
        url: GitLab server URL (e.g., "https://gitlab-global.argus-insight.dev.net").
        private_token: GitLab API token with admin privileges.
    """
    global _gitlab_client
    logger.info("Initializing GitLab client: %s", url)
    _gitlab_client = GitLabClient(url=url, private_token=private_token)
    logger.info("GitLab client initialized successfully")


def _get_gitlab_client() -> GitLabClient:
    """FastAPI dependency to get the GitLab client."""
    if _gitlab_client is None:
        logger.error("GitLab client not initialized, returning 503")
        raise HTTPException(
            status_code=503, detail="GitLab client not initialized"
        )
    return _gitlab_client


# ---------------------------------------------------------------------------
# Workspace endpoints
# ---------------------------------------------------------------------------

@router.get("/workspaces/check")
async def check_workspace_name(
    name: str = Query(..., description="Workspace name to check"),
    session: AsyncSession = Depends(get_session),
):
    """Check if a workspace name already exists (excluding deleted)."""
    from workspace_provisioner.models import ArgusWorkspace
    result = await session.execute(
        select(ArgusWorkspace).where(
            ArgusWorkspace.name == name,
            ArgusWorkspace.status != "deleted",
        )
    )
    ws = result.scalars().first()
    return {"exists": ws is not None, "name": name}


# ---------------------------------------------------------------------------
# Workspace service auth (must be before /workspaces/{workspace_id})
# ---------------------------------------------------------------------------

import base64
import hashlib
import hmac
import json as json_module
import time
from urllib.parse import urlparse

from fastapi import Cookie, Header, Request, Response

_WS_AUTH_SECRET = "argus-workspace-auth-secret-key"
_WS_AUTH_EXPIRY = 86400  # 24 hours


def _create_ws_token(username: str, workspace_name: str, role: str) -> str:
    payload = {
        "sub": username, "workspace": workspace_name,
        "role": role, "exp": int(time.time()) + _WS_AUTH_EXPIRY,
    }
    payload_json = json_module.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
    sig = hmac.new(_WS_AUTH_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(json_module.dumps({"payload": payload_b64, "sig": sig}).encode()).decode()


def _verify_ws_token(token: str, workspace_name: str) -> dict | None:
    try:
        outer = json_module.loads(base64.urlsafe_b64decode(token))
        payload_b64 = outer["payload"]
        expected_sig = hmac.new(_WS_AUTH_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(outer["sig"], expected_sig):
            return None
        payload = json_module.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        if payload.get("workspace") != workspace_name:
            return None
        return payload
    except Exception:
        return None


@router.get("/workspaces/auth-verify")
async def workspace_auth_verify(
    request: Request,
    workspace: str = Query(""),
    service_id: str = Query(""),
    argus_ws_token: str | None = Cookie(None),
    x_original_url: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """Nginx Ingress auth-url subrequest endpoint for workspace services.

    Supports both workspace name and service_id based lookups.
    With service_id hostnames, the service_id is extracted from the hostname
    and mapped to the workspace name via argus_workspace_services.
    """
    if not argus_ws_token:
        return Response(status_code=401)

    ws_name = workspace

    # If no workspace name, try to resolve from service_id
    if not ws_name and service_id:
        from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService
        svc_result = await session.execute(
            select(ArgusWorkspaceService).where(
                ArgusWorkspaceService.service_id == service_id
            )
        )
        svc = svc_result.scalars().first()
        if svc:
            ws_result = await session.execute(
                select(ArgusWorkspace.name).where(ArgusWorkspace.id == svc.workspace_id)
            )
            ws_name = ws_result.scalar() or ""

    # Fallback: extract from X-Original-URL hostname
    if not ws_name and x_original_url:
        parsed = urlparse(x_original_url)
        host = parsed.hostname or ""
        parts = host.split(".")
        if parts:
            prefix_parts = parts[0].split("-")
            if len(prefix_parts) >= 3:
                # Try service_id lookup from hostname (e.g., argus-mlflow-67e8a400a3f1)
                potential_sid = prefix_parts[-1]
                from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService
                svc_result = await session.execute(
                    select(ArgusWorkspaceService).where(
                        ArgusWorkspaceService.service_id == potential_sid
                    )
                )
                svc = svc_result.scalars().first()
                if svc:
                    ws_result = await session.execute(
                        select(ArgusWorkspace.name).where(
                            ArgusWorkspace.id == svc.workspace_id
                        )
                    )
                    ws_name = ws_result.scalar() or ""

    if not ws_name:
        return Response(status_code=401)
    payload = _verify_ws_token(argus_ws_token, ws_name)
    if payload:
        return Response(status_code=200)
    return Response(status_code=403)


@router.get("/workspaces/auth-launch")
async def workspace_auth_launch(
    current_user: CurrentUser,
    workspace_name: str = Query(..., alias="workspace"),
    session: AsyncSession = Depends(get_session),
):
    """Generate an auth token for accessing workspace services."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.name == workspace_name)
    )
    ws = result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    member_result = await session.execute(
        select(ArgusWorkspaceMember).where(
            ArgusWorkspaceMember.workspace_id == ws.id,
            ArgusWorkspaceMember.user_id == int(current_user.sub),
        )
    )
    if not member_result.scalars().first():
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    token = _create_ws_token(current_user.username, workspace_name, current_user.role)
    return {"token": token, "workspace": workspace_name}


@router.get("/workspaces/auth-redirect")
async def workspace_auth_redirect(
    workspace: str = Query(...),
    token: str = Query(...),
    redirect: str = Query(""),
    session: AsyncSession = Depends(get_session),
):
    """Browser navigates here. Sets cookie and redirects to service."""
    payload = _verify_ws_token(token, workspace)
    if not payload:
        return Response(content="Invalid or expired token", status_code=401)
    # Derive cookie domain from the redirect URL so the cookie is valid
    # for the target service. E.g., redirect to
    # "http://argus-rstudio-xxx.argus-insight.dev.net" → cookie domain ".argus-insight.dev.net"
    cookie_domain = None
    if redirect:
        try:
            from urllib.parse import urlparse as _urlparse
            host = _urlparse(redirect).hostname or ""
            # Strip first subdomain to get the shared parent domain
            # e.g. "argus-rstudio-xxx.argus-insight.dev.net" → ".argus-insight.dev.net"
            parts = host.split(".")
            if len(parts) > 2:
                cookie_domain = "." + ".".join(parts[1:])
        except Exception:
            pass

    if not cookie_domain:
        from app.settings.service import get_config_by_category
        domain_cfg = await get_config_by_category(session, "domain")
        domain = domain_cfg.get("domain_name", "")
        cookie_domain = f".{domain}" if domain else None

    redirect_url = redirect or "/"
    response = Response(status_code=302, headers={"Location": redirect_url})
    response.set_cookie(
        key="argus_ws_token", value=token,
        domain=cookie_domain,
        path="/", max_age=_WS_AUTH_EXPIRY, httponly=False, samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------

@router.post("/workspaces", response_model=WorkspaceResponse)
async def create_workspace(
    req: WorkspaceCreateRequest,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Create a new workspace and trigger the provisioning workflow.

    The workspace is created immediately with status "provisioning".
    The provisioning workflow (GitLab project creation, etc.) runs
    asynchronously in the background. Use the GET workflow endpoint
    to monitor progress.
    """
    logger.info("POST /workspaces - name=%s, domain=%s", req.name, req.domain)
    try:
        result = await service.create_workspace(session, req, gitlab_client)
        logger.info("POST /workspaces - workspace created: id=%d, name=%s", result.id, result.name)
        return result
    except ValueError as e:
        logger.error("POST /workspaces - failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workspaces", response_model=PaginatedWorkspaceResponse)
async def list_workspaces(
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by name or display name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List workspaces with optional status/search filter and pagination."""
    logger.info("GET /workspaces - status=%s, search=%s, page=%d, page_size=%d", status, search, page, page_size)
    return await service.list_workspaces(session, status=status, search=search, page=page, page_size=page_size)


@router.get("/workspaces/my")
async def list_my_workspaces(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """List workspaces where the current user is a member."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
    user_id = int(current_user.sub)
    result = await session.execute(
        select(ArgusWorkspace)
        .join(ArgusWorkspaceMember, ArgusWorkspaceMember.workspace_id == ArgusWorkspace.id)
        .where(ArgusWorkspaceMember.user_id == user_id)
        .where(ArgusWorkspace.status != "deleted")
        .order_by(ArgusWorkspace.name)
    )
    workspaces = result.scalars().all()
    return [
        {"id": ws.id, "name": ws.name, "display_name": ws.display_name, "status": ws.status}
        for ws in workspaces
    ]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get workspace details by ID."""
    logger.info("GET /workspaces/%d", workspace_id)
    ws = await service.get_workspace(session, workspace_id)
    if not ws:
        logger.info("GET /workspaces/%d - not found", workspace_id)
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


class DeployPipelineRequest(BaseModel):
    pipeline_id: int
    plugin_config: dict | None = None  # Optional per-plugin config (e.g. {"tier": "standard"} for Trino)


class TrinoConfigureRequest(BaseModel):
    """Request body for Trino runtime configuration changes."""
    tier: str | None = None  # development | standard | performance | custom
    coordinator_replicas: int | None = None
    worker_replicas: int | None = None
    coordinator_cpu_limit: str | None = None
    coordinator_memory_limit: str | None = None
    worker_cpu_limit: str | None = None
    worker_memory_limit: str | None = None
    query_max_memory: str | None = None
    query_max_memory_per_node: str | None = None
    refresh_catalogs: bool = False


@router.post("/workspaces/{workspace_id}/trino/configure/validate")
async def validate_trino_configure(
    workspace_id: int,
    req: TrinoConfigureRequest,
    session: AsyncSession = Depends(get_session),
):
    """Check if Trino configuration change fits within workspace resource quota."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService
    from app.resource_profile.models import ArgusResourceProfile
    from app.resource_profile.resource_utils import parse_cpu, parse_memory_to_mib

    ws = (await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )).scalars().first()
    if not ws:
        raise HTTPException(404, "Workspace not found")

    # Get profile limits
    profile = None
    if ws.resource_profile_id:
        profile = (await session.execute(
            select(ArgusResourceProfile).where(ArgusResourceProfile.id == ws.resource_profile_id)
        )).scalars().first()

    # Current total usage from all running services
    svcs = (await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
            ArgusWorkspaceService.status == "running",
        )
    )).scalars().all()

    current_cpu = Decimal("0")
    current_mem_mib = 0
    trino_cpu = Decimal("0")
    trino_mem_mib = 0
    for svc in svcs:
        meta = svc.metadata_json if hasattr(svc, 'metadata_json') else (svc.metadata if isinstance(svc.metadata, dict) else {})
        res = meta.get("resources", {})
        cpu = parse_cpu(res.get("cpu_limit", "0"))
        mem = parse_memory_to_mib(res.get("memory_limit", "0"))
        current_cpu += cpu
        current_mem_mib += mem
        if svc.plugin_name == "argus-trino":
            trino_cpu = cpu
            trino_mem_mib = mem

    # Calculate new Trino resource
    coord_replicas = req.coordinator_replicas or 1
    worker_replicas = req.worker_replicas or 0
    coord_cpu = parse_cpu(req.coordinator_cpu_limit or "1")
    coord_mem = parse_memory_to_mib(req.coordinator_memory_limit or "2Gi")
    worker_cpu = parse_cpu(req.worker_cpu_limit or "2")
    worker_mem = parse_memory_to_mib(req.worker_memory_limit or "4Gi")

    new_trino_cpu = coord_cpu * coord_replicas + worker_cpu * worker_replicas
    new_trino_mem = coord_mem * coord_replicas + worker_mem * worker_replicas

    # Delta
    delta_cpu = new_trino_cpu - trino_cpu
    delta_mem = new_trino_mem - trino_mem_mib

    after_cpu = float(current_cpu + delta_cpu)
    after_mem = (current_mem_mib + delta_mem) / 1024  # GiB

    limit_cpu = float(profile.cpu_cores) if profile else 999
    limit_mem = float(profile.memory_mb) / 1024 if profile else 999

    allowed = after_cpu <= limit_cpu and after_mem <= limit_mem

    return {
        "allowed": allowed,
        "current": {"cpu_used": float(current_cpu), "memory_used_gb": round(current_mem_mib / 1024, 1)},
        "limit": {"cpu": limit_cpu, "memory_gb": round(limit_mem, 1)},
        "delta": {"cpu": float(delta_cpu), "memory_gb": round(float(delta_mem) / 1024, 1)},
        "after": {"cpu_used": round(after_cpu, 1), "memory_used_gb": round(after_mem, 1)},
        "message": "" if allowed else f"Exceeds workspace limit ({limit_cpu} CPU, {limit_mem:.0f}Gi). Upgrade the resource profile.",
    }


@router.post("/workspaces/{workspace_id}/trino/configure")
async def configure_trino(
    workspace_id: int,
    req: TrinoConfigureRequest,
    session: AsyncSession = Depends(get_session),
):
    """Apply Trino configuration changes (replicas, resources, query limits, catalogs)."""
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    ws = (await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )).scalars().first()
    if not ws:
        raise HTTPException(404, "Workspace not found")

    namespace = ws.k8s_namespace or f"argus-ws-{ws.name}"

    # Find Trino service
    svc = (await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
            ArgusWorkspaceService.plugin_name == "argus-trino",
            ArgusWorkspaceService.status == "running",
        )
    )).scalars().first()
    if not svc:
        raise HTTPException(404, "Trino service not found in this workspace")

    import asyncio as aio
    import json as json_mod
    import re

    def k8s_mem_to_java(mem: str) -> str:
        m = re.match(r"^(\d+)(Gi|Mi|G|M)$", mem)
        if not m:
            return mem
        val, unit = m.group(1), m.group(2)
        return f"{val}{'G' if unit.startswith('G') else 'M'}"

    coord_replicas = req.coordinator_replicas or 1
    worker_replicas = req.worker_replicas or 0
    coord_cpu = req.coordinator_cpu_limit or "1"
    coord_mem = req.coordinator_memory_limit or "2Gi"
    worker_cpu = req.worker_cpu_limit or "2"
    worker_mem = req.worker_memory_limit or "4Gi"
    include_coord = "true" if worker_replicas == 0 else "false"
    query_max = req.query_max_memory or "1GB"
    query_max_node = req.query_max_memory_per_node or "512MB"

    # 1. Update ConfigMap (coordinator config with query limits)
    from workspace_provisioner.kubernetes.client import kubectl_apply

    meta = svc.metadata if isinstance(svc.metadata, dict) else (json_mod.loads(svc.metadata) if isinstance(svc.metadata, str) else {})
    shared_secret = ""
    # Extract shared secret from current configmap
    proc = await aio.create_subprocess_exec(
        "kubectl", "get", "configmap", f"argus-trino-{ws.name}-config",
        "-n", namespace, "-o", "jsonpath={.data.config-coordinator\\.properties}",
        stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    for line in out.decode().split("\n"):
        if "shared-secret=" in line:
            shared_secret = line.split("=", 1)[1].strip()
            break

    coord_config = f"""coordinator=true
node-scheduler.include-coordinator={include_coord}
http-server.http.port=8080
http-server.process-forwarded=true
http-server.authentication.type=PASSWORD
http-server.authentication.allow-insecure-over-http=true
web-ui.enabled=true
web-ui.authentication.type=FIXED
web-ui.user=admin
discovery.uri=http://argus-trino-{ws.name}:8080
query.max-memory={query_max}
query.max-memory-per-node={query_max_node}
internal-communication.shared-secret={shared_secret}
"""

    # Patch configmap coordinator config
    proc = await aio.create_subprocess_exec(
        "kubectl", "get", "configmap", f"argus-trino-{ws.name}-config",
        "-n", namespace, "-o", "json",
        stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE,
    )
    cm_out, _ = await proc.communicate()
    cm = json_mod.loads(cm_out.decode())
    cm["data"]["config-coordinator.properties"] = coord_config
    cm["data"]["jvm-coordinator.config"] = f"""-server
-Xmx{k8s_mem_to_java(coord_mem)}
-XX:+UseG1GC
-XX:G1HeapRegionSize=32M
-XX:+ExplicitGCInvokesConcurrent
-XX:+HeapDumpOnOutOfMemoryError
-Djdk.attach.allowAttachSelf=true
"""
    cm["data"]["jvm-worker.config"] = f"""-server
-Xmx{k8s_mem_to_java(worker_mem)}
-XX:+UseG1GC
-XX:G1HeapRegionSize=32M
-XX:+ExplicitGCInvokesConcurrent
-XX:+HeapDumpOnOutOfMemoryError
-Djdk.attach.allowAttachSelf=true
"""
    await kubectl_apply(json_mod.dumps(cm))
    logger.info("Trino ConfigMap updated: query_max=%s, include_coord=%s", query_max, include_coord)

    # 2. Refresh catalogs if requested
    if req.refresh_catalogs:
        from workspace_provisioner.workflow.steps.trino_deploy import _build_catalog_configmap
        catalog_yaml = await _build_catalog_configmap(workspace_id, ws.name, namespace)
        await kubectl_apply(catalog_yaml)
        logger.info("Trino catalogs refreshed for workspace %s", ws.name)

    # 3. Patch Coordinator Deployment (replicas + resources)
    patch_cmd = [
        "kubectl", "patch", "deployment", f"argus-trino-{ws.name}",
        "-n", namespace, "--type=json", "-p", json_mod.dumps([
            {"op": "replace", "path": "/spec/replicas", "value": coord_replicas},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": coord_cpu},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": coord_mem},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": f"{int(float(coord_cpu.rstrip('m')) * 500)}m" if not coord_cpu.endswith("m") else coord_cpu},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": coord_mem},
        ]),
    ]
    proc = await aio.create_subprocess_exec(*patch_cmd, stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE)
    await proc.communicate()

    # 4. Patch Worker Deployment (replicas + resources)
    patch_cmd = [
        "kubectl", "patch", "deployment", f"argus-trino-{ws.name}-worker",
        "-n", namespace, "--type=json", "-p", json_mod.dumps([
            {"op": "replace", "path": "/spec/replicas", "value": worker_replicas},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": worker_cpu},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": worker_mem},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": f"{int(float(worker_cpu.rstrip('m')) * 500)}m" if not worker_cpu.endswith("m") else worker_cpu},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": worker_mem},
        ]),
    ]
    proc = await aio.create_subprocess_exec(*patch_cmd, stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE)
    await proc.communicate()

    # 5. Rollout restart to pick up ConfigMap changes
    proc = await aio.create_subprocess_exec(
        "kubectl", "rollout", "restart", f"deployment/argus-trino-{ws.name}",
        "-n", namespace, stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE,
    )
    await proc.communicate()

    # 6. Update service metadata
    meta["display"]["Tier"] = (req.tier or "custom").capitalize()
    meta["display"]["Coordinators"] = str(coord_replicas)
    meta["display"]["Workers"] = str(worker_replicas)
    meta["resources"] = {
        "cpu_limit": coord_cpu,
        "memory_limit": coord_mem,
        "worker_cpu_limit": worker_cpu,
        "worker_memory_limit": worker_mem,
    }
    from sqlalchemy import text
    await session.execute(
        text("UPDATE argus_workspace_services SET metadata = :m WHERE id = :id"),
        {"m": json_mod.dumps(meta), "id": svc.id},
    )
    await session.commit()

    logger.info("Trino configured: ws=%s tier=%s coord=%d×%s/%s worker=%d×%s/%s",
                ws.name, req.tier, coord_replicas, coord_cpu, coord_mem,
                worker_replicas, worker_cpu, worker_mem)

    return {"status": "ok", "message": "Trino configuration applied. Pods are restarting."}


@router.post("/workspaces/{workspace_id}/deploy")
async def deploy_pipeline_to_workspace(
    workspace_id: int,
    req: DeployPipelineRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Deploy a pipeline to an existing workspace."""
    import asyncio
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspacePipeline
    from workspace_provisioner.schemas import WorkspaceCreateRequest

    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check workspace is not already deploying or deleting
    if ws.status == "provisioning":
        raise HTTPException(status_code=400, detail="A deployment is already in progress for this workspace.")
    if ws.status == "deleting":
        raise HTTPException(status_code=400, detail="This workspace is being deleted.")

    # Add pipeline association
    ws_pipeline = ArgusWorkspacePipeline(
        workspace_id=workspace_id,
        pipeline_id=req.pipeline_id,
        deploy_order=0,
        status="pending",
    )
    session.add(ws_pipeline)
    await session.commit()

    # Build a minimal WorkspaceCreateRequest for the provisioning workflow
    fake_req = WorkspaceCreateRequest(
        name=ws.name,
        display_name=ws.display_name,
        domain=ws.domain,
        admin_user_id=ws.created_by,
        pipeline_ids=[req.pipeline_id],
        plugin_config=req.plugin_config,
    )

    # Update workspace status
    ws.status = "provisioning"
    await session.commit()

    # Load requesting user info (for per_user services like VS Code, Jupyter)
    from app.usermgr.models import ArgusUser
    from app.settings.service import get_config_by_category
    req_user_result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == int(current_user.sub))
    )
    req_user = req_user_result.scalars().first()
    creator_info = {}
    if req_user:
        gitlab_cfg = await get_config_by_category(session, "gitlab")
        creator_info = {
            "creator_username": req_user.username,
            "creator_email": req_user.email,
            "creator_name": f"{req_user.first_name} {req_user.last_name}".strip() or req_user.username,
            "creator_password": gitlab_cfg.get("gitlab_password", "") or "Argus!nsight2026",
            "admin_user_id": ws.created_by,
        }

    # Launch provisioning in background
    asyncio.create_task(
        service._run_provisioning_workflow(workspace_id, fake_req, gitlab_client, creator_info)
    )

    logger.info("Deploy pipeline %d to workspace %d", req.pipeline_id, workspace_id)
    return {"status": "ok", "message": f"Pipeline deployment started for workspace '{ws.name}'"}


@router.delete("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def delete_workspace(
    workspace_id: int,
    req: WorkspaceDeleteRequest = WorkspaceDeleteRequest(),
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Delete a workspace and tear down all provisioned resources.

    Sets the workspace status to "deleting" and launches a teardown
    workflow in the background. Use the GET workflow endpoint to
    monitor deletion progress.
    """
    logger.info("DELETE /workspaces/%d", workspace_id)
    try:
        result = await service.delete_workspace(session, workspace_id, gitlab_client, req)
        if not result:
            logger.info("DELETE /workspaces/%d - not found", workspace_id)
            raise HTTPException(status_code=404, detail="Workspace not found")
        logger.info("DELETE /workspaces/%d - deletion started", workspace_id)
        return result
    except ValueError as e:
        logger.error("DELETE /workspaces/%d - failed: %s", workspace_id, e)
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Credential endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/credentials",
    response_model=WorkspaceCredentialResponse,
)
async def get_workspace_credentials(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get service credentials and connection info for a workspace.

    Returns credentials generated during provisioning (GitLab URLs,
    MinIO keys, Airflow password, etc.). Only available after
    provisioning completes successfully.
    """
    logger.info("GET /workspaces/%d/credentials", workspace_id)
    cred = await service.get_workspace_credentials(session, workspace_id)
    if not cred:
        logger.info("GET /workspaces/%d/credentials - not found", workspace_id)
        raise HTTPException(status_code=404, detail="Credentials not found")
    return cred


# ---------------------------------------------------------------------------
# Service endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/services",
    response_model=list[WorkspaceServiceResponse],
)
async def get_workspace_services(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all services deployed to a workspace."""
    from workspace_provisioner.models import ArgusWorkspaceService

    result = await session.execute(
        select(ArgusWorkspaceService)
        .where(ArgusWorkspaceService.workspace_id == workspace_id)
        .order_by(ArgusWorkspaceService.created_at)
    )
    services = result.scalars().all()
    return [
        WorkspaceServiceResponse(
            id=s.id, workspace_id=s.workspace_id,
            plugin_name=s.plugin_name, service_id=s.service_id,
            display_name=s.display_name,
            version=s.version, endpoint=s.endpoint,
            username=s.username, password=s.password,
            access_token=s.access_token, status=s.status,
            metadata=s.metadata_json,
            created_at=s.created_at, updated_at=s.updated_at,
        ) for s in services
    ]


@router.delete("/workspaces/{workspace_id}/services/{service_id}")
async def delete_workspace_service(
    workspace_id: int,
    service_id: int,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete a workspace service: teardown K8s resources, DNS, DB record, audit log."""
    try:
        await service.delete_workspace_service_with_teardown(
            session=session,
            workspace_id=workspace_id,
            service_db_id=service_id,
            actor_user_id=int(current_user.sub),
            actor_username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Service log endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/services/{service_id}/log-sources",
    response_model=ServiceLogSourcesResponse,
)
async def get_service_log_sources(
    workspace_id: int,
    service_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get available log sources (containers) for a workspace service."""
    from app.k8s.service import _make_client

    k8s = await _make_client(session)
    try:
        pod_name, namespace, pod = await service.resolve_service_pod(
            session, workspace_id, service_id, k8s,
        )
    except ValueError as e:
        await k8s.close()
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        await k8s.close()

    containers = []
    for cs in pod.get("status", {}).get("containerStatuses", []):
        state = "unknown"
        for s in ("running", "waiting", "terminated"):
            if cs.get("state", {}).get(s):
                state = s
                break
        containers.append(ContainerInfo(
            name=cs["name"],
            label=service._container_label(cs["name"]),
            state=state,
            restart_count=cs.get("restartCount", 0),
        ))

    init_containers = []
    for cs in pod.get("status", {}).get("initContainerStatuses", []):
        state = "unknown"
        for s in ("running", "waiting", "terminated"):
            if cs.get("state", {}).get(s):
                state = s
                break
        init_containers.append(ContainerInfo(
            name=cs["name"],
            label=service._container_label(cs["name"]),
            state=state,
            restart_count=cs.get("restartCount", 0),
        ))

    return ServiceLogSourcesResponse(
        workspace_id=workspace_id,
        service_id=service_id,
        plugin_name=pod.get("metadata", {}).get("labels", {}).get(
            "app.kubernetes.io/name", "",
        ),
        pod_name=pod_name,
        namespace=namespace,
        containers=containers,
        init_containers=init_containers,
    )


@router.get(
    "/workspaces/{workspace_id}/services/{service_id}/logs",
    response_model=ServiceLogsResponse,
)
async def get_service_logs(
    request: Request,
    workspace_id: int,
    service_id: int,
    container: str | None = Query(None, description="Container name"),
    tail_lines: int = Query(100, alias="tailLines", ge=1, le=10000),
    since_seconds: int | None = Query(None, alias="sinceSeconds"),
    timestamps: bool = Query(True),
    follow: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Get logs from a workspace service container.

    If follow=true, returns an SSE stream instead of JSON.
    """
    from app.k8s.service import _make_client

    k8s = await _make_client(session)
    try:
        pod_name, namespace, _pod = await service.resolve_service_pod(
            session, workspace_id, service_id, k8s,
        )
    except ValueError as e:
        await k8s.close()
        raise HTTPException(status_code=404, detail=str(e))

    if follow:
        import json as json_module
        from starlette.responses import StreamingResponse
        from typing import AsyncIterator

        async def log_stream() -> AsyncIterator[str]:
            try:
                async for line in k8s.get_pod_logs(
                    pod_name, namespace,
                    container=container,
                    follow=True,
                    tail_lines=tail_lines,
                    since_seconds=since_seconds,
                    timestamps=timestamps,
                ):
                    if await request.is_disconnected():
                        break
                    yield f"data: {json_module.dumps({'line': line})}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json_module.dumps({'error': str(e)})}\n\n"
            finally:
                await k8s.close()

        return StreamingResponse(
            log_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            lines: list[str] = []
            async for line in k8s.get_pod_logs(
                pod_name, namespace,
                container=container,
                follow=False,
                tail_lines=tail_lines,
                since_seconds=since_seconds,
                timestamps=timestamps,
            ):
                lines.append(line)
            return ServiceLogsResponse(
                pod_name=pod_name,
                container=container or "",
                lines=lines,
            )
        except Exception as e:
            logger.error(
                "Failed to get logs for workspace=%d service=%d: %s",
                workspace_id, service_id, e,
            )
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            await k8s.close()


@router.get(
    "/workspaces/{workspace_id}/services/{service_id}/events",
    response_model=list[ServiceEventResponse],
)
async def get_service_events(
    workspace_id: int,
    service_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get Kubernetes events for a workspace service pod."""
    from app.k8s.service import _make_client

    k8s = await _make_client(session)
    try:
        pod_name, namespace, _pod = await service.resolve_service_pod(
            session, workspace_id, service_id, k8s,
        )
    except ValueError:
        await k8s.close()
        return []

    try:
        event_data = await k8s.list_resources(
            "events", namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
        )
    finally:
        await k8s.close()

    events = []
    for ev in event_data.get("items", []):
        events.append(ServiceEventResponse(
            type=ev.get("type", "Normal"),
            reason=ev.get("reason", ""),
            message=ev.get("message", ""),
            count=ev.get("count", 1),
            first_timestamp=ev.get("firstTimestamp"),
            last_timestamp=ev.get("lastTimestamp"),
            source_component=ev.get("source", {}).get("component"),
        ))
    return events


# ---------------------------------------------------------------------------
# Pipeline association endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/pipelines",
    response_model=list[WorkspacePipelineResponse],
)
async def get_workspace_pipelines(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get pipelines associated with a workspace."""
    from workspace_provisioner.models import ArgusWorkspacePipeline
    from workspace_provisioner.plugins.models import ArgusPipeline

    result = await session.execute(
        select(ArgusWorkspacePipeline)
        .where(ArgusWorkspacePipeline.workspace_id == workspace_id)
        .order_by(ArgusWorkspacePipeline.deploy_order)
    )
    ws_pipelines = result.scalars().all()

    responses = []
    for wp in ws_pipelines:
        # Load pipeline name
        p_result = await session.execute(
            select(ArgusPipeline).where(ArgusPipeline.id == wp.pipeline_id)
        )
        pipeline = p_result.scalars().first()
        responses.append(WorkspacePipelineResponse(
            id=wp.id,
            pipeline_id=wp.pipeline_id,
            pipeline_name=pipeline.name if pipeline else None,
            pipeline_display_name=pipeline.display_name if pipeline else None,
            deploy_order=wp.deploy_order,
            status=wp.status,
            created_at=wp.created_at,
        ))
    return responses


# ---------------------------------------------------------------------------
# LLM Proxy (AI Playground → workspace LLM services)
# ---------------------------------------------------------------------------

@router.post("/workspaces/{workspace_id}/llm/chat")
async def llm_chat_proxy(
    request: Request,
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Proxy chat completions to workspace LLM service (vLLM/Ollama).

    Avoids CORS and auth issues by routing through the backend server
    which can reach K8s internal endpoints directly via Ingress.
    """
    import httpx
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService
    from starlette.responses import StreamingResponse

    body = await request.json()
    service_id = body.pop("_service_id", None)  # custom field to select service

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Find target LLM service
    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
            ArgusWorkspaceService.plugin_name.in_(["argus-vllm", "argus-ollama"]),
        )
    )
    llm_services = svc_result.scalars().all()
    if not llm_services:
        raise HTTPException(status_code=404, detail="No LLM service in this workspace")

    # Select service by _service_id or first available
    target = None
    if service_id:
        target = next((s for s in llm_services if str(s.id) == str(service_id)), None)
    if not target:
        target = llm_services[0]

    # Use external endpoint (Ingress) since server may be outside K8s
    base_url = target.endpoint or ""
    if not base_url:
        raise HTTPException(status_code=502, detail="LLM service has no endpoint")

    # Ollama needs /v1 prefix for OpenAI-compatible API
    if target.plugin_name == "argus-ollama" and "/v1" not in base_url:
        base_url = base_url.rstrip("/") + "/v1"

    url = f"{base_url}/chat/completions"
    is_stream = body.get("stream", False)

    if is_stream:
        async def proxy_stream():
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", url, json=body) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            proxy_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )


@router.get("/workspaces/{workspace_id}/llm/models")
async def llm_list_models(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List available models from workspace LLM services."""
    import httpx
    from workspace_provisioner.models import ArgusWorkspaceService

    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
            ArgusWorkspaceService.plugin_name.in_(["argus-vllm", "argus-ollama"]),
            ArgusWorkspaceService.status == "running",
        )
    )
    services = svc_result.scalars().all()

    result = []
    for svc in services:
        base_url = svc.endpoint or ""
        if not base_url:
            continue

        try:
            if svc.plugin_name == "argus-ollama":
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{base_url}/api/tags")
                    if resp.status_code == 200:
                        for m in resp.json().get("models", []):
                            result.append({
                                "service_id": svc.id,
                                "service_type": "ollama",
                                "service_label": svc.display_name or "Ollama",
                                "model": m["name"],
                            })
            elif svc.plugin_name == "argus-vllm":
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{base_url}/v1/models")
                    if resp.status_code == 200:
                        for m in resp.json().get("data", []):
                            result.append({
                                "service_id": svc.id,
                                "service_type": "vllm",
                                "service_label": svc.display_name or "vLLM",
                                "model": m["id"],
                            })
        except Exception as e:
            logger.debug("Failed to list models from %s: %s", svc.plugin_name, e)

    return {"models": result}


# ---------------------------------------------------------------------------
# Model deployment (MLflow → KServe)
# ---------------------------------------------------------------------------

# MLflow model flavor → KServe modelFormat mapping
_FLAVOR_TO_KSERVE: dict[str, str] = {
    "sklearn": "sklearn",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "xgboost": "xgboost",
    "lightgbm": "lightgbm",
    "onnx": "onnx",
    "transformers": "huggingface",
}


def _detect_framework(run_info: dict) -> str:
    """Detect model framework from MLflow run tags or flavors."""
    tags = run_info.get("tags", {})
    # Check mlflow.log_model.history tag
    if isinstance(tags, dict):
        for key in tags:
            for flavor in _FLAVOR_TO_KSERVE:
                if flavor in key.lower():
                    return flavor
    return "mlflow"  # fallback: mlserver handles all flavors


def _check_service_exists(
    services: list, plugin_name: str,
) -> bool:
    """Check if a specific plugin service exists in the workspace."""
    return any(s.plugin_name == plugin_name for s in services)


@router.get(
    "/workspaces/{workspace_id}/models",
    response_model=ModelListResponse,
)
async def list_models(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List registered models from workspace's MLflow instance.

    Also reports whether MLflow and KServe are available.
    """
    import httpx
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    # Load workspace + services
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
        )
    )
    services = svc_result.scalars().all()

    mlflow_available = _check_service_exists(services, "argus-mlflow")
    kserve_available = _check_service_exists(services, "argus-kserve")

    if not mlflow_available:
        return ModelListResponse(
            models=[], mlflow_available=False, kserve_available=kserve_available,
        )

    # Find MLflow internal endpoint
    mlflow_svc = next(
        (s for s in services if s.plugin_name == "argus-mlflow"), None,
    )
    if not mlflow_svc:
        return ModelListResponse(models=[], mlflow_available=False, kserve_available=kserve_available)

    # Prefer external endpoint (works from both inside and outside K8s cluster),
    # fall back to internal endpoint
    mlflow_url = mlflow_svc.endpoint or (
        mlflow_svc.metadata_json or {}
    ).get("internal", {}).get("endpoint", "")

    # Query MLflow REST API
    models: list[ModelVersionItem] = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # List registered models
            resp = await client.get(
                f"{mlflow_url}/api/2.0/mlflow/registered-models/search",
                params={"max_results": 100},
            )
            if resp.status_code != 200:
                return ModelListResponse(
                    models=[], mlflow_available=True, kserve_available=kserve_available,
                )
            data = resp.json()
            for rm in data.get("registered_models", []):
                latest = rm.get("latest_versions", [{}])
                for mv in latest:
                    run_id = mv.get("run_id", "")
                    # Fetch run metrics
                    metrics: dict[str, float] = {}
                    if run_id:
                        try:
                            run_resp = await client.get(
                                f"{mlflow_url}/api/2.0/mlflow/runs/get",
                                params={"run_id": run_id},
                            )
                            if run_resp.status_code == 200:
                                run_data = run_resp.json().get("run", {})
                                run_metrics = run_data.get("data", {}).get("metrics", [])
                                for m in run_metrics:
                                    metrics[m["key"]] = m["value"]
                        except Exception:
                            pass

                    source = mv.get("source", "")
                    models.append(ModelVersionItem(
                        name=rm.get("name", ""),
                        version=mv.get("version", "1"),
                        stage=mv.get("current_stage"),
                        description=mv.get("description"),
                        run_id=run_id,
                        artifact_uri=source,
                        framework=_detect_framework(mv),
                        metrics=metrics,
                        created_at=mv.get("creation_timestamp"),
                    ))
    except Exception as e:
        logger.warning("Failed to query MLflow at %s: %s", mlflow_url, e)

    return ModelListResponse(
        models=models,
        mlflow_available=True,
        kserve_available=kserve_available,
    )


@router.post(
    "/workspaces/{workspace_id}/models/deploy",
    response_model=ModelServingStatus,
)
async def deploy_model(
    workspace_id: int,
    req: ModelDeployRequest,
    session: AsyncSession = Depends(get_session),
):
    """Deploy a model version from MLflow as a KServe InferenceService."""
    import httpx
    from app.k8s.service import _make_client
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    # Load workspace
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.workspace_id == workspace_id,
        )
    )
    services = svc_result.scalars().all()

    if not _check_service_exists(services, "argus-mlflow"):
        raise HTTPException(status_code=400, detail="MLflow is not deployed in this workspace")
    if not _check_service_exists(services, "argus-kserve"):
        raise HTTPException(status_code=400, detail="KServe is not deployed in this workspace")

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"

    # Get MLflow model artifact URI — prefer external endpoint
    mlflow_svc = next(s for s in services if s.plugin_name == "argus-mlflow")
    mlflow_url = mlflow_svc.endpoint or (
        mlflow_svc.metadata_json or {}
    ).get("internal", {}).get("endpoint", "")

    artifact_uri = None
    framework = "mlflow"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{mlflow_url}/api/2.0/mlflow/model-versions/get",
                params={"name": req.model_name, "version": req.model_version},
            )
            if resp.status_code == 200:
                mv = resp.json().get("model_version", {})
                artifact_uri = mv.get("source")
                framework = _detect_framework(mv)
    except Exception as e:
        logger.warning("Failed to get model version from MLflow: %s", e)

    if not artifact_uri:
        raise HTTPException(
            status_code=404,
            detail=f"Model {req.model_name} v{req.model_version} not found in MLflow",
        )

    # Build KServe InferenceService manifest
    kserve_format = _FLAVOR_TO_KSERVE.get(framework, "mlflow")
    isvc_name = f"argus-model-{req.model_name}".lower().replace("_", "-")[:63]

    resource_requests = {"cpu": req.cpu, "memory": req.memory}
    resource_limits = {"cpu": req.cpu, "memory": req.memory}
    if req.gpu > 0:
        resource_requests["nvidia.com/gpu"] = str(req.gpu)
        resource_limits["nvidia.com/gpu"] = str(req.gpu)

    isvc_manifest = {
        "apiVersion": "serving.kserve.io/v1beta1",
        "kind": "InferenceService",
        "metadata": {
            "name": isvc_name,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/part-of": "argus-insight",
                "argus-insight/workspace": workspace.name,
            },
            "annotations": {
                "mlflow.org/model-name": req.model_name,
                "mlflow.org/model-version": req.model_version,
            },
        },
        "spec": {
            "predictor": {
                "minReplicas": req.min_replicas,
                "maxReplicas": req.max_replicas,
                "model": {
                    "modelFormat": {"name": kserve_format},
                    "storageUri": artifact_uri,
                    "resources": {
                        "requests": resource_requests,
                        "limits": resource_limits,
                    },
                },
            },
        },
    }

    # Apply via K8s API
    k8s = await _make_client(session)
    try:
        # Use CustomObjectsApi for CRD
        from kubernetes_asyncio import client as k8s_client
        await k8s._ensure_client()
        custom_api = k8s_client.CustomObjectsApi(k8s._api_client)

        try:
            # Try update first
            await custom_api.patch_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=isvc_name,
                body=isvc_manifest,
            )
        except Exception:
            # Create if not exists
            await custom_api.create_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                body=isvc_manifest,
            )
    finally:
        await k8s.close()

    endpoint = f"http://{isvc_name}.{namespace}.svc.cluster.local"

    return ModelServingStatus(
        model_name=req.model_name,
        model_version=req.model_version,
        endpoint=endpoint,
        status="Deploying",
        ready=False,
    )


@router.get(
    "/workspaces/{workspace_id}/models/{model_name}/serving",
    response_model=ModelServingStatus,
)
async def get_model_serving(
    workspace_id: int,
    model_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get serving status of a deployed model."""
    from app.k8s.service import _make_client
    from workspace_provisioner.models import ArgusWorkspace

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
    isvc_name = f"argus-model-{model_name}".lower().replace("_", "-")[:63]

    k8s = await _make_client(session)
    try:
        from kubernetes_asyncio import client as k8s_client
        await k8s._ensure_client()
        custom_api = k8s_client.CustomObjectsApi(k8s._api_client)

        try:
            isvc = await custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=isvc_name,
            )
        except Exception:
            return ModelServingStatus(model_name=model_name, status="Not deployed")
    finally:
        await k8s.close()

    conditions = isvc.get("status", {}).get("conditions", [])
    ready = any(
        c.get("type") == "Ready" and c.get("status") == "True"
        for c in conditions
    )
    url = isvc.get("status", {}).get("url", "")
    status = "Ready" if ready else "Deploying"

    annotations = isvc.get("metadata", {}).get("annotations", {})
    version = annotations.get("mlflow.org/model-version")

    return ModelServingStatus(
        model_name=model_name,
        model_version=version,
        endpoint=url or None,
        status=status,
        ready=ready,
    )


@router.delete("/workspaces/{workspace_id}/models/{model_name}/serving")
async def undeploy_model(
    workspace_id: int,
    model_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Undeploy a model (delete KServe InferenceService)."""
    from app.k8s.service import _make_client
    from workspace_provisioner.models import ArgusWorkspace

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
    isvc_name = f"argus-model-{model_name}".lower().replace("_", "-")[:63]

    k8s = await _make_client(session)
    try:
        from kubernetes_asyncio import client as k8s_client
        await k8s._ensure_client()
        custom_api = k8s_client.CustomObjectsApi(k8s._api_client)
        await custom_api.delete_namespaced_custom_object(
            group="serving.kserve.io",
            version="v1beta1",
            namespace=namespace,
            plural="inferenceservices",
            name=isvc_name,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Model serving not found: {e}")
    finally:
        await k8s.close()

    return {"ok": True}


# ---------------------------------------------------------------------------
# Workspace dashboard (aggregated, minimal K8s calls)
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/dashboard",
    response_model=WorkspaceDashboardResponse,
)
async def get_workspace_dashboard(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Aggregated workspace dashboard: pod health, PVC storage, recent activity.

    Makes exactly 2 K8s API calls (list pods + list PVCs) and 1 DB query.
    """
    from app.k8s.service import _make_client
    from workspace_provisioner.models import (
        ArgusWorkspace, ArgusWorkspaceAuditLog, ArgusWorkspaceService,
    )

    # 1. Load workspace + services from DB
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    svc_result = await session.execute(
        select(ArgusWorkspaceService)
        .where(ArgusWorkspaceService.workspace_id == workspace_id)
        .order_by(ArgusWorkspaceService.created_at)
    )
    db_services = svc_result.scalars().all()
    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"

    # 2. K8s: list pods + PVCs in namespace (2 API calls)
    k8s = await _make_client(session)
    try:
        pod_data, pvc_data = await asyncio.gather(
            k8s.list_resources("pods", namespace=namespace),
            k8s.list_resources("persistentvolumeclaims", namespace=namespace),
        )
    finally:
        await k8s.close()

    pods = pod_data.get("items", [])
    pvcs = pvc_data.get("items", [])

    # 3. Match pods to services
    health_items: list[ServiceHealthItem] = []
    matched_pod_names: set[str] = set()

    for svc in db_services:
        short = service._plugin_short_name(svc.plugin_name)
        matched_pod = None

        # Try service_id match first, then short name + workspace name
        for pod in pods:
            pname = pod["metadata"]["name"]
            if pname in matched_pod_names:
                continue
            if svc.service_id and svc.service_id in pname:
                matched_pod = pod
                break
            if pname.startswith(f"argus-{short}-{workspace.name}"):
                matched_pod = pod
                break

        if not matched_pod:
            continue

        matched_pod_names.add(matched_pod["metadata"]["name"])
        pod_status = matched_pod.get("status", {})
        phase = pod_status.get("phase", "Unknown")

        # Ready check
        conditions = pod_status.get("conditions", [])
        ready = any(
            c.get("type") == "Ready" and c.get("status") == "True"
            for c in conditions
        )

        # Restarts + uptime from container statuses
        restarts = 0
        uptime_seconds = None
        for cs in pod_status.get("containerStatuses", []):
            restarts += cs.get("restartCount", 0)
            started = cs.get("state", {}).get("running", {}).get("startedAt")
            if started:
                from datetime import datetime, timezone
                try:
                    start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    up = int((datetime.now(timezone.utc) - start_dt).total_seconds())
                    if uptime_seconds is None or up < uptime_seconds:
                        uptime_seconds = up
                except (ValueError, TypeError):
                    pass

        # Resource requests/limits from first container spec
        cpu_req = mem_req = cpu_lim = mem_lim = None
        containers = matched_pod.get("spec", {}).get("containers", [])
        if containers:
            res = containers[0].get("resources", {})
            cpu_req = res.get("requests", {}).get("cpu")
            mem_req = res.get("requests", {}).get("memory")
            cpu_lim = res.get("limits", {}).get("cpu")
            mem_lim = res.get("limits", {}).get("memory")

        health_items.append(ServiceHealthItem(
            plugin_name=svc.plugin_name,
            display_name=svc.display_name,
            pod_name=matched_pod["metadata"]["name"],
            phase=phase,
            ready=ready,
            restarts=restarts,
            uptime_seconds=uptime_seconds,
            cpu_request=cpu_req,
            memory_request=mem_req,
            cpu_limit=cpu_lim,
            memory_limit=mem_lim,
        ))

    # 4. PVC storage
    storage_items: list[StorageItem] = []
    for pvc in pvcs:
        pvc_name = pvc["metadata"]["name"]
        capacity = pvc.get("status", {}).get("capacity", {}).get("storage")
        pvc_phase = pvc.get("status", {}).get("phase", "Pending")

        # Derive service hint from PVC name (e.g., "argus-minio-ml-team-data" → "minio")
        hint = None
        for svc in db_services:
            short = service._plugin_short_name(svc.plugin_name)
            if short in pvc_name:
                hint = svc.display_name or svc.plugin_name
                break

        storage_items.append(StorageItem(
            name=pvc_name,
            capacity=capacity,
            phase=pvc_phase,
            service_hint=hint,
        ))

    # 5. Recent activity from audit logs (last 10, DB query only)
    from workspace_provisioner.models import ArgusWorkspaceAuditLog
    audit_result = await session.execute(
        select(ArgusWorkspaceAuditLog)
        .where(ArgusWorkspaceAuditLog.workspace_id == workspace_id)
        .order_by(ArgusWorkspaceAuditLog.created_at.desc())
        .limit(10)
    )
    activity_items = [
        ActivityItem(
            action=log.action,
            actor_username=log.actor_username,
            detail=log.detail,
            created_at=log.created_at,
        )
        for log in audit_result.scalars().all()
    ]

    # 6. Service counts
    total = len(db_services)
    running = sum(1 for h in health_items if h.phase == "Running" and h.ready)

    return WorkspaceDashboardResponse(
        service_health=health_items,
        storage=storage_items,
        recent_activity=activity_items,
        total_services=total,
        running_services=running,
    )


# ---------------------------------------------------------------------------
# Membership endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
)
async def add_member(
    workspace_id: int,
    req: WorkspaceMemberAddRequest,
    session: AsyncSession = Depends(get_session),
):
    """Add a member to a workspace."""
    logger.info("POST /workspaces/%d/members - user_id=%d, role=%s", workspace_id, req.user_id, req.role)
    ws = await service.get_workspace(session, workspace_id)
    if not ws:
        logger.error("POST /workspaces/%d/members - workspace not found", workspace_id)
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await service.add_member(session, workspace_id, req)


class BulkAddMembersRequest(BaseModel):
    user_ids: list[int]


@router.post(
    "/workspaces/{workspace_id}/members/bulk",
    response_model=list[WorkspaceMemberResponse],
)
async def bulk_add_members(
    workspace_id: int,
    req: BulkAddMembersRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Add multiple members to a workspace with GitLab provisioning.

    For each user:
    1. Check if GitLab user exists (argus-{username}), create if not.
    2. Add as project member (Maintainer level = all except delete repo).
    3. Create project access token.
    4. Add to workspace members.
    """
    import secrets
    from app.usermgr.models import ArgusUser
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember

    # Load workspace
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    results = []
    for user_id in req.user_ids:
        # Check if already a member
        existing = await session.execute(
            select(ArgusWorkspaceMember).where(
                ArgusWorkspaceMember.workspace_id == workspace_id,
                ArgusWorkspaceMember.user_id == user_id,
            )
        )
        if existing.scalars().first():
            continue

        # Load user info
        user_result = await session.execute(
            select(ArgusUser).where(ArgusUser.id == user_id)
        )
        user = user_result.scalars().first()
        if not user:
            continue

        gitlab_username = f"argus-{user.username}"
        gitlab_token = None
        token_name = None

        try:
            # Step 1: Ensure GitLab user exists
            gl_user = await gitlab_client.find_user(gitlab_username)
            if not gl_user:
                safe_password = secrets.token_urlsafe(12) + "!A1a"
                gl_user = await gitlab_client.create_user(
                    username=gitlab_username,
                    password=safe_password,
                    email=user.email or f"{gitlab_username}@argus.local",
                    name=f"{user.first_name} {user.last_name}".strip() or gitlab_username,
                )
                # Save gitlab credentials
                user.gitlab_username = gitlab_username
                user.gitlab_password = safe_password

            # Resolve GitLab project ID from workspace record or service metadata
            gl_project_id = ws.gitlab_project_id
            if not gl_project_id:
                from workspace_provisioner.models import ArgusWorkspaceService
                svc_result = await session.execute(
                    select(ArgusWorkspaceService).where(
                        ArgusWorkspaceService.workspace_id == workspace_id,
                        ArgusWorkspaceService.plugin_name == "argus-gitlab",
                    )
                )
                gl_svc = svc_result.scalars().first()
                if gl_svc and gl_svc.metadata_json:
                    internal = gl_svc.metadata_json.get("internal", gl_svc.metadata_json)
                    gl_project_id = internal.get("project_id")

            # Step 2: Add to project as Maintainer (all permissions except delete repo)
            if gl_project_id:
                await gitlab_client.add_project_member(
                    project_id=gl_project_id,
                    user_id=gl_user["id"],
                    access_level=40,  # Maintainer
                )

                # Step 3: Create project access token
                token_name = f"{gitlab_username}-{ws.name}"
                try:
                    token_info = await gitlab_client.create_project_access_token(
                        project_id=gl_project_id,
                        name=token_name,
                    )
                    gitlab_token = token_info["token"]
                except Exception as e:
                    logger.warning("Failed to create token for %s: %s", gitlab_username, e)

        except Exception as e:
            logger.warning("GitLab provisioning failed for user %d: %s", user_id, e)

        # Step 4: MinIO user creation + workspace bucket access
        minio_provisioned = False
        try:
            from app.settings.service import get_config_by_category
            cfg = await get_config_by_category(session, "argus")
            minio_endpoint = cfg.get("object_storage_endpoint", "")
            minio_access = cfg.get("object_storage_access_key", "")
            minio_secret = cfg.get("object_storage_secret_key", "")
            minio_ssl = cfg.get("object_storage_use_ssl", "false").lower() == "true"

            if minio_endpoint and minio_access and minio_secret:
                from workspace_provisioner.minio.client import MinioAdminClient
                from workspace_provisioner.config import MinioWorkspaceConfig

                ws_config_cfg = await get_config_by_category(session, "deploy_mapping")
                bucket_prefix = "workspace-"  # default
                minio_ep = minio_endpoint.replace("http://", "").replace("https://", "")
                minio_client = MinioAdminClient(
                    endpoint=minio_ep,
                    root_user=minio_access,
                    root_password=minio_secret,
                    secure=minio_ssl,
                )

                bucket_name = f"{bucket_prefix}{ws.name}"
                minio_username = f"user-{user.username}"

                # Create MinIO user (idempotent - returns created=False if exists)
                user_secret = secrets.token_urlsafe(16)
                user_info = await minio_client.create_user(minio_username, user_secret)

                # Set bucket policy for workspace bucket
                await minio_client.set_user_bucket_policy(minio_username, bucket_name)

                # Save S3 credentials if this is a new user
                if user_info.get("created") and not user.s3_access_key:
                    user.s3_access_key = minio_username
                    user.s3_secret_key = user_secret
                    user.s3_bucket = bucket_name

                minio_provisioned = True
                logger.info(
                    "MinIO access granted for member %s: user=%s bucket=%s",
                    user.username, minio_username, bucket_name,
                )
        except Exception as e:
            logger.warning("MinIO provisioning failed for user %d: %s", user_id, e)

        # Step 5: Add workspace member
        member = ArgusWorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role="User",
            gitlab_access_token=gitlab_token,
            gitlab_token_name=token_name,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        resp = await service._build_member_response(session, member, ws.created_by)
        results.append(resp)

        # Audit log
        await service.log_audit(
            session, workspace_id, ws.name, "member_added",
            actor_user_id=int(current_user.sub), actor_username=current_user.username,
            target_user_id=user_id, target_username=user.username,
            detail={
                "role": "User",
                "gitlab_provisioned": gitlab_token is not None,
                "minio_provisioned": minio_provisioned,
            },
        )

    logger.info("Bulk added %d members to workspace %d", len(results), workspace_id)
    return results


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
async def list_members(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
):
    """List all members of a workspace."""
    logger.info("GET /workspaces/%d/members", workspace_id)
    return await service.list_members(session, workspace_id)


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
async def remove_member(
    workspace_id: int,
    member_id: int,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
    gitlab_client: GitLabClient = Depends(_get_gitlab_client),
):
    """Remove a member from a workspace and GitLab project."""
    from app.usermgr.models import ArgusUser
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember

    logger.info("DELETE /workspaces/%d/members/%d", workspace_id, member_id)

    # Load member
    member_result = await session.execute(
        select(ArgusWorkspaceMember).where(ArgusWorkspaceMember.id == member_id)
    )
    member = member_result.scalars().first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent removing workspace owner
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if ws and ws.created_by == member.user_id:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

    # Load user info
    user_result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == member.user_id)
    )
    user = user_result.scalars().first()

    # Resolve GitLab project ID (workspace record or service metadata)
    gl_project_id = ws.gitlab_project_id if ws else None
    if not gl_project_id and ws:
        from workspace_provisioner.models import ArgusWorkspaceService
        svc_result = await session.execute(
            select(ArgusWorkspaceService).where(
                ArgusWorkspaceService.workspace_id == workspace_id,
                ArgusWorkspaceService.plugin_name == "argus-gitlab",
            )
        )
        gl_svc = svc_result.scalars().first()
        if gl_svc and gl_svc.metadata_json:
            internal = gl_svc.metadata_json.get("internal", gl_svc.metadata_json)
            gl_project_id = internal.get("project_id")

    # Remove from GitLab project
    if gl_project_id and user:
        gitlab_username = f"argus-{user.username}"
        try:
            gl_user = await gitlab_client.find_user(gitlab_username)
            if gl_user:
                await gitlab_client.remove_project_member(
                    project_id=gl_project_id,
                    user_id=gl_user["id"],
                )
        except Exception as e:
            logger.warning("Failed to remove GitLab member: %s", e)

    # Remove from workspace
    if not await service.remove_member(session, member_id):
        raise HTTPException(status_code=404, detail="Member not found")

    # Audit log
    await service.log_audit(
        session, workspace_id, ws.name, "member_removed",
        actor_user_id=int(current_user.sub), actor_username=current_user.username,
        target_user_id=member.user_id, target_username=user.username if user else None,
        detail={"gitlab_removed": gl_project_id is not None},
    )

    logger.info("DELETE /workspaces/%d/members/%d - removed (with GitLab)", workspace_id, member_id)
    return {"status": "ok", "message": "Member removed"}


# ---------------------------------------------------------------------------
# Audit log endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/workspaces/{workspace_id}/audit-logs",
    response_model=PaginatedAuditLogResponse,
)
async def get_workspace_audit_logs(
    workspace_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get audit logs for a specific workspace."""
    from sqlalchemy import func as sqlfunc
    from workspace_provisioner.models import ArgusWorkspaceAuditLog

    base = select(ArgusWorkspaceAuditLog).where(
        ArgusWorkspaceAuditLog.workspace_id == workspace_id
    )
    count_q = select(sqlfunc.count()).select_from(base.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(ArgusWorkspaceAuditLog.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    logs = result.scalars().all()

    return PaginatedAuditLogResponse(
        items=[
            AuditLogResponse(
                id=l.id, workspace_id=l.workspace_id, workspace_name=l.workspace_name,
                action=l.action, target_user_id=l.target_user_id,
                target_username=l.target_username, actor_user_id=l.actor_user_id,
                actor_username=l.actor_username, detail=l.detail,
                created_at=l.created_at,
            ) for l in logs
        ],
        total=total, page=page, page_size=page_size,
    )


# =========================================================================== #
# Service Configuration (runtime config change)
# =========================================================================== #

POSTGRESQL_ALLOWED_OPTIONS = {
    "max_connections", "shared_buffers", "work_mem", "maintenance_work_mem",
    "effective_cache_size", "wal_buffers", "checkpoint_completion_target",
    "random_page_cost", "effective_io_concurrency",
    "log_min_duration_statement", "log_statement",
    "temp_buffers", "default_statistics_target",
}

POSTGRESQL_BLOCKED_OPTIONS = {
    "port", "data_directory", "hba_file", "ident_file",
    "listen_addresses", "unix_socket_directories",
    "ssl", "ssl_cert_file", "ssl_key_file",
    "password_encryption", "wal_level", "archive_mode",
}

JUPYTER_ALLOWED_OPTIONS = {
    "ServerApp.max_body_size", "ServerApp.max_buffer_size",
    "ServerApp.shutdown_no_activity_timeout", "ServerApp.terminals_enabled",
    "MappingKernelManager.cull_idle_timeout", "MappingKernelManager.cull_interval",
    "MappingKernelManager.cull_connected", "MappingKernelManager.default_kernel_name",
    "ContentsManager.allow_hidden",
}

JUPYTER_BLOCKED_OPTIONS = {
    "ServerApp.port", "ServerApp.ip", "ServerApp.root_dir",
    "ServerApp.base_url", "ServerApp.certfile", "ServerApp.keyfile",
    "ServerApp.open_browser", "ServerApp.allow_remote_access",
    "ServerApp.token", "ServerApp.password",
}

MLFLOW_ALLOWED_OPTIONS = {
    "MLFLOW_WORKERS", "GUNICORN_CMD_ARGS",
    "MLFLOW_LOGGING_LEVEL", "MLFLOW_SERVE_ARTIFACTS",
}

MLFLOW_BLOCKED_OPTIONS = {
    "MLFLOW_TRACKING_URI", "MLFLOW_BACKEND_STORE_URI",
    "MLFLOW_DEFAULT_ARTIFACT_ROOT", "MLFLOW_S3_ENDPOINT_URL",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
}

AIRFLOW_ALLOWED_OPTIONS = {
    # core
    "AIRFLOW__CORE__PARALLELISM", "AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG",
    "AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG", "AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION",
    "AIRFLOW__CORE__DEFAULT_TIMEZONE", "AIRFLOW__CORE__DAG_FILE_PROCESSOR_TIMEOUT",
    # scheduler
    "AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL", "AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL",
    "AIRFLOW__SCHEDULER__PARSING_PROCESSES", "AIRFLOW__SCHEDULER__SCHEDULER_HEARTBEAT_SEC",
    # webserver
    "AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_TIMEOUT", "AIRFLOW__WEBSERVER__DEFAULT_UI_TIMEZONE",
    "AIRFLOW__WEBSERVER__HIDE_PAUSED_DAGS_BY_DEFAULT", "AIRFLOW__WEBSERVER__PAGE_SIZE",
    "AIRFLOW__WEBSERVER__DEFAULT_DAG_RUN_DISPLAY_NUMBER", "AIRFLOW__WEBSERVER__WORKERS",
    # logging
    "AIRFLOW__LOGGING__LOGGING_LEVEL", "AIRFLOW__LOGGING__FAB_LOGGING_LEVEL",
    # smtp
    "AIRFLOW__SMTP__SMTP_HOST", "AIRFLOW__SMTP__SMTP_PORT",
    "AIRFLOW__SMTP__SMTP_STARTTLS", "AIRFLOW__SMTP__SMTP_SSL",
    "AIRFLOW__SMTP__SMTP_USER", "AIRFLOW__SMTP__SMTP_PASSWORD",
    "AIRFLOW__SMTP__SMTP_MAIL_FROM",
}

AIRFLOW_BLOCKED_OPTIONS = {
    "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", "AIRFLOW__CORE__FERNET_KEY",
    "AIRFLOW__WEBSERVER__SECRET_KEY", "AIRFLOW__WEBSERVER__BASE_URL",
    "AIRFLOW__WEBSERVER__WEB_SERVER_PORT", "AIRFLOW__CORE__DAGS_FOLDER",
}

MARIADB_ALLOWED_OPTIONS = {
    "max_connections", "wait_timeout", "interactive_timeout", "connect_timeout",
    "max_allowed_packet", "thread_cache_size",
    "innodb_buffer_pool_size", "innodb_log_file_size", "innodb_flush_log_at_trx_commit",
    "innodb_file_per_table", "tmp_table_size", "max_heap_table_size",
    "sort_buffer_size", "join_buffer_size",
    "slow_query_log", "long_query_time",
    "character_set_server", "collation_server",
}

MARIADB_BLOCKED_OPTIONS = {
    "port", "socket", "datadir", "pid_file", "log_bin", "server_id",
    "bind_address", "skip_networking", "skip_grant_tables",
    "plugin_load", "secure_file_priv", "basedir", "tmpdir",
}


class ServiceConfigUpdateRequest(BaseModel):
    options: dict[str, str]


@router.get("/workspaces/{workspace_id}/services/{service_id}/config")
async def get_service_config(
    workspace_id: int,
    service_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get the runtime configuration for a deployed service."""
    import asyncio
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(ArgusWorkspaceService.id == service_id)
    )
    svc = svc_result.scalars().first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    namespace = ws.k8s_namespace or f"argus-ws-{ws.name}"

    if svc.plugin_name == "argus-mariadb":
        configmap_name = f"argus-mariadb-{ws.name}-custom-config"
        cmd = ["kubectl", "get", "configmap", configmap_name, "-n", namespace, "-o", "jsonpath={.data.custom\\.cnf}"]
        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"plugin_name": svc.plugin_name, "options": {}, "allowed_options": list(MARIADB_ALLOWED_OPTIONS)}

        # Parse custom.cnf
        options = {}
        for line in stdout.decode().splitlines():
            line = line.strip()
            if not line or line.startswith("[") or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                options[key.strip()] = val.strip()

        return {
            "plugin_name": svc.plugin_name,
            "options": options,
            "allowed_options": sorted(MARIADB_ALLOWED_OPTIONS),
        }

    if svc.plugin_name == "argus-postgresql":
        configmap_name = f"argus-postgresql-{ws.name}-custom-config"
        cmd = ["kubectl", "get", "configmap", configmap_name, "-n", namespace, "-o", "jsonpath={.data.custom\\.conf}"]
        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"plugin_name": svc.plugin_name, "options": {}, "allowed_options": list(POSTGRESQL_ALLOWED_OPTIONS)}

        options = {}
        for line in stdout.decode().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                options[key.strip()] = val.strip()

        return {
            "plugin_name": svc.plugin_name,
            "options": options,
            "allowed_options": sorted(POSTGRESQL_ALLOWED_OPTIONS),
        }

    if svc.plugin_name.startswith("argus-jupyter"):
        # Jupyter uses INSTANCE_ID (service_id) in ConfigMap name
        svc_service_id = svc.service_id or ""
        configmap_name = f"argus-jupyter-{svc_service_id}-custom-config"
        cmd = ["kubectl", "get", "configmap", configmap_name, "-n", namespace, "-o", "jsonpath={.data.custom_config\\.py}"]
        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"plugin_name": svc.plugin_name, "options": {}, "allowed_options": list(JUPYTER_ALLOWED_OPTIONS)}

        # Parse Python config: c.Class.option = value
        options = {}
        for line in stdout.decode().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("c.") and "=" in line:
                key = line.split("=", 1)[0].strip().replace("c.", "")
                val = line.split("=", 1)[1].strip()
                # Remove quotes from string values
                if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                    val = val[1:-1]
                options[key] = val

        return {
            "plugin_name": svc.plugin_name,
            "options": options,
            "allowed_options": sorted(JUPYTER_ALLOWED_OPTIONS),
        }

    if svc.plugin_name == "argus-mlflow":
        configmap_name = f"argus-mlflow-{ws.name}-custom-config"
        cmd = ["kubectl", "get", "configmap", configmap_name, "-n", namespace, "-o", "json"]
        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"plugin_name": svc.plugin_name, "options": {}, "allowed_options": sorted(MLFLOW_ALLOWED_OPTIONS)}

        import json as _json
        cm = _json.loads(stdout.decode())
        options = {k: v for k, v in cm.get("data", {}).items() if k in MLFLOW_ALLOWED_OPTIONS}

        return {
            "plugin_name": svc.plugin_name,
            "options": options,
            "allowed_options": sorted(MLFLOW_ALLOWED_OPTIONS),
        }

    if svc.plugin_name == "argus-airflow":
        configmap_name = f"argus-airflow-{ws.name}-custom-config"
        cmd = ["kubectl", "get", "configmap", configmap_name, "-n", namespace, "-o", "json"]
        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"plugin_name": svc.plugin_name, "options": {}, "allowed_options": sorted(AIRFLOW_ALLOWED_OPTIONS)}

        import json as _json
        cm = _json.loads(stdout.decode())
        options = {k: v for k, v in cm.get("data", {}).items() if k in AIRFLOW_ALLOWED_OPTIONS}

        return {
            "plugin_name": svc.plugin_name,
            "options": options,
            "allowed_options": sorted(AIRFLOW_ALLOWED_OPTIONS),
        }

    return {"plugin_name": svc.plugin_name, "options": {}, "allowed_options": []}


@router.put("/workspaces/{workspace_id}/services/{service_id}/config")
async def update_service_config(
    workspace_id: int,
    service_id: int,
    body: ServiceConfigUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update runtime configuration for a deployed service and restart."""
    import asyncio
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceService

    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(ArgusWorkspaceService.id == service_id)
    )
    svc = svc_result.scalars().first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    namespace = ws.k8s_namespace or f"argus-ws-{ws.name}"

    if svc.plugin_name == "argus-mariadb":
        # Validate options
        for key in body.options:
            if key in MARIADB_BLOCKED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Option '{key}' cannot be changed")
            if key not in MARIADB_ALLOWED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Unknown option '{key}'")

        # Build custom.cnf content
        lines = ["[mysqld]"]
        for key, val in body.options.items():
            lines.append(f"{key} = {val}")
        cnf_content = "\n".join(lines) + "\n"

        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")

        configmap_name = f"argus-mariadb-{ws.name}-custom-config"

        # Update ConfigMap via kubectl patch
        import json as _json
        patch = _json.dumps({"data": {"custom.cnf": cnf_content}})
        cmd = ["kubectl", "patch", "configmap", configmap_name, "-n", namespace, "--type=merge", f"-p={patch}"]
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {stderr.decode()}")

        # Restart StatefulSet
        cmd2 = ["kubectl", "rollout", "restart", f"statefulset/argus-mariadb-{ws.name}", "-n", namespace]
        if kubeconfig:
            cmd2.insert(1, f"--kubeconfig={kubeconfig}")

        proc2 = await asyncio.create_subprocess_exec(
            *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        logger.info("MariaDB config updated for workspace %s, restarting", ws.name)
        return {"status": "ok", "message": "Configuration updated. MariaDB is restarting."}

    if svc.plugin_name == "argus-postgresql":
        for key in body.options:
            if key in POSTGRESQL_BLOCKED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Option '{key}' cannot be changed")
            if key not in POSTGRESQL_ALLOWED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Unknown option '{key}'")

        lines = []
        for key, val in body.options.items():
            lines.append(f"{key} = {val}")
        conf_content = "\n".join(lines) + "\n"

        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")

        configmap_name = f"argus-postgresql-{ws.name}-custom-config"

        import json as _json
        patch = _json.dumps({"data": {"custom.conf": conf_content}})
        cmd = ["kubectl", "patch", "configmap", configmap_name, "-n", namespace, "--type=merge", f"-p={patch}"]
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {stderr.decode()}")

        cmd2 = ["kubectl", "rollout", "restart", f"statefulset/argus-postgresql-{ws.name}", "-n", namespace]
        if kubeconfig:
            cmd2.insert(1, f"--kubeconfig={kubeconfig}")

        proc2 = await asyncio.create_subprocess_exec(
            *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        logger.info("PostgreSQL config updated for workspace %s, restarting", ws.name)
        return {"status": "ok", "message": "Configuration updated. PostgreSQL is restarting."}

    if svc.plugin_name.startswith("argus-jupyter"):
        for key in body.options:
            if key in JUPYTER_BLOCKED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Option '{key}' cannot be changed")
            if key not in JUPYTER_ALLOWED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Unknown option '{key}'")

        # Build Python config
        lines = []
        for key, val in body.options.items():
            # Determine value type
            if val in ("True", "False"):
                lines.append(f"c.{key} = {val}")
            elif val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
                lines.append(f"c.{key} = {val}")
            else:
                lines.append(f"c.{key} = '{val}'")
        conf_content = "\n".join(lines) + "\n"

        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")

        svc_service_id = svc.service_id or ""
        configmap_name = f"argus-jupyter-{svc_service_id}-custom-config"

        import json as _json
        patch = _json.dumps({"data": {"custom_config.py": conf_content}})
        cmd = ["kubectl", "patch", "configmap", configmap_name, "-n", namespace, "--type=merge", f"-p={patch}"]
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {stderr.decode()}")

        # Restart Deployment
        cmd2 = ["kubectl", "rollout", "restart", f"deployment/argus-jupyter-{svc_service_id}", "-n", namespace]
        if kubeconfig:
            cmd2.insert(1, f"--kubeconfig={kubeconfig}")

        proc2 = await asyncio.create_subprocess_exec(
            *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        logger.info("JupyterLab config updated for service %s, restarting", svc_service_id)
        return {"status": "ok", "message": "Configuration updated. JupyterLab is restarting."}

    if svc.plugin_name == "argus-mlflow":
        for key in body.options:
            if key in MLFLOW_BLOCKED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Option '{key}' cannot be changed")
            if key not in MLFLOW_ALLOWED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Unknown option '{key}'")

        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")

        configmap_name = f"argus-mlflow-{ws.name}-custom-config"

        import json as _json
        patch = _json.dumps({"data": body.options})
        cmd = ["kubectl", "patch", "configmap", configmap_name, "-n", namespace, "--type=merge", f"-p={patch}"]
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {stderr.decode()}")

        cmd2 = ["kubectl", "rollout", "restart", f"statefulset/argus-mlflow-{ws.name}", "-n", namespace]
        if kubeconfig:
            cmd2.insert(1, f"--kubeconfig={kubeconfig}")

        proc2 = await asyncio.create_subprocess_exec(
            *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        logger.info("MLflow config updated for workspace %s, restarting", ws.name)
        return {"status": "ok", "message": "Configuration updated. MLflow is restarting."}

    if svc.plugin_name == "argus-airflow":
        for key in body.options:
            if key in AIRFLOW_BLOCKED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Option '{key}' cannot be changed")
            if key not in AIRFLOW_ALLOWED_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Unknown option '{key}'")

        from app.settings.service import get_config_by_category
        cfg = await get_config_by_category(session, "k8s")
        kubeconfig = cfg.get("k8s_kubeconfig_path", "")

        configmap_name = f"argus-airflow-{ws.name}-custom-config"

        import json as _json
        patch = _json.dumps({"data": body.options})
        cmd = ["kubectl", "patch", "configmap", configmap_name, "-n", namespace, "--type=merge", f"-p={patch}"]
        if kubeconfig:
            cmd.insert(1, f"--kubeconfig={kubeconfig}")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to update config: {stderr.decode()}")

        cmd2 = ["kubectl", "rollout", "restart", f"statefulset/argus-airflow-{ws.name}", "-n", namespace]
        if kubeconfig:
            cmd2.insert(1, f"--kubeconfig={kubeconfig}")

        proc2 = await asyncio.create_subprocess_exec(
            *cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc2.communicate()

        logger.info("Airflow config updated for workspace %s, restarting", ws.name)
        return {"status": "ok", "message": "Configuration updated. Airflow is restarting."}

    raise HTTPException(status_code=400, detail=f"Configuration not supported for {svc.plugin_name}")
