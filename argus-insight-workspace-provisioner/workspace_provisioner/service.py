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
from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
from workspace_provisioner.schemas import (
    PaginatedWorkspaceResponse,
    StepExecutionResponse,
    WorkflowExecutionResponse,
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
    # Check uniqueness
    existing = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.name == req.name)
    )
    if existing.scalars().first():
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
            )

            executor = WorkflowExecutor(session)
            executor.add_step(GitLabCreateProjectStep(gitlab_client))
            executor.add_step(MinioDeployStep())
            executor.add_step(MinioSetupStep())
            executor.add_step(AirflowDeployStep())
            executor.add_step(MlflowDeployStep())
            # Future steps will be added here:
            # executor.add_step(DnsRegisterStep(...))

            execution = await executor.run(
                workspace_id=workspace_id,
                workflow_name="workspace-provision",
                ctx=ctx,
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
                else:
                    workspace.status = WorkspaceStatus.FAILED.value
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
    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        return None
    return _build_workspace_response(ws)


async def list_workspaces(
    session: AsyncSession,
    status: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> PaginatedWorkspaceResponse:
    """List workspaces with optional filtering and pagination."""
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


async def delete_workspace(session: AsyncSession, workspace_id: int) -> bool:
    """Delete a workspace by ID."""
    result = await session.execute(
        select(ArgusWorkspace).where(ArgusWorkspace.id == workspace_id)
    )
    ws = result.scalars().first()
    if not ws:
        return False
    await session.delete(ws)
    await session.commit()
    logger.info("Workspace deleted: %s (id=%d)", ws.name, ws.id)
    return True


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
    result = await session.execute(
        select(ArgusWorkspaceMember).where(ArgusWorkspaceMember.id == member_id)
    )
    member = result.scalars().first()
    if not member:
        return False
    await session.delete(member)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Workflow status
# ---------------------------------------------------------------------------

async def get_workflow_status(
    session: AsyncSession, workspace_id: int
) -> list[WorkflowExecutionResponse]:
    """Get all workflow executions for a workspace, with step details."""
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
