"""SQLAlchemy ORM models for workflow execution tracking.

Tracks the execution state of workspace provisioning workflows:
- ArgusWorkflowExecution: A single workflow run tied to a workspace.
- ArgusWorkflowStepExecution: Individual step results within a workflow run.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class ArgusWorkflowExecution(Base):
    """Workflow execution record.

    Tracks one complete workflow run for a workspace (e.g., "workspace-provision").
    Each execution contains multiple step executions.

    Columns:
        id:            Auto-incremented primary key.
        workspace_id:  FK to the workspace being provisioned.
        workflow_name: Identifier for the workflow definition (e.g., "workspace-provision").
        status:        Overall status ("pending", "running", "completed", "failed", "cancelled").
        started_at:    When the workflow execution began.
        finished_at:   When the workflow execution ended (success or failure).
        error_message: Summary error message if the workflow failed.
        created_at:    Record creation timestamp.
    """

    __tablename__ = "argus_workflow_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("argus_workspaces.id"), nullable=False)
    workflow_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ArgusWorkflowStepExecution(Base):
    """Individual step execution within a workflow.

    Each row represents the execution of one step in the workflow pipeline.
    Steps are executed sequentially by the WorkflowExecutor and their
    results are persisted here for monitoring and debugging.

    Columns:
        id:             Auto-incremented primary key.
        execution_id:   FK to the parent workflow execution.
        step_name:      Unique step identifier (e.g., "gitlab-create-project").
        step_order:     Execution order (0-based).
        status:         Step status ("pending", "running", "completed", "failed", "skipped").
        started_at:     When this step began executing.
        finished_at:    When this step finished.
        error_message:  Error details if the step failed.
        result_data:    JSON string with step-specific output data.
    """

    __tablename__ = "argus_workflow_step_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(
        Integer, ForeignKey("argus_workflow_executions.id"), nullable=False
    )
    step_name = Column(String(100), nullable=False)
    step_order = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    result_data = Column(Text)
