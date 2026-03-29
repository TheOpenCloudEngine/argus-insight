"""Step-based Workflow Engine for workspace provisioning.

Provides the core abstractions for defining and executing multi-step workflows:
- WorkflowStep: Abstract base class for individual steps.
- WorkflowContext: Shared state passed between steps.
- WorkflowExecutor: Runs a sequence of steps, writing progress to audit logs.

Steps are executed sequentially. Each step can read/write to the shared context,
allowing later steps to use outputs from earlier steps (e.g., GitLab project ID).

Usage:
    executor = WorkflowExecutor(session)
    executor.add_step(GitLabCreateProjectStep())
    executor.add_step(MinioCreateBucketStep())
    await executor.run(workspace_id=1, workflow_name="workspace-provision")
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from workspace_provisioner.models import ArgusWorkspaceAuditLog

logger = logging.getLogger(__name__)


class WorkflowContext:
    """Shared mutable state for a workflow execution.

    Steps read inputs and write outputs through this context object.
    The context is initialized with workspace metadata and accumulates
    results as each step completes.
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
    - teardown(): Called during workspace deletion to remove resources.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique step identifier."""

    @abstractmethod
    async def execute(self, ctx: WorkflowContext) -> dict | None:
        """Execute the step."""

    async def rollback(self, ctx: WorkflowContext) -> None:
        """Rollback this step's changes. Called on workflow failure."""

    async def teardown(self, ctx: WorkflowContext) -> dict | None:
        """Tear down resources created by this step during workspace deletion."""
        await self.rollback(ctx)
        return None


@dataclass
class StepResult:
    """Result of a single step execution."""
    step_name: str
    step_order: int
    status: str  # "completed", "failed", "skipped"
    error_message: str | None = None


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    status: str  # "completed", "failed"
    error_message: str | None = None
    steps: list[StepResult] = field(default_factory=list)


class WorkflowExecutor:
    """Executes a sequence of WorkflowSteps, tracking progress via audit logs.

    Steps are added via add_step() and executed in order by run().
    Progress is recorded to argus_workspace_audit_logs for monitoring.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._steps: list[WorkflowStep] = []

    def add_step(self, step: WorkflowStep) -> "WorkflowExecutor":
        """Add a step to the workflow pipeline. Returns self for chaining."""
        self._steps.append(step)
        return self

    async def _audit(
        self, ctx: WorkflowContext, action: str, detail: dict | None = None,
    ) -> None:
        """Write an audit log entry for a workflow event."""
        entry = ArgusWorkspaceAuditLog(
            workspace_id=ctx.workspace_id,
            workspace_name=ctx.workspace_name,
            action=action,
            detail=detail,
        )
        self._session.add(entry)
        await self._session.commit()

    async def run(
        self,
        workspace_id: int,
        workflow_name: str,
        ctx: WorkflowContext,
        include_steps: list[str] | None = None,
    ) -> WorkflowResult:
        """Execute all steps sequentially.

        If a step fails, subsequent steps are skipped and rollback is
        attempted for completed steps. Progress is recorded via audit logs.
        """
        include_set: set[str] | None = set(include_steps) if include_steps else None
        started_at = datetime.now(timezone.utc)

        step_names = [s.name for s in self._steps]
        await self._audit(ctx, "workflow_started", {
            "workflow_name": workflow_name,
            "steps": step_names,
        })

        completed_steps: list[WorkflowStep] = []
        result = WorkflowResult(status="completed")
        failed = False

        for i, step in enumerate(self._steps):
            if failed:
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="skipped",
                ))
                continue

            if include_set is not None and step.name not in include_set:
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="skipped",
                ))
                logger.info(
                    "Workflow %s step [%d/%d] %s: skipped (not in include_steps)",
                    workflow_name, i + 1, len(self._steps), step.name,
                )
                continue

            logger.info(
                "Workflow %s step [%d/%d] %s: starting",
                workflow_name, i + 1, len(self._steps), step.name,
            )

            await self._audit(ctx, "step_started", {
                "workflow_name": workflow_name,
                "step_name": step.name,
                "step_order": i,
            })

            try:
                step_result = await step.execute(ctx)
                completed_steps.append(step)
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="completed",
                ))
                logger.info(
                    "Workflow %s step [%d/%d] %s: completed",
                    workflow_name, i + 1, len(self._steps), step.name,
                )
                await self._audit(ctx, "step_completed", {
                    "workflow_name": workflow_name,
                    "step_name": step.name,
                    "step_order": i,
                })
            except Exception as e:
                failed = True
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="failed",
                    error_message=str(e),
                ))
                logger.error(
                    "Workflow %s step [%d/%d] %s: failed - %s",
                    workflow_name, i + 1, len(self._steps), step.name, e,
                )

                await self._audit(ctx, "step_failed", {
                    "workflow_name": workflow_name,
                    "step_name": step.name,
                    "step_order": i,
                    "error": str(e),
                })

                # Attempt rollback of completed steps in reverse order
                for rollback_step in reversed(completed_steps):
                    try:
                        await rollback_step.rollback(ctx)
                        logger.info("Workflow %s step %s: rollback completed",
                                    workflow_name, rollback_step.name)
                    except Exception as re:
                        logger.error("Workflow %s step %s: rollback failed - %s",
                                     workflow_name, rollback_step.name, re)

                duration = (datetime.now(timezone.utc) - started_at).total_seconds()
                result.status = "failed"
                result.error_message = f"Step '{step.name}' failed: {e}"
                await self._audit(ctx, "workflow_failed", {
                    "workflow_name": workflow_name,
                    "failed_step": step.name,
                    "error": str(e),
                    "steps_completed": len(completed_steps),
                    "steps_total": len(self._steps),
                    "duration_sec": int(duration),
                })

        if not failed:
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.info("Workflow %s: completed successfully", workflow_name)
            await self._audit(ctx, "workflow_completed", {
                "workflow_name": workflow_name,
                "steps_completed": len(completed_steps),
                "duration_sec": int(duration),
            })

        return result

    async def run_teardown(
        self,
        workspace_id: int,
        workflow_name: str,
        ctx: WorkflowContext,
        include_steps: list[str] | None = None,
    ) -> WorkflowResult:
        """Execute teardown for all steps in reverse order (best-effort).

        Unlike run(), teardown continues executing remaining steps even if
        one fails. This ensures maximum cleanup.
        """
        include_set: set[str] | None = set(include_steps) if include_steps else None
        started_at = datetime.now(timezone.utc)
        steps_reversed = list(reversed(self._steps))

        step_names = [s.name for s in steps_reversed]
        await self._audit(ctx, "workflow_started", {
            "workflow_name": workflow_name,
            "steps": step_names,
        })

        result = WorkflowResult(status="completed")
        failed_steps: list[str] = []

        for i, step in enumerate(steps_reversed):
            if include_set is not None and step.name not in include_set:
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="skipped",
                ))
                logger.info(
                    "Workflow %s step [%d/%d] %s: skipped (not in include_steps)",
                    workflow_name, i + 1, len(steps_reversed), step.name,
                )
                continue

            logger.info(
                "Workflow %s step [%d/%d] %s: tearing down",
                workflow_name, i + 1, len(steps_reversed), step.name,
            )

            await self._audit(ctx, "step_started", {
                "workflow_name": workflow_name,
                "step_name": step.name,
                "step_order": i,
            })

            try:
                await step.teardown(ctx)
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="completed",
                ))
                logger.info(
                    "Workflow %s step [%d/%d] %s: teardown completed",
                    workflow_name, i + 1, len(steps_reversed), step.name,
                )
                await self._audit(ctx, "step_completed", {
                    "workflow_name": workflow_name,
                    "step_name": step.name,
                    "step_order": i,
                })
            except Exception as e:
                failed_steps.append(step.name)
                result.steps.append(StepResult(
                    step_name=step.name, step_order=i, status="failed",
                    error_message=str(e),
                ))
                logger.error(
                    "Workflow %s step [%d/%d] %s: teardown failed - %s "
                    "(continuing with remaining steps)",
                    workflow_name, i + 1, len(steps_reversed), step.name, e,
                )
                await self._audit(ctx, "step_failed", {
                    "workflow_name": workflow_name,
                    "step_name": step.name,
                    "step_order": i,
                    "error": str(e),
                })

        duration = (datetime.now(timezone.utc) - started_at).total_seconds()
        if failed_steps:
            result.status = "failed"
            result.error_message = f"Teardown failed for steps: {', '.join(failed_steps)}"
            await self._audit(ctx, "workflow_failed", {
                "workflow_name": workflow_name,
                "failed_steps": failed_steps,
                "steps_completed": len(steps_reversed) - len(failed_steps),
                "steps_total": len(steps_reversed),
                "duration_sec": int(duration),
            })
        else:
            logger.info("Workflow %s: teardown completed successfully", workflow_name)
            await self._audit(ctx, "workflow_completed", {
                "workflow_name": workflow_name,
                "steps_completed": len(steps_reversed),
                "duration_sec": int(duration),
            })

        return result
