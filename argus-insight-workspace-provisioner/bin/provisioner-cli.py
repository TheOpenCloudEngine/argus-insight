#!/usr/bin/env python3
"""Argus Insight Workspace Provisioner - Standalone CLI.

A command-line tool for testing the workspace provisioning workflow
independently of argus-insight-server.

Commands:
    create   - Create a workspace and run the provisioning workflow
    status   - Check provisioning workflow status for a workspace
    list     - List all workspaces
    get      - Get workspace details by ID
    delete   - Delete a workspace
    validate - Validate a provisioning config JSON file (dry-run)
    render   - Render K8s manifests without applying (dry-run)

Environment variables:
    PROVISIONER_DB_URL  Database URL (default: postgresql+asyncpg://argus:argus@localhost:5432/argus)
    GITLAB_URL          GitLab server URL (required for create)
    GITLAB_TOKEN        GitLab private token (required for create)

Usage:
    python bin/provisioner-cli.py create --file bin/samples/workspace-default.json
    python bin/provisioner-cli.py create --file bin/samples/workspace-full.json --dry-run
    python bin/provisioner-cli.py status --workspace-id 1
    python bin/provisioner-cli.py list
    python bin/provisioner-cli.py validate --file bin/samples/workspace-full.json
    python bin/provisioner-cli.py render --file bin/samples/workspace-default.json --step minio
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_request_file(filepath: str) -> dict:
    """Load and validate a workspace creation request JSON file."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    return data


async def cmd_create(args: argparse.Namespace) -> None:
    """Create a workspace and run the provisioning workflow."""
    from workspace_provisioner.config import ProvisioningConfig
    from workspace_provisioner.schemas import WorkspaceCreateRequest
    from workspace_provisioner.standalone import get_standalone_session, init_db

    data = load_request_file(args.file)

    # Validate request
    req = WorkspaceCreateRequest(**data)
    print(f"Workspace: {req.name}")
    print(f"Domain:    {req.domain}")
    print(f"Admin ID:  {req.admin_user_id}")
    print(f"Config:    {req.provisioning_config.model_dump_json(indent=2)}")
    print()

    if args.dry_run:
        print("[DRY-RUN] Request validated successfully. No resources created.")
        return

    # Check GitLab credentials
    gitlab_url = os.environ.get("GITLAB_URL")
    gitlab_token = os.environ.get("GITLAB_TOKEN")

    if not gitlab_url or not gitlab_token:
        print(
            "Error: GITLAB_URL and GITLAB_TOKEN environment variables are required.",
            file=sys.stderr,
        )
        print("  export GITLAB_URL=https://gitlab-global.argus-insight.dev.net")
        print("  export GITLAB_TOKEN=glpat-xxxxxxxxxxxx")
        sys.exit(1)

    await init_db()

    # Patch service.py to use standalone session
    from workspace_provisioner import standalone
    import workspace_provisioner.service as svc_module

    # Monkey-patch the async_session import in service
    original_run = svc_module._run_provisioning_workflow

    async def patched_run(workspace_id, req, gitlab_client):
        """Patched workflow runner that uses standalone DB session."""
        from workspace_provisioner.workflow.engine import WorkflowContext, WorkflowExecutor
        from workspace_provisioner.workflow.steps.gitlab_create_project import (
            GitLabCreateProjectStep,
        )
        from workspace_provisioner.workflow.steps.minio_deploy import MinioDeployStep
        from workspace_provisioner.workflow.steps.minio_setup import MinioSetupStep
        from workspace_provisioner.workflow.steps.airflow_deploy import AirflowDeployStep
        from workspace_provisioner.workflow.steps.mlflow_deploy import MlflowDeployStep
        from workspace_provisioner.models import ArgusWorkspace
        from workspace_provisioner.schemas import WorkspaceStatus
        from sqlalchemy import select

        async with standalone.get_standalone_session() as session:
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

                execution = await executor.run(
                    workspace_id=workspace_id,
                    workflow_name="workspace-provision",
                    ctx=ctx,
                )

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

                print(f"\nWorkflow result: {execution.status}")
                if execution.error_message:
                    print(f"Error: {execution.error_message}")

            except Exception as e:
                logging.getLogger(__name__).error("Workflow failed: %s", e)
                raise

    svc_module._run_provisioning_workflow = patched_run

    # Create workspace
    from workspace_provisioner.gitlab.client import GitLabClient
    from workspace_provisioner.models import ArgusWorkspace, ArgusWorkspaceMember
    from workspace_provisioner.schemas import WorkspaceStatus

    gitlab_client = GitLabClient(url=gitlab_url, private_token=gitlab_token)

    async with standalone.get_standalone_session() as session:
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
        print(f"Workspace created: id={workspace.id}, name={workspace.name}")

        # Add admin member
        member = ArgusWorkspaceMember(
            workspace_id=workspace.id,
            user_id=req.admin_user_id,
            role="WorkspaceAdmin",
        )
        session.add(member)
        await session.commit()

    # Run workflow synchronously (not as background task)
    print("\nRunning provisioning workflow...")
    await patched_run(workspace.id, req, gitlab_client)
    print("Done.")


async def cmd_status(args: argparse.Namespace) -> None:
    """Check provisioning workflow status for a workspace."""
    from workspace_provisioner.standalone import get_standalone_session, init_db
    from workspace_provisioner.workflow.models import (
        ArgusWorkflowExecution,
        ArgusWorkflowStepExecution,
    )
    from sqlalchemy import select

    await init_db()

    async with get_standalone_session() as session:
        result = await session.execute(
            select(ArgusWorkflowExecution)
            .where(ArgusWorkflowExecution.workspace_id == args.workspace_id)
            .order_by(ArgusWorkflowExecution.created_at.desc())
        )
        executions = result.scalars().all()

        if not executions:
            print(f"No workflow executions found for workspace_id={args.workspace_id}")
            return

        for ex in executions:
            print(f"Workflow: {ex.workflow_name} (id={ex.id})")
            print(f"  Status:     {ex.status}")
            print(f"  Started:    {ex.started_at}")
            print(f"  Finished:   {ex.finished_at}")
            if ex.error_message:
                print(f"  Error:      {ex.error_message}")

            step_result = await session.execute(
                select(ArgusWorkflowStepExecution)
                .where(ArgusWorkflowStepExecution.execution_id == ex.id)
                .order_by(ArgusWorkflowStepExecution.step_order)
            )
            steps = step_result.scalars().all()

            for s in steps:
                status_icon = {
                    "completed": "+",
                    "failed": "X",
                    "running": ">",
                    "skipped": "-",
                    "pending": ".",
                }.get(s.status, "?")
                print(f"  [{status_icon}] Step {s.step_order + 1}: {s.step_name} ({s.status})")
                if s.error_message:
                    print(f"        Error: {s.error_message}")
                if s.result_data and args.verbose:
                    print(f"        Result: {s.result_data}")
            print()


async def cmd_list(args: argparse.Namespace) -> None:
    """List all workspaces."""
    from workspace_provisioner.models import ArgusWorkspace
    from workspace_provisioner.standalone import get_standalone_session, init_db
    from sqlalchemy import select

    await init_db()

    async with get_standalone_session() as session:
        result = await session.execute(
            select(ArgusWorkspace).order_by(ArgusWorkspace.created_at.desc())
        )
        workspaces = result.scalars().all()

        if not workspaces:
            print("No workspaces found.")
            return

        fmt = "{:<5} {:<20} {:<15} {:<50}"
        print(fmt.format("ID", "NAME", "STATUS", "DOMAIN"))
        print("-" * 90)
        for ws in workspaces:
            print(fmt.format(ws.id, ws.name, ws.status, ws.domain))


async def cmd_get(args: argparse.Namespace) -> None:
    """Get workspace details by ID."""
    from workspace_provisioner.models import ArgusWorkspace
    from workspace_provisioner.standalone import get_standalone_session, init_db
    from sqlalchemy import select

    await init_db()

    async with get_standalone_session() as session:
        result = await session.execute(
            select(ArgusWorkspace).where(ArgusWorkspace.id == args.workspace_id)
        )
        ws = result.scalars().first()

        if not ws:
            print(f"Workspace not found: id={args.workspace_id}")
            return

        print(f"ID:                    {ws.id}")
        print(f"Name:                  {ws.name}")
        print(f"Display Name:          {ws.display_name}")
        print(f"Description:           {ws.description}")
        print(f"Domain:                {ws.domain}")
        print(f"Status:                {ws.status}")
        print(f"K8s Cluster:           {ws.k8s_cluster}")
        print(f"K8s Namespace:         {ws.k8s_namespace}")
        print(f"GitLab Project ID:     {ws.gitlab_project_id}")
        print(f"GitLab Project URL:    {ws.gitlab_project_url}")
        print(f"MinIO Endpoint:        {ws.minio_endpoint}")
        print(f"MinIO Console:         {ws.minio_console_endpoint}")
        print(f"MinIO Default Bucket:  {ws.minio_default_bucket}")
        print(f"Airflow Endpoint:      {ws.airflow_endpoint}")
        print(f"MLflow Endpoint:       {ws.mlflow_endpoint}")
        print(f"Created By:            {ws.created_by}")
        print(f"Created At:            {ws.created_at}")
        print(f"Updated At:            {ws.updated_at}")


async def cmd_delete(args: argparse.Namespace) -> None:
    """Delete a workspace."""
    from workspace_provisioner.models import ArgusWorkspace
    from workspace_provisioner.standalone import get_standalone_session, init_db
    from sqlalchemy import select

    await init_db()

    async with get_standalone_session() as session:
        result = await session.execute(
            select(ArgusWorkspace).where(ArgusWorkspace.id == args.workspace_id)
        )
        ws = result.scalars().first()
        if not ws:
            print(f"Workspace not found: id={args.workspace_id}")
            return

        if not args.force:
            answer = input(f"Delete workspace '{ws.name}' (id={ws.id})? [y/N] ")
            if answer.lower() != "y":
                print("Cancelled.")
                return

        await session.delete(ws)
        await session.commit()
        print(f"Workspace deleted: {ws.name} (id={ws.id})")


async def cmd_validate(args: argparse.Namespace) -> None:
    """Validate a provisioning config JSON file."""
    from workspace_provisioner.schemas import WorkspaceCreateRequest

    data = load_request_file(args.file)

    try:
        req = WorkspaceCreateRequest(**data)
        print("Validation: OK")
        print()
        print(f"  name:           {req.name}")
        print(f"  display_name:   {req.display_name}")
        print(f"  domain:         {req.domain}")
        print(f"  k8s_cluster:    {req.k8s_cluster}")
        print(f"  k8s_namespace:  {req.k8s_namespace}")
        print(f"  admin_user_id:  {req.admin_user_id}")
        print()
        print("  provisioning_config:")
        config = req.provisioning_config
        print(f"    minio.image:               {config.minio.image}")
        print(f"    minio.storage_size:         {config.minio.storage_size}")
        print(f"    minio.resources:            {config.minio.resources.cpu_request}/{config.minio.resources.memory_request} (req) → {config.minio.resources.cpu_limit}/{config.minio.resources.memory_limit} (lim)")
        print(f"    airflow.image:              {config.airflow.image}")
        print(f"    airflow.postgres_image:     {config.airflow.postgres_image}")
        print(f"    airflow.git_sync_image:     {config.airflow.git_sync_image}")
        print(f"    airflow.git_sync_interval:  {config.airflow.git_sync_interval}s")
        print(f"    airflow.dags_storage_size:  {config.airflow.dags_storage_size}")
        print(f"    airflow.logs_storage_size:  {config.airflow.logs_storage_size}")
        print(f"    airflow.db_storage_size:    {config.airflow.db_storage_size}")
        print(f"    airflow.webserver:          {config.airflow.webserver_resources.cpu_request}/{config.airflow.webserver_resources.memory_request} (req) → {config.airflow.webserver_resources.cpu_limit}/{config.airflow.webserver_resources.memory_limit} (lim)")
        print(f"    airflow.scheduler:          {config.airflow.scheduler_resources.cpu_request}/{config.airflow.scheduler_resources.memory_request} (req) → {config.airflow.scheduler_resources.cpu_limit}/{config.airflow.scheduler_resources.memory_limit} (lim)")
        print(f"    mlflow.image:               {config.mlflow.image}")
        print(f"    mlflow.postgres_image:      {config.mlflow.postgres_image}")
        print(f"    mlflow.db_storage_size:     {config.mlflow.db_storage_size}")
        print(f"    mlflow.resources:           {config.mlflow.resources.cpu_request}/{config.mlflow.resources.memory_request} (req) → {config.mlflow.resources.cpu_limit}/{config.mlflow.resources.memory_limit} (lim)")
    except Exception as e:
        print(f"Validation: FAILED", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        sys.exit(1)


async def cmd_render(args: argparse.Namespace) -> None:
    """Render K8s manifests without applying (dry-run)."""
    from workspace_provisioner.schemas import WorkspaceCreateRequest
    from workspace_provisioner.kubernetes.client import render_manifests

    data = load_request_file(args.file)
    req = WorkspaceCreateRequest(**data)
    config = req.provisioning_config
    namespace = req.k8s_namespace or f"argus-ws-{req.name}"

    step = args.step

    variables = {
        "WORKSPACE_NAME": req.name,
        "K8S_NAMESPACE": namespace,
        "DOMAIN": req.domain,
    }

    if step == "minio":
        variables.update({
            "MINIO_IMAGE": config.minio.image,
            "MINIO_STORAGE_SIZE": config.minio.storage_size,
            "MINIO_CPU_REQUEST": config.minio.resources.cpu_request,
            "MINIO_CPU_LIMIT": config.minio.resources.cpu_limit,
            "MINIO_MEMORY_REQUEST": config.minio.resources.memory_request,
            "MINIO_MEMORY_LIMIT": config.minio.resources.memory_limit,
            "MINIO_ROOT_USER": f"minio-{req.name}-admin",
            "MINIO_ROOT_PASSWORD": "<GENERATED_AT_RUNTIME>",
        })
    elif step == "airflow":
        variables.update({
            "AIRFLOW_IMAGE": config.airflow.image,
            "AIRFLOW_POSTGRES_IMAGE": config.airflow.postgres_image,
            "AIRFLOW_GIT_SYNC_IMAGE": config.airflow.git_sync_image,
            "AIRFLOW_GIT_SYNC_INTERVAL": str(config.airflow.git_sync_interval),
            "AIRFLOW_DAGS_STORAGE_SIZE": config.airflow.dags_storage_size,
            "AIRFLOW_LOGS_STORAGE_SIZE": config.airflow.logs_storage_size,
            "AIRFLOW_DB_STORAGE_SIZE": config.airflow.db_storage_size,
            "AIRFLOW_WEBSERVER_CPU_REQUEST": config.airflow.webserver_resources.cpu_request,
            "AIRFLOW_WEBSERVER_CPU_LIMIT": config.airflow.webserver_resources.cpu_limit,
            "AIRFLOW_WEBSERVER_MEMORY_REQUEST": config.airflow.webserver_resources.memory_request,
            "AIRFLOW_WEBSERVER_MEMORY_LIMIT": config.airflow.webserver_resources.memory_limit,
            "AIRFLOW_SCHEDULER_CPU_REQUEST": config.airflow.scheduler_resources.cpu_request,
            "AIRFLOW_SCHEDULER_CPU_LIMIT": config.airflow.scheduler_resources.cpu_limit,
            "AIRFLOW_SCHEDULER_MEMORY_REQUEST": config.airflow.scheduler_resources.memory_request,
            "AIRFLOW_SCHEDULER_MEMORY_LIMIT": config.airflow.scheduler_resources.memory_limit,
            "AIRFLOW_ADMIN_PASSWORD": "<GENERATED_AT_RUNTIME>",
            "AIRFLOW_DB_PASSWORD": "<GENERATED_AT_RUNTIME>",
            "AIRFLOW_FERNET_KEY": "<GENERATED_AT_RUNTIME>",
            "AIRFLOW_SECRET_KEY": "<GENERATED_AT_RUNTIME>",
            "GITLAB_REPO_URL": "<SET_FROM_GITLAB_STEP>",
            "GITLAB_TOKEN": os.environ.get("GITLAB_TOKEN", "<NOT_SET>"),
        })
    elif step == "mlflow":
        variables.update({
            "MLFLOW_IMAGE": config.mlflow.image,
            "MLFLOW_POSTGRES_IMAGE": config.mlflow.postgres_image,
            "MLFLOW_DB_STORAGE_SIZE": config.mlflow.db_storage_size,
            "MLFLOW_CPU_REQUEST": config.mlflow.resources.cpu_request,
            "MLFLOW_CPU_LIMIT": config.mlflow.resources.cpu_limit,
            "MLFLOW_MEMORY_REQUEST": config.mlflow.resources.memory_request,
            "MLFLOW_MEMORY_LIMIT": config.mlflow.resources.memory_limit,
            "MLFLOW_DB_PASSWORD": "<GENERATED_AT_RUNTIME>",
            "MLFLOW_ARTIFACT_BUCKET": req.name,
            "MINIO_ACCESS_KEY": "<SET_FROM_MINIO_STEP>",
            "MINIO_SECRET_KEY": "<SET_FROM_MINIO_STEP>",
        })
    else:
        print(f"Unknown step: {step}. Use: minio, airflow, mlflow", file=sys.stderr)
        sys.exit(1)

    manifests = render_manifests(step, variables)
    print(manifests)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provisioner-cli",
        description="Argus Insight Workspace Provisioner - Standalone CLI",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create
    p_create = subparsers.add_parser("create", help="Create a workspace and run provisioning")
    p_create.add_argument("-f", "--file", required=True, help="Path to workspace request JSON file")
    p_create.add_argument("--dry-run", action="store_true", help="Validate only, don't create resources")

    # status
    p_status = subparsers.add_parser("status", help="Check workflow status for a workspace")
    p_status.add_argument("-w", "--workspace-id", type=int, required=True, help="Workspace ID")
    p_status.add_argument("-v", "--verbose", action="store_true", help="Show step result data")

    # list
    subparsers.add_parser("list", help="List all workspaces")

    # get
    p_get = subparsers.add_parser("get", help="Get workspace details")
    p_get.add_argument("-w", "--workspace-id", type=int, required=True, help="Workspace ID")

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete a workspace")
    p_delete.add_argument("-w", "--workspace-id", type=int, required=True, help="Workspace ID")
    p_delete.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate a provisioning config file")
    p_validate.add_argument("-f", "--file", required=True, help="Path to workspace request JSON file")

    # render
    p_render = subparsers.add_parser("render", help="Render K8s manifests (dry-run)")
    p_render.add_argument("-f", "--file", required=True, help="Path to workspace request JSON file")
    p_render.add_argument("-s", "--step", required=True, choices=["minio", "airflow", "mlflow"],
                          help="Step to render manifests for")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)

    command_map = {
        "create": cmd_create,
        "status": cmd_status,
        "list": cmd_list,
        "get": cmd_get,
        "delete": cmd_delete,
        "validate": cmd_validate,
        "render": cmd_render,
    }

    asyncio.run(command_map[args.command](args))


if __name__ == "__main__":
    main()
