"""SQLAlchemy ORM models for workspace management.

Defines the database schema for workspaces, membership, and credentials:
- ArgusWorkspace: Workspace definitions with K8s cluster binding.
- ArgusWorkspaceMember: Many-to-many relationship between users and workspaces with roles.
- ArgusWorkspaceCredential: Service credentials and connection info generated during provisioning.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, func

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
        kserve_endpoint: KServe gateway URL (e.g., "kserve-ml-team-dev.argus-insight.dev.net").
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
    kserve_endpoint = Column(String(500))
    status = Column(String(20), nullable=False, default="provisioning")
    resource_profile_id = Column(
        Integer, ForeignKey("argus_resource_profiles.id", ondelete="SET NULL"),
    )
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
    gitlab_access_token = Column(String(255))   # Per-user GitLab project access token
    gitlab_token_name = Column(String(100))     # Token name (e.g. "argus-admin-mlteamdev")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ArgusWorkspaceCredential(Base):
    """Workspace credential and connection info table.

    Stores all service credentials and connection details generated during
    workspace provisioning. The primary key is the workspace_id itself
    (one credential record per workspace).

    Columns:
        workspace_id:       PK + FK to argus_workspaces.id.
        gitlab_http_url:    GitLab HTTP clone URL.
        gitlab_ssh_url:     GitLab SSH clone URL.
        minio_endpoint:     MinIO internal K8s service endpoint.
        minio_root_user:    MinIO root admin username.
        minio_root_password: MinIO root admin password.
        minio_access_key:   Workspace admin S3 access key.
        minio_secret_key:   Workspace admin S3 secret key.
        airflow_url:        Airflow webserver external URL.
        airflow_admin_username: Airflow admin username.
        airflow_admin_password: Airflow web UI admin password.
        mlflow_artifact_bucket: MinIO bucket for MLflow artifacts.
        kserve_endpoint:    KServe gateway external URL.
        created_at:         Timestamp when credentials were stored.
        updated_at:         Timestamp of last modification.
    """

    __tablename__ = "argus_workspace_credentials"

    workspace_id = Column(
        Integer, ForeignKey("argus_workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    gitlab_http_url = Column(String(500))
    gitlab_ssh_url = Column(String(500))
    minio_endpoint = Column(String(500))
    minio_root_user = Column(String(255))
    minio_root_password = Column(String(500))
    minio_access_key = Column(String(255))
    minio_secret_key = Column(String(500))
    airflow_url = Column(String(500))
    airflow_admin_username = Column(String(255))
    airflow_admin_password = Column(String(500))
    mlflow_artifact_bucket = Column(String(255))
    kserve_endpoint = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusWorkspacePipeline(Base):
    """Workspace-Pipeline association table.

    A workspace can use multiple pipelines, and each pipeline can be
    used by multiple workspaces. Tracks deployment order and status.

    Columns:
        id:            Auto-incremented primary key.
        workspace_id:  FK to argus_workspaces.id.
        pipeline_id:   FK to argus_pipelines.id.
        deploy_order:  Order in which pipelines are deployed (0-based).
        status:        Deployment status (pending, running, completed, failed).
        created_at:    Timestamp when the association was created.
    """

    __tablename__ = "argus_workspace_pipelines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("argus_workspaces.id", ondelete="CASCADE"), nullable=False)
    pipeline_id = Column(Integer, ForeignKey("argus_pipelines.id"), nullable=False)
    deploy_order = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ArgusWorkspaceService(Base):
    """Service instances deployed to a workspace.

    Each row represents one plugin/service deployed to a workspace.
    UNIQUE(workspace_id, plugin_name) ensures one service per plugin per workspace.
    """

    __tablename__ = "argus_workspace_services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("argus_workspaces.id", ondelete="CASCADE"), nullable=False)
    plugin_name = Column(String(100), nullable=False)
    service_id = Column(String(20))  # timestamp hex + random (e.g., "67e8a400a3f1")
    display_name = Column(String(255))
    version = Column(String(50))
    endpoint = Column(String(500))
    username = Column(String(255))
    password = Column(String(255))
    access_token = Column(String(500))
    status = Column(String(20), nullable=False, default="running")
    metadata_json = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusWorkspaceAuditLog(Base):
    """Audit log for workspace member and lifecycle events."""

    __tablename__ = "argus_workspace_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False)
    workspace_name = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    target_user_id = Column(Integer)
    target_username = Column(String(100))
    actor_user_id = Column(Integer)
    actor_username = Column(String(100))
    detail = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
