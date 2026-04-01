"""SQLAlchemy ORM model for resource profiles."""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, Numeric, String, Text, func

from app.core.database import Base


class ArgusResourceProfile(Base):
    """Resource profile defining CPU/Memory limits for a workspace.

    Columns:
        id:           Auto-incremented primary key.
        name:         Unique profile slug (e.g. "small", "medium", "large").
        display_name: Human-readable name (e.g. "Small", "Medium", "Large").
        description:  Optional description.
        cpu_cores:    Total CPU cores allowed (e.g. 8.000).
        memory_mb:    Total memory in MiB (e.g. 16384 for 16 GiB).
        is_default:   Whether this is the default profile for new workspaces.
        created_at:   Timestamp when the profile was created.
        updated_at:   Timestamp of the last modification.
    """

    __tablename__ = "argus_resource_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    cpu_cores = Column(Numeric(10, 3), nullable=False)
    memory_mb = Column(BigInteger, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
