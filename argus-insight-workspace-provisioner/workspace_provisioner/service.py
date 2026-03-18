"""Workspace provisioning service.

Business logic for workspace CRUD and provisioning workflow orchestration.
This service is called by the router and coordinates between the database
models and the workflow engine.
"""

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_provisioner.gitlab.client import GitLabClient
from workspace_provisioner.models import (
    ArgusWorkspace,
    ArgusWorkspaceCredential,
    ArgusWorkspaceMember,
)
from workspace_provisioner.schemas import (
    PaginatedWorkspaceResponse,
    StepExecutionResponse,
    WorkflowExecutionResponse,
    WorkspaceCredentialResponse,
    WorkspaceDeleteRequest,
    WorkspaceMemberAddRequest,
    WorkspaceMemberResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceStatus,
)
from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowExecutor
from workspace_provisioner.workflow.models import (
    ArgusWorkflowExecution,
    ArgusWorkflowStepExecution,
)
from workspace_provisioner.workflow.steps.gitlab_create_project import (
    GitLabCreateProjectStep,
)
from workspace_provisioner.workflow.steps.airflow_deploy import AirflowDeployStep
from workspace_provisioner.workflow.steps.minio_deploy import MinioDeployStep
from workspace_provisioner.workflow.steps.minio_setup import MinioSetupStep
from workspace_provisioner.workflow.steps.mlflow_deploy import MlflowDeployStep
from workspace_provisioner.workflow.steps.kserve_deploy import KServeDeployStep
from workspace_provisioner.workflow.steps.custom_hook import CustomHookStep

logger = logging.getLogger(__name__)


def _build_workspace_response(ws: ArgusWorkspace) -> WorkspaceResponse:
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

    # Create workspace record
    workspace = ArgusWorkspace(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        domain=req.domain,
        k8s_cluster=req.k8s_cluster,
        k8s_namespace=req.k8s_namespace or f"argus-ws-{req.name}",
        status=WorkspaceStatus.PROVISIONING.value,
        created_by=req.admin_user_id,
    )
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    logger.info("Workspace created: %s (id=%d)", workspace.name, workspace.id)

    # Add creator as WorkspaceAdmin
    member = ArgusWorkspaceMember(
        workspace_id=workspace.id,
        user_id=req.admin_user_id,
        role="WorkspaceAdmin",
    )
    session.add(member)
    await session.commit()

    # Launch provisioning workflow in background
    logger.info("Launching provisioning workflow in background for workspace %d", workspace.id)
    asyncio.create_task(
        _run_provisioning_workflow(workspace.id, req, gitlab_client)
    )

    return _build_workspace_response(workspace)


async def _run_provisioning_workflow(
    workspace_id: int,
    req: WorkspaceCreateRequest,
    gitlab_client: GitLabClient,
) -> None:
    """Background task: run the workspace provisioning workflow.

    Creates a new database session for the background task, builds the
    workflow pipeline, executes it, and updates the workspace status.
    """
    from app.core.database import async_session

    logger.info("Starting provisioning workflow for workspace %d (%s)", workspace_id, req.name)
    async with async_session() as session:
        try:
            provisioning_config = req.provisioning_config
            ctx = WorkflowContext(
                workspace_id=workspace_id,
                workspace_name=req.name,
                domain=req.domain,
                minio_config=provisioning_config.minio,
                airflow_config=provisioning_config.airflow,
                mlflow_config=provisioning_config.mlflow,
                kserve_config=provisioning_config.kserve,
            )

            executor = WorkflowExecutor(session)
            executor.add_step(GitLabCreateProjectStep(gitlab_client))
            executor.add_step(MinioDeployStep())
            executor.add_step(MinioSetupStep())
            executor.add_step(AirflowDeployStep())
            executor.add_step(MlflowDeployStep())
            executor.add_step(KServeDeployStep())
            executor.add_step(CustomHookStep())

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
                    workspace.gitlab_project_id = ctx.get("gitlab_project_id")
                    workspace.gitlab_project_url = ctx.get("gitlab_project_url")
                    workspace.minio_endpoint = ctx.get("minio_external_endpoint")
                    workspace.minio_console_endpoint = ctx.get("minio_console_endpoint")
                    workspace.minio_default_bucket = ctx.get("minio_default_bucket")
                    workspace.airflow_endpoint = ctx.get("airflow_endpoint")
                    workspace.mlflow_endpoint = ctx.get("mlflow_endpoint")
                    workspace.kserve_endpoint = ctx.get("kserve_endpoint")

                    # Store service credentials and connection info
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
    return _build_workspace_response(ws)


async def list_workspaces(
    session: AsyncSession,
    status: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> PaginatedWorkspaceResponse:
    """List workspaces with optional filtering and pagination."""
    logger.info("Listing workspaces: status=%s, page=%d, page_size=%d", status, page, page_size)
    base = select(ArgusWorkspace)
    if status:
        base = base.where(ArgusWorkspace.status == status)

    count_query = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = base.order_by(ArgusWorkspace.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    workspaces = result.scalars().all()

    return PaginatedWorkspaceResponse(
        items=[_build_workspace_response(ws) for ws in workspaces],
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

    logger.info("Launching deletion workflow in background for workspace %d", workspace_id)
    asyncio.create_task(
        _run_deletion_workflow(workspace_id, deletion_context, gitlab_client, req)
    )

    return _build_workspace_response(ws)


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

            # Build executor with same steps as provisioning
            # (run_teardown executes them in reverse order)
            executor = WorkflowExecutor(session)
            executor.add_step(GitLabCreateProjectStep(gitlab_client))
            executor.add_step(MinioDeployStep())
            executor.add_step(MinioSetupStep())
            executor.add_step(AirflowDeployStep())
            executor.add_step(MlflowDeployStep())
            executor.add_step(KServeDeployStep())
            executor.add_step(CustomHookStep())

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
    return WorkspaceMemberResponse(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=member.role,
        created_at=member.created_at,
    )


async def list_members(
    session: AsyncSession, workspace_id: int
) -> list[WorkspaceMemberResponse]:
    """List all members of a workspace."""
    logger.info("Listing members for workspace: id=%d", workspace_id)
    result = await session.execute(
        select(ArgusWorkspaceMember).where(
            ArgusWorkspaceMember.workspace_id == workspace_id
        )
    )
    members = result.scalars().all()
    return [
        WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            created_at=m.created_at,
        )
        for m in members
    ]


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
# Workflow status
# ---------------------------------------------------------------------------

async def get_workflow_status(
    session: AsyncSession, workspace_id: int
) -> list[WorkflowExecutionResponse]:
    """Get all workflow executions for a workspace, with step details."""
    logger.info("Fetching workflow status for workspace: id=%d", workspace_id)
    result = await session.execute(
        select(ArgusWorkflowExecution)
        .where(ArgusWorkflowExecution.workspace_id == workspace_id)
        .order_by(ArgusWorkflowExecution.created_at.desc())
    )
    executions = result.scalars().all()

    responses = []
    for ex in executions:
        step_result = await session.execute(
            select(ArgusWorkflowStepExecution)
            .where(ArgusWorkflowStepExecution.execution_id == ex.id)
            .order_by(ArgusWorkflowStepExecution.step_order)
        )
        steps = step_result.scalars().all()

        responses.append(
            WorkflowExecutionResponse(
                id=ex.id,
                workspace_id=ex.workspace_id,
                workflow_name=ex.workflow_name,
                status=ex.status,
                started_at=ex.started_at,
                finished_at=ex.finished_at,
                error_message=ex.error_message,
                created_at=ex.created_at,
                steps=[
                    StepExecutionResponse(
                        id=s.id,
                        step_name=s.step_name,
                        step_order=s.step_order,
                        status=s.status,
                        started_at=s.started_at,
                        finished_at=s.finished_at,
                        error_message=s.error_message,
                        result_data=s.result_data,
                    )
                    for s in steps
                ],
            )
        )

    return responses
