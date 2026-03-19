"""SQLAlchemy ORM models for infrastructure configuration."""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base


class ArgusConfiguration(Base):
    """Infrastructure configuration (key-value pairs).

    Categories group related settings together (e.g. 'network').
    """

    __tablename__ = "argus_configuration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(String(500), nullable=False, default="")
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
