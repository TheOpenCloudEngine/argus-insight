"""SQLAlchemy ORM models for user management.

Defines the database schema for the user management module:
- ArgusRole: Role definitions with role_id identifier (e.g., argus-admin).
- ArgusUser: User accounts linked to roles via foreign key.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class ArgusRole(Base):
    """Role table.

    Columns:
        id:          Auto-incremented primary key.
        role_id:     Unique role identifier matching Keycloak realm role names
                     (e.g., "argus-admin", "argus-superuser", "argus-user").
        name:        Display name (e.g., "Admin", "Superuser", "User").
        description: Optional description of the role's permissions.
        created_at:  Timestamp when the role was created.
        updated_at:  Timestamp of the last modification.
    """

    __tablename__ = "argus_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(String(50), nullable=False, unique=True)
    name = Column(String(50), nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusUser(Base):
    """User table. Stores user identity, credentials, and status.

    Columns:
        id:            Auto-incremented primary key.
        username:      Unique login identifier.
        email:         Unique email address.
        first_name:    User's first (given) name.
        last_name:     User's last (family) name.
        phone_number:  Optional contact phone number.
        password_hash: SHA-256 hash of the user's password.
        status:        Account status ("active" or "inactive").
        role_id:       Foreign key to argus_roles.id.
        created_at:    Timestamp when the account was created.
        updated_at:    Timestamp of the last profile modification.
    """

    __tablename__ = "argus_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(30))
    password_hash = Column(String(255), nullable=False, default="")
    status = Column(String(20), nullable=False, default="active")
    auth_type = Column(String(20), nullable=False, default="local")  # "local" or "keycloak"
    s3_access_key = Column(String(100))   # MinIO per-user access key
    s3_secret_key = Column(String(100))   # MinIO per-user secret key
    s3_bucket = Column(String(255))       # MinIO bucket name (e.g. "user-admin")
    role_id = Column(Integer, ForeignKey("argus_roles.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
