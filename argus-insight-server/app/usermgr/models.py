"""SQLAlchemy ORM models for user management."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class ArgusRole(Base):
    """Role table. Defines user roles (Admin, User, etc.)."""

    __tablename__ = "argus_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusUser(Base):
    """User table. Stores user identity, credentials, and status."""

    __tablename__ = "argus_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(30))
    password_hash = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    role_id = Column(Integer, ForeignKey("argus_roles.id"), nullable=False)
    group_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
