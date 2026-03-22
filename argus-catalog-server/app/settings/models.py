"""Settings ORM models."""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class CatalogConfiguration(Base):
    """Key-value configuration storage.

    Stores dynamic configuration that can be changed at runtime via the
    Settings API. Used for Object Storage (MinIO/S3) settings, etc.
    """

    __tablename__ = "catalog_configuration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(String(500), nullable=False, default="")
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
