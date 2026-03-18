"""Step-based Workflow Engine for workspace provisioning.

Provides the core abstractions for defining and executing multi-step workflows:
- WorkflowStep: Abstract base class for individual steps.
- WorkflowContext: Shared state passed between steps.
- WorkflowExecutor: Runs a sequence of steps, tracking state in the database.

Steps are executed sequentially. Each step can read/write to the shared context,
allowing later steps to use outputs from earlier steps (e.g., GitLab project ID).

Usage:
    executor = WorkflowExecutor(session)
    executor.add_step(GitLabCreateProjectStep())
    executor.add_step(MinioCreateBucketStep())
    await executor.run(workspace_id=1, workflow_name="workspace-provision")
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_provisioner.workflow.models import (
    ArgusWorkflowExecution,
    ArgusWorkflowStepExecution,
)

logger = logging.getLogger(__name__)


class WorkflowContext:
    """Shared mutable state for a workflow execution.

    Steps read inputs and write outputs through this context object.
    The context is initialized with workspace metadata and accumulates
    results as each step completes.

    Attributes:
        workspace_id: The workspace being provisioned.
        workspace_name: Workspace slug name.
        domain: Domain suffix (e.g., "dev.net").
        data: Free-form dictionary for step inputs/outputs.
    """

    def __init__(
        self,
        workspace_id: int,
        workspace_name: str,
        domain: str,
        **kwargs,
    ) -> None:
        self.workspace_id = workspace_id
        self.workspace_name = workspace_name
        self.domain = domain
        self.data: dict = dict(kwargs)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value


class WorkflowStep(ABC):
    """Abstract base class for a single workflow step.

    Subclasses must implement:
    - name: A unique identifier for this step (e.g., "gitlab-create-project").
    - execute(): The async method that performs the step's work.

    Optionally override:
    - rollback(): Called if a later step fails and rollback is needed.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique step identifier."""

    @abstractmethod
    async def execute(self, ctx: WorkflowContext) -> dict | None:
        """Execute the step.

        Args:
            ctx: Shared workflow context for reading inputs and writing outputs.

        Returns:
            Optional dict of result data to persist in the step execution record.

        Raises:
            Exception: Any exception will mark the step (and workflow) as failed.
        """

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Rollback this step's changes. Called on workflow failure.

        Default implementation is a no-op. Override in subclasses that
        create resources which should be cleaned up on failure.
        """


class WorkflowExecutor:
    """Executes a sequence of WorkflowSteps and tracks state in the database.

    Steps are added via add_step() and executed in order by run().
    Each step's status is persisted to argus_workflow_step_executions,
    and the overall workflow status is tracked in argus_workflow_executions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._steps: list[WorkflowStep] = []

    def add_step(self, step: WorkflowStep) -> "WorkflowExecutor":
        """Add a step to the workflow pipeline. Returns self for chaining."""
        self._steps.append(step)
        return self

    async def run(
        self,
        workspace_id: int,
        workflow_name: str,
        ctx: WorkflowContext,
    ) -> ArgusWorkflowExecution:
        """Execute all steps sequentially.

        Creates workflow and step execution records, runs each step,
        and updates statuses in real-time. If a step fails, subsequent
        steps are skipped and rollback is attempted for completed steps.

        Args:
            workspace_id: The workspace to provision.
            workflow_name: Identifier for this workflow type.
            ctx: Pre-built workflow context with workspace metadata.

        Returns:
            The ArgusWorkflowExecution record with final status.
        """
        now = datetime.now(timezone.utc)

        # Create workflow execution record
        execution = ArgusWorkflowExecution(
            workspace_id=workspace_id,
            workflow_name=workflow_name,
            status="running",
            started_at=now,
        )
        self._session.add(execution)
        await self._session.commit()
        await self._session.refresh(execution)

        # Create step execution records
        step_records: list[ArgusWorkflowStepExecution] = []
        for i, step in enumerate(self._steps):
            step_record = ArgusWorkflowStepExecution(
                execution_id=execution.id,
                step_name=step.name,
                step_order=i,
                status="pending",
            )
            self._session.add(step_record)
            step_records.append(step_record)
        await self._session.commit()
        for sr in step_records:
            await self._session.refresh(sr)

        # Execute steps sequentially
        completed_steps: list[tuple[WorkflowStep, ArgusWorkflowStepExecution]] = []
        failed = False

        for i, (step, step_record) in enumerate(zip(self._steps, step_records)):
            if failed:
                step_record.status = "skipped"
                await self._session.commit()
                continue

            step_record.status = "running"
            step_record.started_at = datetime.now(timezone.utc)
            await self._session.commit()

            logger.info(
                "Workflow %s step [%d/%d] %s: starting",
                workflow_name,
                i + 1,
                len(self._steps),
                step.name,
            )

            try:
                result = await step.execute(ctx)
                step_record.status = "completed"
                step_record.finished_at = datetime.now(timezone.utc)
                if result:
                    step_record.result_data = json.dumps(result, ensure_ascii=False)
                await self._session.commit()
                completed_steps.append((step, step_record))
                logger.info(
                    "Workflow %s step [%d/%d] %s: completed",
                    workflow_name,
                    i + 1,
                    len(self._steps),
                    step.name,
                )
            except Exception as e:
                step_record.status = "failed"
                step_record.finished_at = datetime.now(timezone.utc)
                step_record.error_message = str(e)
                await self._session.commit()
                failed = True
                logger.error(
                    "Workflow %s step [%d/%d] %s: failed - %s",
                    workflow_name,
                    i + 1,
                    len(self._steps),
                    step.name,
                    e,
                )

                # Attempt rollback of completed steps in reverse order
                for rollback_step, _ in reversed(completed_steps):
                    try:
                        await rollback_step.rollback(ctx)
                        logger.info(
                            "Workflow %s step %s: rollback completed",
                            workflow_name,
                            rollback_step.name,
                        )
                    except Exception as re:
                        logger.error(
                            "Workflow %s step %s: rollback failed - %s",
                            workflow_name,
                            rollback_step.name,
                            re,
                        )

                execution.status = "failed"
                execution.finished_at = datetime.now(timezone.utc)
                execution.error_message = f"Step '{step.name}' failed: {e}"
                await self._session.commit()

        if not failed:
            execution.status = "completed"
            execution.finished_at = datetime.now(timezone.utc)
            await self._session.commit()
            logger.info("Workflow %s: completed successfully", workflow_name)

        await self._session.refresh(execution)
        return execution

    async def get_execution(self, execution_id: int) -> ArgusWorkflowExecution | None:
        """Look up a workflow execution by ID."""
        result = await self._session.execute(
            select(ArgusWorkflowExecution).where(
                ArgusWorkflowExecution.id == execution_id
            )
        )
        return result.scalars().first()

    async def get_step_executions(
        self, execution_id: int
    ) -> list[ArgusWorkflowStepExecution]:
        """Get all step executions for a workflow execution, ordered by step_order."""
        result = await self._session.execute(
            select(ArgusWorkflowStepExecution)
            .where(ArgusWorkflowStepExecution.execution_id == execution_id)
            .order_by(ArgusWorkflowStepExecution.step_order)
        )
        return list(result.scalars().all())
