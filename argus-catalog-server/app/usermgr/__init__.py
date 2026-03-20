"""User management module.

Provides CRUD operations for user accounts and role management.
This module follows the standard router/schemas/service pattern:

- router.py  : FastAPI API endpoints (HTTP handlers).
- schemas.py : Pydantic request/response models and enums.
- service.py : Business logic and database operations.
- models.py  : SQLAlchemy ORM model definitions (ArgusUser, ArgusRole).

Key features:
- User CRUD (create, read, update, delete) with paginated listing.
- Role-based access control (Admin, User roles).
- Account status management (activate/deactivate).
- Uniqueness validation for username and email.
- Password hashing using SHA-256.
"""
