"""SQLAlchemy models for plugin configuration.

Stores admin-configured plugin settings such as enabled state,
execution order, selected version, and default configuration overrides.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.core.database import Base


class ArgusPipeline(Base):
    """Named deployment pipeline."""

    __tablename__ = "argus_pipelines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)  # slug: "ml-team-pipeline"
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    is_default = Column(Boolean, default=False)
    version = Column(Integer, nullable=False, default=1)
    deleted = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(100))  # username of the creator
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return (
            f"<ArgusPipeline(name={self.name!r}, "
            f"display_name={self.display_name!r}, default={self.is_default})>"
        )


class ArgusPluginConfig(Base):
    """Admin-configured plugin settings.

    Stores which plugins are enabled, their execution order,
    selected version, and default configuration overrides.
    """

    __tablename__ = "argus_plugin_configs"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "plugin_name", name="uq_pipeline_plugin"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_id = Column(
        Integer,
        ForeignKey("argus_pipelines.id", ondelete="CASCADE"),
        nullable=True,
    )
    plugin_name = Column(String(100), nullable=False)  # "airflow-deploy"
    enabled = Column(Boolean, default=True)
    display_order = Column(Integer, nullable=False)  # admin-specified order
    selected_version = Column(String(50))  # "1.2" — null means default
    default_config = Column(JSON)  # default config overrides as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return (
            f"<ArgusPluginConfig(name={self.plugin_name!r}, "
            f"enabled={self.enabled}, order={self.display_order})>"
        )
