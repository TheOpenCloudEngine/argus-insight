"""SQLAlchemy ORM model for VS Code Server instances."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class ArgusVscodeInstance(Base):
    """VS Code Server instance tracking table.

    Each user can have at most one VS Code Server instance (code-server)
    deployed on K3s. The instance is accessed via a unique hostname and
    authenticated through Nginx Ingress auth-url subrequest.

    Columns:
        id:             Auto-incremented primary key.
        user_id:        FK to argus_users.id. UNIQUE — one instance per user.
        username:       Cached username for hostname construction.
        domain:         Domain suffix (e.g. "dev.net").
        k8s_namespace:  Kubernetes namespace (default: "argus-vscode").
        hostname:       Full hostname (e.g. argus-vscode-admin.argus-insight.dev.net).
        status:         deploying | running | failed | deleting | deleted.
        created_at:     Timestamp when the instance record was created.
        updated_at:     Timestamp of last status change.
    """

    __tablename__ = "argus_vscode_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("argus_users.id"), nullable=False, unique=True
    )
    username = Column(String(100), nullable=False)
    domain = Column(String(255), nullable=False)
    k8s_namespace = Column(String(255), nullable=False, default="argus-vscode")
    hostname = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="deploying")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
