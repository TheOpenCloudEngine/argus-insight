"""SQLAlchemy ORM models for user management.

Defines the database schema for the user management module:
- ArgusRole: Role definitions (e.g., Admin, User) stored in `argus_roles`.
- ArgusUser: User accounts stored in `argus_users`, linked to roles via foreign key.

Both tables include automatic timestamp management:
- created_at: Set to the current time on row insertion (server-side default).
- updated_at: Set to the current time on every update (onupdate trigger).
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class ArgusRole(Base):
    """Role table. Defines user roles (Admin, User, etc.).

    Each role has a unique name and an optional description. Users reference
    roles via the `role_id` foreign key in the `argus_users` table.

    Columns:
        id:          Auto-incremented primary key.
        name:        Unique role name (e.g., "Admin", "User"). Max 50 chars.
        description: Optional human-readable description of the role's permissions.
        created_at:  Timestamp when the role was created (auto-set by DB).
        updated_at:  Timestamp of the last modification (auto-updated by DB).
    """

    __tablename__ = "argus_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusUser(Base):
    """User table. Stores user identity, credentials, and status.

    Represents a platform user account. Each user has a unique username and
    email, belongs to exactly one role, and has an account status (active/inactive).

    Columns:
        id:            Auto-incremented primary key.
        username:      Unique login identifier. Max 100 chars. Cannot be changed after creation.
        email:         Unique email address. Max 255 chars.
        first_name:    User's first (given) name. Max 100 chars.
        last_name:     User's last (family) name. Max 100 chars.
        phone_number:  Optional contact phone number. Max 30 chars.
        password_hash: SHA-256 hash of the user's password. Never stored in plaintext.
        status:        Account status ("active" or "inactive"). Defaults to "active".
        role_id:       Foreign key to `argus_roles.id`. Determines the user's permission level.
        created_at:    Timestamp when the account was created (auto-set by DB).
        updated_at:    Timestamp of the last profile modification (auto-updated by DB).
    """

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
