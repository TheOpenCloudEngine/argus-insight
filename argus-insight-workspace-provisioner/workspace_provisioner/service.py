"""Workspace provisioning service.

Business logic for workspace CRUD and provisioning workflow orchestration.
This service is called by the router and coordinates between the database
models and the workflow engine.
"""

import asyncio
import logging
import secrets
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.models import (
    ArgusWorkspace,
    ArgusWorkspaceAuditLog,
    ArgusWorkspaceCredential,
    ArgusWorkspaceMember,
    ArgusWorkspaceService,
)
from workspace_provisioner.schemas import (
    PaginatedWorkspaceResponse,
    WorkspaceCredentialResponse,
    WorkspaceDeleteRequest,
    WorkspaceMemberAddRequest,
    WorkspaceMemberResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceStatus,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowExecutor
from workspace_provisioner.plugins.registry import PluginRegistry
from workspace_provisioner.workflow.steps.gitlab_create_project import (
    GitLabCreateProjectStep,
)

logger = logging.getLogger(__name__)


def generate_service_id() -> str:
    """Generate a unique service ID for hostname security.

    Format: 8-char hex timestamp + 4-char random hex = 12 chars.
    Example: "67e8a400a3f1"
    """
    ts_hex = f"{int(time.time()):08x}"
    rand_hex = secrets.token_hex(2)
    return f"{ts_hex}{rand_hex}"


async def log_audit(
    session: AsyncSession,
    workspace_id: int,
    workspace_name: str,
    action: str,
    actor_user_id: int | None = None,
    actor_username: str | None = None,
    target_user_id: int | None = None,
    target_username: str | None = None,
    detail: dict | None = None,
) -> None:
    """Write a workspace audit log entry."""
    entry = ArgusWorkspaceAuditLog(
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        action=action,
        target_user_id=target_user_id,
        target_username=target_username,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        detail=detail,
    )
    session.add(entry)
    await session.commit()
    logger.info("Audit: workspace=%s action=%s actor=%s target=%s",
                workspace_name, action, actor_username, target_username)


# Plugins that support multiple instances per workspace.
MULTI_INSTANCE_PLUGINS = {
    "argus-vscode-server",
    "argus-jupyter", "argus-jupyter-tensorflow", "argus-jupyter-pyspark",
    "argus-rstudio",
    "argus-langserve",
}


async def register_workspace_service(
    workspace_id: int,
    plugin_name: str,
    display_name: str | None = None,
    version: str | None = None,
    endpoint: str | None = None,
    username: str | None = None,
    password: str | None = None,
    access_token: str | None = None,
    status: str = "running",
    metadata: dict | None = None,
    service_id: str | None = None,
) -> None:
    """Register or update a service deployed to a workspace.

    Multi-instance plugins (vscode, jupyter*) always INSERT a new record.
    Single-instance plugins upsert by (workspace_id, plugin_name).

    Raises RuntimeError if the workspace's resource profile quota would be exceeded.
    """
    from app.core.database import async_session as get_async_session

    async with get_async_session() as session:
        # Quota check: if metadata contains resources, verify against profile limits
        if metadata and metadata.get("resources"):
            res = metadata["resources"]
            cpu_limit = res.get("cpu_limit", "0")
            memory_limit = res.get("memory_limit", "0")
            from app.resource_profile.service import check_resource_quota
            allowed, details = await check_resource_quota(
                session, workspace_id, cpu_limit, memory_limit,
            )
            if not allowed:
                raise RuntimeError(
                    f"Resource quota exceeded for workspace {workspace_id}: {details}"
                )

        is_multi = plugin_name in MULTI_INSTANCE_PLUGINS

        if not is_multi:
            # Single-instance: upsert by (workspace_id, plugin_name)
            result = await session.execute(
                select(ArgusWorkspaceService).where(
                    ArgusWorkspaceService.workspace_id == workspace_id,
                    ArgusWorkspaceService.plugin_name == plugin_name,
                )
            )
            svc = result.scalars().first()
            if svc:
                if display_name: svc.display_name = display_name
                if version: svc.version = version
                if endpoint: svc.endpoint = endpoint
                if username: svc.username = username
                if password: svc.password = password
                if access_token: svc.access_token = access_token
                if service_id: svc.service_id = service_id
                svc.status = status
                if metadata: svc.metadata_json = metadata
                await session.commit()
                logger.info("Service updated: workspace=%d plugin=%s service_id=%s",
                             workspace_id, plugin_name, service_id)
                return

        # Multi-instance or new single-instance: always INSERT
        svc = ArgusWorkspaceService(
            workspace_id=workspace_id,
            plugin_name=plugin_name,
            service_id=service_id,
            display_name=display_name,
            version=version,
            endpoint=endpoint,
            username=username,
            password=password,
            access_token=access_token,
            status=status,
            metadata_json=metadata,
        )
        session.add(svc)
        await session.commit()
        logger.info("Service registered: workspace=%d plugin=%s service_id=%s endpoint=%s",
                     workspace_id, plugin_name, service_id, endpoint)

        # Audit log
        ws_result = await session.execute(
            select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
        )
        ws = ws_result.scalars().first()
        if ws:
            entry = ArgusWorkspaceAuditLog(
                workspace_id=workspace_id,
                workspace_name=ws.name,
                action="service_added",
                detail={
                    "plugin_name": plugin_name,
                    "display_name": display_name,
                    "endpoint": endpoint,
                    "service_id": service_id,
                    "version": version,
                },
            )
            session.add(entry)
            await session.commit()


# Plugins that should not be deleted individually from the Resources tab.
NON_DELETABLE_PLUGINS = {"argus-gitlab", "argus-minio-workspace"}


async def delete_workspace_service_with_teardown(
    session: AsyncSession,
    workspace_id: int,
    service_db_id: int,
    actor_user_id: int | None = None,
    actor_username: str | None = None,
) -> None:
    """Delete a workspace service: teardown K8s resources, remove DNS, delete DB record, audit log.

    Steps:
        1. Load service and workspace from DB.
        2. Instantiate the plugin's WorkflowStep via PluginRegistry.
        3. Build a WorkflowContext for teardown.
        4. Call step.teardown(ctx) to delete K8s resources.
        5. Delete DNS record (best-effort).
        6. Delete DB record.
        7. Write audit log.
    """
    from urllib.parse import urlparse

    from workspace_provisioner.models import ArgusWorkspace
    from workspace_provisioner.plugins.registry import PluginRegistry
    from workspace_provisioner.workflow.engine import WorkflowContext
    from workspace_provisioner.workflow.steps.app_deploy import delete_app_dns

    # 1. Load service record
    result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.id == service_db_id,
            ArgusWorkspaceService.workspace_id == workspace_id,
        )
    )
    svc = result.scalars().first()
    if not svc:
        raise ValueError("Service not found")

    if svc.plugin_name in NON_DELETABLE_PLUGINS:
        raise ValueError(f"Plugin '{svc.plugin_name}' cannot be deleted individually")

    # Load workspace
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = ws_result.scalars().first()
    if not ws:
        raise ValueError("Workspace not found")

    # 2. Instantiate the workflow step
    registry = PluginRegistry.get_instance()
    step = None
    try:
        step = registry.instantiate_step(svc.plugin_name)
    except Exception:
        # For gitlab step which needs a client, or unknown plugins
        logger.warning(
            "Could not instantiate step for plugin '%s', will skip K8s teardown",
            svc.plugin_name,
        )

    # 3. Build WorkflowContext with service_id for teardown
    ctx = WorkflowContext(
        workspace_id=ws.id,
        workspace_name=ws.name,
        domain=ws.domain,
    )
    ctx.set("k8s_namespace", ws.k8s_namespace or f"argus-ws-{ws.name}")
    if svc.service_id:
        ctx.set("teardown_service_id", svc.service_id)

    # 4. Teardown K8s resources
    if step:
        try:
            await step.teardown(ctx)
            logger.info(
                "K8s teardown completed for service '%s' (plugin=%s) in workspace '%s'",
                svc.display_name, svc.plugin_name, ws.name,
            )
        except Exception as e:
            logger.error(
                "K8s teardown failed for service '%s' (plugin=%s): %s",
                svc.display_name, svc.plugin_name, e,
            )
            raise RuntimeError(
                f"Failed to teardown K8s resources for {svc.display_name}: {e}"
            ) from e

    # 5. Delete DNS record (best-effort)
    if svc.endpoint:
        try:
            parsed = urlparse(svc.endpoint)
            hostname = parsed.hostname or svc.endpoint
            await delete_app_dns(session, hostname)
            logger.info("DNS deleted for hostname '%s'", hostname)
        except Exception as e:
            logger.warning("DNS deletion failed for '%s': %s (continuing)", svc.endpoint, e)

    # Save details before deleting
    detail = {
        "plugin_name": svc.plugin_name,
        "display_name": svc.display_name,
        "endpoint": svc.endpoint,
        "service_id": svc.service_id,
        "version": svc.version,
    }

    # 6. Delete DB record
    await session.delete(svc)
    await session.flush()

    # 7. Audit log
    await log_audit(
        session, workspace_id, ws.name,
        action="service_deleted",
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        detail=detail,
    )


async def _build_workspace_response(ws: ArgusWorkspace, session: AsyncSession | None = None) -> WorkspaceResponse:
    username = None
    if session and ws.created_by:
        from app.usermgr.models import ArgusUser
        result = await session.execute(
            select(ArgusUser.username).where(ArgusUser.id == ws.created_by)
        )
        username = result.scalar()
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        display_name=ws.display_name,
        description=ws.description,
        domain=ws.domain,
        k8s_cluster=ws.k8s_cluster,
        k8s_namespace=ws.k8s_namespace,
        gitlab_project_id=ws.gitlab_project_id,
        gitlab_project_url=ws.gitlab_project_url,
        minio_endpoint=ws.minio_endpoint,
        minio_console_endpoint=ws.minio_console_endpoint,
        minio_default_bucket=ws.minio_default_bucket,
        airflow_endpoint=ws.airflow_endpoint,
        mlflow_endpoint=ws.mlflow_endpoint,
        kserve_endpoint=ws.kserve_endpoint,
        status=WorkspaceStatus(ws.status),
        created_by=ws.created_by,
        created_by_username=username,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


async def create_workspace(
    session: AsyncSession,
    req: WorkspaceCreateRequest,
    gitlab_client: GitLabClient,
) -> WorkspaceResponse:
    """Create a workspace record and launch the provisioning workflow.

    The workspace is created with status "provisioning". The workflow runs
    asynchronously in the background, updating the workspace status to
    "active" on success or "failed" on error.

    Args:
        session: Active database session.
        req: Validated workspace creation request.
        gitlab_client: Authenticated GitLab client for project creation.

    Returns:
        The newly created workspace (status will be "provisioning").

    Raises:
        ValueError: If the workspace name already exists.
    """
    logger.info("Creating workspace: name=%s, domain=%s, admin_user_id=%d", req.name, req.domain, req.admin_user_id)

    # Check uniqueness
    existing = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.name == req.name)
    )
    if existing.scalars().first():
        logger.error("Workspace creation failed: name '%s' already exists", req.name)
        raise ValueError(f"Workspace '{req.name}' already exists")

    # Resolve default resource profile
    default_profile_id = None
    try:
        from app.resource_profile.service import get_default_profile_id
        default_profile_id = await get_default_profile_id(session)
    except Exception:
        pass

    # Create workspace record
    workspace = ArgusWorkspace(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        domain=req.domain,
        k8s_cluster=req.k8s_cluster,
        k8s_namespace=req.k8s_namespace or f"argus-ws-{req.name}",
        status=WorkspaceStatus.PROVISIONING.value,
        resource_profile_id=default_profile_id,
        created_by=req.admin_user_id,
    )
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    logger.info("Workspace created: %s (id=%d, profile=%s)", workspace.name, workspace.id, default_profile_id)

    # Add creator as WorkspaceAdmin
    member = ArgusWorkspaceMember(
        workspace_id=workspace.id,
        user_id=req.admin_user_id,
        role="WorkspaceAdmin",
    )
    session.add(member)

    # Associate pipelines
    from workspace_provisioner.models import ArgusWorkspacePipeline
    for i, pipeline_id in enumerate(req.pipeline_ids):
        ws_pipeline = ArgusWorkspacePipeline(
            workspace_id=workspace.id,
            pipeline_id=pipeline_id,
            deploy_order=i,
            status="pending",
        )
        session.add(ws_pipeline)

    # Load creator info for GitLab user provisioning
    from app.usermgr.models import ArgusUser
    creator_result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == req.admin_user_id)
    )
    creator = creator_result.scalars().first()
    creator_info = {}
    if creator:
        # Load GitLab default password from settings
        from app.settings.service import get_config_by_category
        gitlab_cfg = await get_config_by_category(session, "gitlab")
        gitlab_password = gitlab_cfg.get("gitlab_password", "")

        creator_info = {
            "creator_username": creator.username,
            "creator_email": creator.email,
            "creator_name": f"{creator.first_name} {creator.last_name}".strip() or creator.username,
            "creator_password": gitlab_password or "Argus!nsight2026",
            "admin_user_id": req.admin_user_id,
        }

    await session.commit()

    # Audit log
    await log_audit(
        session, workspace.id, workspace.name, "workspace_created",
        actor_user_id=req.admin_user_id,
        actor_username=creator_info.get("creator_username"),
        detail={"pipeline_ids": req.pipeline_ids},
    )

    # Launch provisioning workflow in background
    logger.info("Launching provisioning workflow in background for workspace %d", workspace.id)
    asyncio.create_task(
        _run_provisioning_workflow(workspace.id, req, gitlab_client, creator_info)
    )

    return await _build_workspace_response(workspace, session)



async def _build_plugin_workflow(
    session: "AsyncSession",
    executor: WorkflowExecutor,
    req: "WorkspaceCreateRequest",
    gitlab_client: GitLabClient,
) -> WorkflowContext:
    """Build the workflow pipeline from plugin registry and admin configuration.

    Resolves plugin order from DB (admin-configured), validates dependencies,
    instantiates step classes, and builds the workflow context with plugin configs.
    """
    from workspace_provisioner.plugins.models import ArgusPluginConfig

    registry = PluginRegistry.get_instance()

    # Load admin-configured plugin order from DB
    result = await session.execute(
        select(ArgusPluginConfig)
        .where(ArgusPluginConfig.enabled.is_(True))
        .order_by(ArgusPluginConfig.display_order)
    )
    db_configs = {c.plugin_name: c for c in result.scalars().all()}

    # Determine which plugins to run and their versions
    if req.plugins:
        # Use request-specified plugins (subset of admin-configured)
        plugin_names = [
            name for name in db_configs
            if name in req.plugins or not req.plugins
        ]
        # Add any request-specified plugins not in DB config
        for name in req.plugins:
            if name not in plugin_names:
                plugin_names.append(name)
    else:
        plugin_names = list(db_configs.keys())

    # Resolve versions: request > DB config > plugin default
    versions = {}
    for name in plugin_names:
        if req.plugins and name in req.plugins and req.plugins[name].version:
            versions[name] = req.plugins[name].version
        elif name in db_configs and db_configs[name].selected_version:
            versions[name] = db_configs[name].selected_version
        # else: uses plugin default_version

    # Validate dependency order
    ordered = registry.resolve_order(plugin_names, versions or None)

    # Build context with plugin-specific configs
    ctx_kwargs = {}
    for name in ordered:
        plugin_config = None
        # Merge: plugin default < DB default_config < request config
        if name in db_configs and db_configs[name].default_config:
            plugin_config = db_configs[name].default_config
        if req.plugins and name in req.plugins and req.plugins[name].config:
            if plugin_config:
                plugin_config.update(req.plugins[name].config)
            else:
                plugin_config = req.plugins[name].config

        if plugin_config:
            # Store config in context under plugin's config key
            config_key = name.replace("-", "_") + "_config"
            meta = registry.get(name)
            ver = versions.get(name)
            config_cls = registry.get_config_class(name, ver)
            if config_cls:
                ctx_kwargs[config_key] = config_cls(**plugin_config)
            else:
                ctx_kwargs[config_key] = plugin_config

    ctx = WorkflowContext(
        workspace_id=0,  # Set by caller
        workspace_name=req.name,
        domain=req.domain,
        **ctx_kwargs,
    )

    # Instantiate steps in resolved order
    for name in ordered:
        ver = versions.get(name)
        try:
            step = registry.instantiate_step(name, ver)
            executor.add_step(step)
        except Exception as e:
            # Special handling for gitlab step which needs the client
            if name in ("gitlab-create-project", "argus-gitlab"):
                executor.add_step(GitLabCreateProjectStep(gitlab_client))
            else:
                raise RuntimeError(
                    f"Failed to instantiate plugin '{name}' (version={ver}): {e}"
                ) from e

    logger.info(
        "Plugin workflow built: %d steps in order %s",
        len(ordered), ordered,
    )
    return ctx


async def _build_pipeline_workflow(
    session: "AsyncSession",
    executor: WorkflowExecutor,
    req: "WorkspaceCreateRequest",
    gitlab_client: GitLabClient,
    creator_info: dict | None = None,
) -> WorkflowContext:
    """Build workflow from selected pipeline_ids.

    Loads plugin configs from each selected pipeline (in order),
    merges them, and instantiates steps accordingly.
    """
    from workspace_provisioner.plugins.models import ArgusPluginConfig, ArgusPipeline

    registry = PluginRegistry.get_instance()

    # Collect all plugin configs from selected pipelines in order
    all_plugin_names = []
    versions = {}
    ctx_kwargs = {}

    for pipeline_id in req.pipeline_ids:
        result = await session.execute(
            select(ArgusPluginConfig)
            .where(ArgusPluginConfig.pipeline_id == pipeline_id)
            .where(ArgusPluginConfig.enabled.is_(True))
            .order_by(ArgusPluginConfig.display_order)
        )
        configs = result.scalars().all()

        for cfg in configs:
            if cfg.plugin_name not in all_plugin_names:
                all_plugin_names.append(cfg.plugin_name)
            if cfg.selected_version:
                versions[cfg.plugin_name] = cfg.selected_version
            if cfg.default_config:
                config_key = cfg.plugin_name.replace("-", "_") + "_config"
                meta = registry.get(cfg.plugin_name)
                ver = cfg.selected_version
                config_cls = registry.get_config_class(cfg.plugin_name, ver) if meta else None
                if config_cls:
                    ctx_kwargs[config_key] = config_cls(**(cfg.default_config or {}))
                else:
                    ctx_kwargs[config_key] = cfg.default_config

    # Inject creator info into context
    if creator_info:
        ctx_kwargs.update(creator_info)

    # Inject server host for ingress auth-url
    import socket
    try:
        ctx_kwargs["argus_server_host"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        ctx_kwargs["argus_server_host"] = "127.0.0.1"

    ctx = WorkflowContext(
        workspace_id=0,
        workspace_name=req.name,
        domain=req.domain,
        **ctx_kwargs,
    )

    # Instantiate steps
    for name in all_plugin_names:
        ver = versions.get(name)
        try:
            step = registry.instantiate_step(name, ver)
            executor.add_step(step)
        except Exception:
            if name in ("gitlab-create-project", "argus-gitlab"):
                executor.add_step(GitLabCreateProjectStep(gitlab_client))
            else:
                logger.warning("Skipping plugin '%s': instantiation failed", name)

    logger.info(
        "Pipeline workflow built: %d steps from %d pipeline(s): %s",
        len(all_plugin_names), len(req.pipeline_ids), all_plugin_names,
    )
    return ctx


async def _run_provisioning_workflow(
    workspace_id: int,
    req: WorkspaceCreateRequest,
    gitlab_client: GitLabClient,
    creator_info: dict | None = None,
) -> None:
    """Background task: run the workspace provisioning workflow.

    Supports three modes:
    - Pipeline-based (req.pipeline_ids): Builds workflow from selected pipelines.
    - Plugin-based (req.plugins is set): Uses PluginRegistry to resolve steps.
    - Legacy (both None): Falls back to hardcoded step list.
    """
    from app.core.database import async_session

    logger.info("Starting provisioning workflow for workspace %d (%s)", workspace_id, req.name)
    async with async_session() as session:
        try:
            executor = WorkflowExecutor(session)

            if req.pipeline_ids and len(req.pipeline_ids) > 0:
                # Pipeline-based provisioning
                logger.info("Using pipeline-based provisioning: pipeline_ids=%s", req.pipeline_ids)
                ctx = await _build_pipeline_workflow(
                    session, executor, req, gitlab_client, creator_info
                )
            elif req.plugins is not None:
                # Plugin-based provisioning
                logger.info("Using plugin-based provisioning")
                ctx = await _build_plugin_workflow(
                    session, executor, req, gitlab_client
                )
            else:
                # No pipelines and no plugins — nothing to deploy
                logger.info("No pipelines or plugins specified, creating empty workspace")
                ctx = WorkflowContext(
                    workspace_id=0,
                    workspace_name=req.name,
                    domain=req.domain,
                )

            ctx.workspace_id = workspace_id

            execution = await executor.run(
                workspace_id=workspace_id,
                workflow_name="workspace-provision",
                ctx=ctx,
                include_steps=req.steps,
            )

            # Update workspace status based on workflow result
            result = await session.execute(
                select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
            )
            workspace = result.scalars().first()
            if workspace:
                if execution.status == "completed":
                    workspace.status = WorkspaceStatus.ACTIVE.value

                    # Apply K8s ResourceQuota from resource profile
                    if workspace.resource_profile_id:
                        from app.resource_profile.models import ArgusResourceProfile
                        profile_result = await session.execute(
                            select(ArgusResourceProfile).where(
                                ArgusResourceProfile.id == workspace.resource_profile_id
                            )
                        )
                        profile = profile_result.scalars().first()
                        if profile:
                            from workspace_provisioner.workflow.steps.app_deploy import apply_resource_quota
                            ns = workspace.k8s_namespace or f"argus-ws-{workspace.name}"
                            await apply_resource_quota(ns, float(profile.cpu_cores), int(profile.memory_mb))
                            logger.info("ResourceQuota applied: workspace=%s profile=%s cpu=%s mem=%sMi",
                                        workspace.name, profile.name, profile.cpu_cores, profile.memory_mb)

                    workspace.gitlab_project_id = ctx.get("gitlab_project_id")
                    workspace.gitlab_project_url = ctx.get("gitlab_project_url")
                    workspace.minio_endpoint = ctx.get("minio_external_endpoint")
                    workspace.minio_console_endpoint = ctx.get("minio_console_endpoint")
                    workspace.minio_default_bucket = ctx.get("minio_default_bucket")
                    workspace.airflow_endpoint = ctx.get("airflow_endpoint")
                    workspace.mlflow_endpoint = ctx.get("mlflow_endpoint")
                    workspace.kserve_endpoint = ctx.get("kserve_endpoint")

                    # Store/update service credentials and connection info
                    existing_cred = await session.execute(
                        select(ArgusWorkspaceCredential).where(
                            ArgusWorkspaceCredential.workspace_id == workspace_id
                        )
                    )
                    credential = existing_cred.scalars().first()
                    if credential:
                        # Update existing
                        credential.gitlab_http_url = ctx.get("gitlab_http_url") or credential.gitlab_http_url
                        credential.gitlab_ssh_url = ctx.get("gitlab_ssh_url") or credential.gitlab_ssh_url
                        credential.minio_endpoint = ctx.get("minio_endpoint") or credential.minio_endpoint
                        credential.minio_root_user = ctx.get("minio_root_user") or credential.minio_root_user
                        credential.minio_root_password = ctx.get("minio_root_password") or credential.minio_root_password
                        credential.minio_access_key = ctx.get("minio_ws_admin_access_key") or credential.minio_access_key
                        credential.minio_secret_key = ctx.get("minio_ws_admin_secret_key") or credential.minio_secret_key
                        credential.airflow_url = ctx.get("airflow_endpoint") or credential.airflow_url
                        credential.airflow_admin_password = ctx.get("airflow_admin_password") or credential.airflow_admin_password
                        credential.mlflow_artifact_bucket = ctx.get("mlflow_artifact_bucket") or credential.mlflow_artifact_bucket
                        credential.kserve_endpoint = ctx.get("kserve_endpoint") or credential.kserve_endpoint
                    else:
                        # Create new
                        credential = ArgusWorkspaceCredential(
                            workspace_id=workspace_id,
                            gitlab_http_url=ctx.get("gitlab_http_url"),
                            gitlab_ssh_url=ctx.get("gitlab_ssh_url"),
                            minio_endpoint=ctx.get("minio_endpoint"),
                            minio_root_user=ctx.get("minio_root_user"),
                            minio_root_password=ctx.get("minio_root_password"),
                            minio_access_key=ctx.get("minio_ws_admin_access_key"),
                            minio_secret_key=ctx.get("minio_ws_admin_secret_key"),
                            airflow_url=ctx.get("airflow_endpoint"),
                            airflow_admin_username="admin",
                            airflow_admin_password=ctx.get("airflow_admin_password"),
                            mlflow_artifact_bucket=ctx.get("mlflow_artifact_bucket"),
                            kserve_endpoint=ctx.get("kserve_endpoint"),
                        )
                        session.add(credential)
                    logger.info(
                        "Provisioning completed for workspace %d (%s), "
                        "credentials stored, status → active",
                        workspace_id, req.name,
                    )
                else:
                    workspace.status = WorkspaceStatus.FAILED.value
                    logger.error("Provisioning failed for workspace %d (%s), status → failed", workspace_id, req.name)
                await session.commit()

        except Exception as e:
            logger.error("Provisioning workflow failed for workspace %d: %s", workspace_id, e)
            result = await session.execute(
                select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
            )
            workspace = result.scalars().first()
            if workspace:
                workspace.status = WorkspaceStatus.FAILED.value
                await session.commit()


async def get_workspace(session: AsyncSession, workspace_id: int) -> WorkspaceResponse | None:
    """Get a workspace by ID."""
    logger.info("Fetching workspace: id=%d", workspace_id)
    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        logger.info("Workspace not found: id=%d", workspace_id)
        return None
    return await _build_workspace_response(ws, session)


async def list_workspaces(
    session: AsyncSession,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> PaginatedWorkspaceResponse:
    """List workspaces with optional filtering and pagination."""
    logger.info("Listing workspaces: status=%s, search=%s, page=%d, page_size=%d", status, search, page, page_size)
    base = select(ArgusWorkspace)
    if status:
        base = base.where(ArgusWorkspace.status == status)
    if search:
        base = base.where(
            ArgusWorkspace.name.ilike(f"%{search}%") | ArgusWorkspace.display_name.ilike(f"%{search}%")
        )

    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(ArgusWorkspace.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    workspaces = result.scalars().all()

    items = [await _build_workspace_response(ws, session) for ws in workspaces]
    return PaginatedWorkspaceResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def delete_workspace(
    session: AsyncSession,
    workspace_id: int,
    gitlab_client: GitLabClient,
    req: WorkspaceDeleteRequest | None = None,
) -> WorkspaceResponse | None:
    """Delete a workspace by tearing down all provisioned resources.

    Sets status to "deleting" and launches the deletion workflow in the
    background. The workflow tears down resources in reverse order:
    CustomHook → KServe → MLflow → Airflow → MinioSetup → MinioDeploy → GitLab.

    Args:
        session: Active database session.
        workspace_id: Workspace to delete.
        gitlab_client: Authenticated GitLab client.
        req: Optional deletion options (force, steps filter).

    Returns:
        The workspace with status "deleting", or None if not found.

    Raises:
        ValueError: If the workspace is already being deleted or provisioned.
    """
    if req is None:
        req = WorkspaceDeleteRequest()

    logger.info("Deleting workspace: id=%d", workspace_id)
    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        logger.info("Workspace not found for deletion: id=%d", workspace_id)
        return None

    if ws.status in (WorkspaceStatus.DELETING.value, WorkspaceStatus.DELETED.value):
        raise ValueError(f"Workspace is already {ws.status}")
    if ws.status == WorkspaceStatus.PROVISIONING.value and not req.force:
        raise ValueError("Workspace is still provisioning. Use force=true to delete.")

    # Fetch credentials before status change
    cred_result = await session.execute(
        select(ArgusWorkspaceCredential).where(
            ArgusWorkspaceCredential.workspace_id == workspace_id
        )
    )
    cred = cred_result.scalars().first()

    # Set status to deleting
    ws.status = WorkspaceStatus.DELETING.value
    await session.commit()
    await session.refresh(ws)

    # Build deletion context from DB records
    deletion_context = _build_deletion_context(ws, cred)

    # Enrich gitlab_project_id from workspace_services if not in workspace record
    if not deletion_context.get("gitlab_project_id"):
        svc_result = await session.execute(
            select(ArgusWorkspaceService).where(
                ArgusWorkspaceService.workspace_id == workspace_id,
                ArgusWorkspaceService.plugin_name == "argus-gitlab",
            )
        )
        gitlab_svc = svc_result.scalars().first()
        if gitlab_svc and gitlab_svc.metadata_json:
            deletion_context["gitlab_project_id"] = gitlab_svc.metadata_json.get("project_id")

    logger.info("Launching deletion workflow in background for workspace %d", workspace_id)
    asyncio.create_task(
        _run_deletion_workflow(workspace_id, deletion_context, gitlab_client, req)
    )

    return await _build_workspace_response(ws, session)


def _build_deletion_context(
    ws: ArgusWorkspace,
    cred: ArgusWorkspaceCredential | None,
) -> dict:
    """Build context dict from workspace and credential DB records.

    This reconstructs the WorkflowContext data that was originally built
    during provisioning, so teardown steps can access endpoints, credentials,
    and configuration needed to delete resources.
    """
    ctx_data = {
        "k8s_namespace": ws.k8s_namespace or f"argus-ws-{ws.name}",
        "gitlab_project_id": ws.gitlab_project_id,
        "gitlab_project_url": ws.gitlab_project_url,
    }
    if cred:
        ctx_data.update({
            "gitlab_http_url": cred.gitlab_http_url,
            "gitlab_ssh_url": cred.gitlab_ssh_url,
            "minio_endpoint": cred.minio_endpoint,
            "minio_root_user": cred.minio_root_user,
            "minio_root_password": cred.minio_root_password,
            "minio_ws_admin_access_key": cred.minio_access_key,
            "minio_ws_admin_secret_key": cred.minio_secret_key,
            "minio_default_bucket": ws.minio_default_bucket,
            "airflow_endpoint": cred.airflow_url,
            "airflow_admin_password": cred.airflow_admin_password,
            "mlflow_artifact_bucket": cred.mlflow_artifact_bucket,
            "kserve_endpoint": cred.kserve_endpoint,
        })
    return ctx_data


async def _add_pipeline_steps_for_teardown(
    session: "AsyncSession",
    executor: WorkflowExecutor,
    workspace_id: int,
    gitlab_client: GitLabClient,
) -> None:
    """Add steps from workspace's associated pipelines for teardown."""
    from workspace_provisioner.models import ArgusWorkspacePipeline
    from workspace_provisioner.plugins.models import ArgusPluginConfig

    registry = PluginRegistry.get_instance()

    # Load pipelines associated with this workspace
    wp_result = await session.execute(
        select(ArgusWorkspacePipeline)
        .where(ArgusWorkspacePipeline.workspace_id == workspace_id)
        .order_by(ArgusWorkspacePipeline.deploy_order)
    )
    ws_pipelines = wp_result.scalars().all()

    added_plugins = set()
    for wp in ws_pipelines:
        cfg_result = await session.execute(
            select(ArgusPluginConfig)
            .where(ArgusPluginConfig.pipeline_id == wp.pipeline_id)
            .where(ArgusPluginConfig.enabled.is_(True))
            .order_by(ArgusPluginConfig.display_order)
        )
        for cfg in cfg_result.scalars().all():
            if cfg.plugin_name in added_plugins:
                continue
            added_plugins.add(cfg.plugin_name)
            try:
                step = registry.instantiate_step(cfg.plugin_name, cfg.selected_version)
                executor.add_step(step)
            except Exception:
                if cfg.plugin_name in ("gitlab-create-project", "argus-gitlab"):
                    executor.add_step(GitLabCreateProjectStep(gitlab_client))
                else:
                    logger.warning("Skipping plugin '%s' for teardown", cfg.plugin_name)

    if not added_plugins:
        logger.info("No pipeline plugins found for workspace %d teardown", workspace_id)


async def _run_deletion_workflow(
    workspace_id: int,
    deletion_context: dict,
    gitlab_client: GitLabClient,
    req: WorkspaceDeleteRequest,
) -> None:
    """Background task: run the workspace deletion workflow.

    Tears down all provisioned resources in reverse order (best-effort).
    On completion, sets workspace status to "deleted" and removes
    credential/member records. On failure, sets status to "failed".
    """
    from app.core.database import async_session

    logger.info("Starting deletion workflow for workspace %d", workspace_id)
    async with async_session() as session:
        try:
            # Load workspace for name/domain
            result = await session.execute(
                select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
            )
            ws = result.scalars().first()
            if not ws:
                logger.error("Workspace %d not found during deletion workflow", workspace_id)
                return

            ctx = WorkflowContext(
                workspace_id=workspace_id,
                workspace_name=ws.name,
                domain=ws.domain,
                **deletion_context,
            )

            # Build executor with steps from workspace's pipelines
            # (run_teardown executes them in reverse order)
            executor = WorkflowExecutor(session)
            await _add_pipeline_steps_for_teardown(
                session, executor, workspace_id, gitlab_client
            )

            execution = await executor.run_teardown(
                workspace_id=workspace_id,
                workflow_name="workspace-delete",
                ctx=ctx,
                include_steps=req.steps,
            )

            # Update workspace status
            result = await session.execute(
                select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
            )
            ws = result.scalars().first()
            if ws:
                if execution.status == "completed":
                    ws.status = WorkspaceStatus.DELETED.value
                    # Free up the workspace name for reuse
                    ws.name = f"{ws.name}-deleted-{ws.id}"
                    # Clean up credential and member records
                    cred_result = await session.execute(
                        select(ArgusWorkspaceCredential).where(
                            ArgusWorkspaceCredential.workspace_id == workspace_id
                        )
                    )
                    cred = cred_result.scalars().first()
                    if cred:
                        await session.delete(cred)
                    member_result = await session.execute(
                        select(ArgusWorkspaceMember).where(
                            ArgusWorkspaceMember.workspace_id == workspace_id
                        )
                    )
                    for m in member_result.scalars().all():
                        await session.delete(m)
                    # Clean up workspace-pipeline associations
                    from workspace_provisioner.models import ArgusWorkspacePipeline
                    wp_result = await session.execute(
                        select(ArgusWorkspacePipeline).where(
                            ArgusWorkspacePipeline.workspace_id == workspace_id
                        )
                    )
                    for wp in wp_result.scalars().all():
                        await session.delete(wp)
                    logger.info(
                        "Deletion completed for workspace %d (%s), status → deleted",
                        workspace_id, ws.name,
                    )
                else:
                    ws.status = WorkspaceStatus.FAILED.value
                    logger.error(
                        "Deletion failed for workspace %d (%s): %s",
                        workspace_id, ws.name, execution.error_message,
                    )
                await session.commit()

        except Exception as e:
            logger.error("Deletion workflow failed for workspace %d: %s", workspace_id, e)
            result = await session.execute(
                select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
            )
            ws = result.scalars().first()
            if ws:
                ws.status = WorkspaceStatus.FAILED.value
                await session.commit()


async def get_workspace_credentials(
    session: AsyncSession, workspace_id: int
) -> WorkspaceCredentialResponse | None:
    """Get credentials and connection info for a workspace."""
    logger.info("Fetching credentials for workspace: id=%d", workspace_id)
    result = await session.execute(
        select(ArgusWorkspaceCredential).where(
            ArgusWorkspaceCredential.workspace_id == workspace_id
        )
    )
    cred = result.scalars().first()
    if not cred:
        logger.info("Credentials not found for workspace: id=%d", workspace_id)
        return None
    return WorkspaceCredentialResponse(
        workspace_id=cred.workspace_id,
        gitlab_http_url=cred.gitlab_http_url,
        gitlab_ssh_url=cred.gitlab_ssh_url,
        minio_endpoint=cred.minio_endpoint,
        minio_root_user=cred.minio_root_user,
        minio_root_password=cred.minio_root_password,
        minio_access_key=cred.minio_access_key,
        minio_secret_key=cred.minio_secret_key,
        airflow_url=cred.airflow_url,
        airflow_admin_username=cred.airflow_admin_username,
        airflow_admin_password=cred.airflow_admin_password,
        mlflow_artifact_bucket=cred.mlflow_artifact_bucket,
        kserve_endpoint=cred.kserve_endpoint,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

async def _build_member_response(
    session: AsyncSession,
    m: ArgusWorkspaceMember,
    owner_user_id: int | None = None,
) -> WorkspaceMemberResponse:
    """Build a member response with user info."""
    from app.usermgr.models import ArgusUser
    user_result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == m.user_id)
    )
    user = user_result.scalars().first()
    return WorkspaceMemberResponse(
        id=m.id,
        workspace_id=m.workspace_id,
        user_id=m.user_id,
        username=user.username if user else None,
        display_name=f"{user.first_name} {user.last_name}".strip() if user else None,
        email=user.email if user else None,
        role=m.role,
        is_owner=(m.user_id == owner_user_id) if owner_user_id else False,
        gitlab_access_token=m.gitlab_access_token,
        gitlab_token_name=m.gitlab_token_name,
        created_at=m.created_at,
    )


async def add_member(
    session: AsyncSession,
    workspace_id: int,
    req: WorkspaceMemberAddRequest,
) -> WorkspaceMemberResponse:
    """Add a member to a workspace."""
    member = ArgusWorkspaceMember(
        workspace_id=workspace_id,
        user_id=req.user_id,
        role=req.role.value,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    logger.info("Member added: user=%d workspace=%d role=%s", req.user_id, workspace_id, req.role)

    # Get workspace owner
    ws_result = await session.execute(
        select(ArgusWorkspace.created_by).where(ArgusWorkspace.id == workspace_id)
    )
    owner_id = ws_result.scalar()
    return await _build_member_response(session, member, owner_id)


async def list_members(
    session: AsyncSession, workspace_id: int
) -> list[WorkspaceMemberResponse]:
    """List all members of a workspace."""
    logger.info("Listing members for workspace: id=%d", workspace_id)

    # Get workspace owner
    ws_result = await session.execute(
        select(ArgusWorkspace.created_by).where(ArgusWorkspace.id == workspace_id)
    )
    owner_id = ws_result.scalar()

    result = await session.execute(
        select(ArgusWorkspaceMember).where(
            ArgusWorkspaceMember.workspace_id == workspace_id
        )
    )
    members = result.scalars().all()
    return [await _build_member_response(session, m, owner_id) for m in members]


async def remove_member(session: AsyncSession, member_id: int) -> bool:
    """Remove a member from a workspace."""
    logger.info("Removing member: id=%d", member_id)
    result = await session.execute(
        select(ArgusWorkspaceMember).where(ArgusWorkspaceMember.id == member_id)
    )
    member = result.scalars().first()
    if not member:
        logger.info("Member not found for removal: id=%d", member_id)
        return False
    await session.delete(member)
    await session.commit()
    logger.info("Member removed: id=%d, user=%d, workspace=%d", member_id, member.user_id, member.workspace_id)
    return True


# ---------------------------------------------------------------------------
# Service log helpers
# ---------------------------------------------------------------------------

# Container label mapping: provides human-readable labels for known containers.
_CONTAINER_LABELS: dict[str, str] = {
    "webserver": "Webserver",
    "scheduler": "Scheduler",
    "git-sync": "DAG Sync",
    "db-init": "DB Migration",
    "create-admin": "Admin Setup",
    "minio": "MinIO",
    "mlflow": "MLflow",
    "postgres": "PostgreSQL",
    "neo4j": "Neo4j",
    "trino": "Trino",
    "mariadb": "MariaDB",
    "milvus": "Milvus",
    "fe": "Frontend (FE)",
    "be": "Backend (BE)",
    "mindsdb": "MindsDB",
    "code-server": "VS Code",
    "jupyter": "Jupyter",
}


async def resolve_service_pod(
    session: AsyncSession,
    workspace_id: int,
    service_db_id: int,
    k8s_client: object,
) -> tuple[str, str, dict]:
    """Find the K8s pod for a workspace service by scanning the namespace.

    Instead of maintaining a mapping table between plugin names and K8s
    labels, this lists pods in the workspace namespace and matches by
    pod name — which always contains the service_id or workspace_name.

    Returns (pod_name, namespace, pod_dict).
    Raises ValueError if the workspace, service, or pod is not found.
    """
    ws_result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    workspace = ws_result.scalars().first()
    if not workspace:
        raise ValueError(f"Workspace not found: {workspace_id}")

    svc_result = await session.execute(
        select(ArgusWorkspaceService).where(
            ArgusWorkspaceService.id == service_db_id,
            ArgusWorkspaceService.workspace_id == workspace_id,
        )
    )
    svc = svc_result.scalars().first()
    if not svc:
        raise ValueError(f"Service not found: {service_db_id}")

    namespace = workspace.k8s_namespace or f"argus-ws-{workspace.name}"

    pod_data = await k8s_client.list_resources("pods", namespace=namespace)
    pods = pod_data.get("items", [])

    # Strategy 1: match by service_id in pod name (works for all services)
    if svc.service_id:
        for pod in pods:
            if svc.service_id in pod["metadata"]["name"]:
                return pod["metadata"]["name"], namespace, pod

    # Strategy 2: match by plugin short name + workspace name
    short = _plugin_short_name(svc.plugin_name)
    prefix = f"argus-{short}-{workspace.name}"
    for pod in pods:
        if pod["metadata"]["name"].startswith(prefix):
            return pod["metadata"]["name"], namespace, pod

    raise ValueError(
        f"No pods found for service {svc.plugin_name} "
        f"(service_id={svc.service_id}) in namespace {namespace}"
    )


def _plugin_short_name(plugin_name: str) -> str:
    """Derive a short name from plugin_name for pod name matching.

    Examples: argus-minio-deploy → minio, argus-vscode-server → vscode
    """
    name = plugin_name
    for suffix in ("-deploy", "-setup", "-workspace"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if name.startswith("argus-"):
        name = name[len("argus-"):]
    return name


def _container_label(name: str) -> str:
    """Get a human-readable label for a container name."""
    return _CONTAINER_LABELS.get(name, name.replace("-", " ").title())


