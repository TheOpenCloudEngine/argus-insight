"""Pydantic schemas for workspace provisioning API.

Request/response models for workspace CRUD, membership management,
and workflow execution status queries.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from workspace_provisioner.config import ProvisioningConfig


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkspaceStatus(str, Enum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"


class WorkspaceMemberRole(str, Enum):
    WORKSPACE_ADMIN = "WorkspaceAdmin"
    USER = "User"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Workspace request schemas
# ---------------------------------------------------------------------------

class WorkspaceCreateRequest(BaseModel):
    """Request to create a new workspace and trigger provisioning workflow."""

    name: str = Field(
        ..., min_length=1, max_length=100,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description="Workspace slug name (lowercase alphanumeric + hyphens)",
    )
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    domain: str = Field(
        ..., min_length=1, max_length=255,
        description="Domain suffix (e.g., 'dev.net')",
    )
    k8s_cluster: str | None = Field(
        None, max_length=255,
        description="Kubernetes cluster name or kubeconfig context",
    )
    k8s_namespace: str | None = Field(
        None, max_length=255,
        description="Kubernetes namespace for workspace resources",
    )
    admin_user_id: int = Field(
        ..., description="User ID to assign as WorkspaceAdmin",
    )
    provisioning_config: ProvisioningConfig = Field(
        default_factory=ProvisioningConfig,
        description="Service-level provisioning settings (images, storage sizes, resources). "
        "Fields not provided will use platform defaults.",
    )
    steps: list[str] | None = Field(
        default=None,
        description="If provided, only these steps will be executed during provisioning. "
        "Steps not in this list are skipped. Pass null or omit to run all steps. "
        "Available step names: gitlab-create-project, minio-deploy, minio-setup, "
        "airflow-deploy, mlflow-deploy, kserve-deploy, custom-hook.",
    )


class WorkspaceMemberAddRequest(BaseModel):
    """Request to add a member to a workspace."""

    user_id: int
    role: WorkspaceMemberRole = WorkspaceMemberRole.USER


# ---------------------------------------------------------------------------
# Workspace response schemas
# ---------------------------------------------------------------------------

class WorkspaceMemberResponse(BaseModel):
    id: int
    workspace_id: int
    user_id: int
    role: str
    created_at: datetime


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: str | None = None
    domain: str
    k8s_cluster: str | None = None
    k8s_namespace: str | None = None
    gitlab_project_id: int | None = None
    gitlab_project_url: str | None = None
    minio_endpoint: str | None = None
    minio_console_endpoint: str | None = None
    minio_default_bucket: str | None = None
    airflow_endpoint: str | None = None
    mlflow_endpoint: str | None = None
    kserve_endpoint: str | None = None
    status: WorkspaceStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class WorkspaceCredentialResponse(BaseModel):
    """Credential and connection info generated during provisioning."""

    workspace_id: int
    gitlab_http_url: str | None = None
    gitlab_ssh_url: str | None = None
    minio_endpoint: str | None = None
    minio_root_user: str | None = None
    minio_root_password: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    airflow_url: str | None = None
    airflow_admin_username: str | None = None
    airflow_admin_password: str | None = None
    mlflow_artifact_bucket: str | None = None
    kserve_endpoint: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedWorkspaceResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Workflow status response schemas
# ---------------------------------------------------------------------------

class StepExecutionResponse(BaseModel):
    id: int
    step_name: str
    step_order: int
    status: StepStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    result_data: str | None = None


class WorkflowExecutionResponse(BaseModel):
    id: int
    workspace_id: int
    workflow_name: str
    status: WorkflowStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    steps: list[StepExecutionResponse] = []
