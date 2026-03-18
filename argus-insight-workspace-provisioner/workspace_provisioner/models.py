"""SQLAlchemy ORM models for workspace management.

Defines the database schema for workspaces and membership:
- ArgusWorkspace: Workspace definitions with K8s cluster binding.
- ArgusWorkspaceMember: Many-to-many relationship between users and workspaces with roles.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class ArgusWorkspace(Base):
    """Workspace table.

    Each workspace represents an isolated environment with its own set of
    services (Airflow, MLflow, VS Code, Jupyter, Trino, MinIO, etc.) deployed
    on a designated Kubernetes cluster.

    Columns:
        id:           Auto-incremented primary key.
        name:         Unique workspace identifier (e.g., "ml-team-dev"). Max 100 chars.
        display_name: Human-readable workspace name. Max 255 chars.
        description:  Optional description of the workspace purpose.
        domain:       Domain suffix for service URLs (e.g., "dev.net").
        k8s_cluster:  Kubernetes cluster name or kubeconfig context for this workspace.
        k8s_namespace: Kubernetes namespace for workspace resources.
        gitlab_project_id: GitLab project ID created for this workspace (set after provisioning).
        gitlab_project_url: GitLab project URL (e.g., "https://gitlab-global.argus-insight.dev.net/workspaces/ml-team-dev").
        minio_endpoint: MinIO API endpoint URL (e.g., "minio-ml-team-dev.argus-insight.dev.net").
        minio_console_endpoint: MinIO console URL (e.g., "minio-console-ml-team-dev.argus-insight.dev.net").
        minio_default_bucket: Default bucket name (same as workspace name).
        airflow_endpoint: Airflow webserver URL (e.g., "airflow-ml-team-dev.argus-insight.dev.net").
        mlflow_endpoint: MLflow tracking server URL (e.g., "mlflow-ml-team-dev.argus-insight.dev.net").
        status:       Workspace status ("provisioning", "active", "failed", "deleting", "deleted").
        created_by:   User ID of the admin who created this workspace.
        created_at:   Timestamp when the workspace was created.
        updated_at:   Timestamp of the last modification.
    """

    __tablename__ = "argus_workspaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    domain = Column(String(255), nullable=False)
    k8s_cluster = Column(String(255))
    k8s_namespace = Column(String(255))
    gitlab_project_id = Column(Integer)
    gitlab_project_url = Column(String(500))
    minio_endpoint = Column(String(500))
    minio_console_endpoint = Column(String(500))
    minio_default_bucket = Column(String(255))
    airflow_endpoint = Column(String(500))
    mlflow_endpoint = Column(String(500))
    status = Column(String(20), nullable=False, default="provisioning")
    created_by = Column(Integer, ForeignKey("argus_users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusWorkspaceMember(Base):
    """Workspace membership table.

    Maps users to workspaces with a specific role. A user can belong to
    multiple workspaces, and each workspace can have multiple members.

    Columns:
        id:           Auto-incremented primary key.
        workspace_id: FK to argus_workspaces.id.
        user_id:      FK to argus_users.id.
        role:         Member role within the workspace ("WorkspaceAdmin" or "User").
        created_at:   Timestamp when membership was granted.
    """

    __tablename__ = "argus_workspace_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("argus_workspaces.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("argus_users.id"), nullable=False)
    role = Column(String(50), nullable=False, default="User")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
