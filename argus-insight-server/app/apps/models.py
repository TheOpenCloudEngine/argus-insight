"""SQLAlchemy ORM models for the app platform.

- ArgusApp: App catalog (registry of deployable app types).
- ArgusAppInstance: Per-user running instances of apps.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class ArgusApp(Base):
    """App catalog — defines available app types (vscode, jupyter, etc.)."""

    __tablename__ = "argus_apps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_type = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(String(500))
    icon = Column(String(50))
    template_dir = Column(String(100), nullable=False)
    default_namespace = Column(String(255), nullable=False, default="argus-apps")
    hostname_pattern = Column(String(255), nullable=False, default="argus-{app_type}-{instance_id}.{domain}")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusAppInstance(Base):
    """Per-user running instance of an app.

    One user can have multiple instances of the same app type.
    Each instance gets a unique short_id (8-char hex from UUID4).
    """

    __tablename__ = "argus_app_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(8), nullable=False, unique=True)
    app_id = Column(Integer, ForeignKey("argus_apps.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("argus_users.id"), nullable=False)
    username = Column(String(100), nullable=False)
    app_type = Column(String(50), nullable=False)
    domain = Column(String(255), nullable=False)
    k8s_namespace = Column(String(255), nullable=False)
    hostname = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="deploying")
    config = Column(Text)
    deploy_steps = Column(Text)  # JSON array of {step, status, message}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
