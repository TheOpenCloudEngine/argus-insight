"""Authentication endpoints — supports Keycloak OIDC and Local JWT."""

import hashlib
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt as jose_jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    CurrentUser, TokenUser, _build_token_user, create_local_token,
)
from app.core.config import settings
from app.core.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfoResponse(BaseModel):
    sub: str
    username: str
    email: str
    first_name: str
    last_name: str
    roles: list[str]
    realm_roles: list[str]
    role: str
    is_admin: bool
    is_superuser: bool


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_url() -> str:
    return (
        f"{settings.auth_keycloak_server_url}"
        f"/realms/{settings.auth_keycloak_realm}"
        f"/protocol/openid-connect/token"
    )


def _logout_url() -> str:
    return (
        f"{settings.auth_keycloak_server_url}"
        f"/realms/{settings.auth_keycloak_realm}"
        f"/protocol/openid-connect/logout"
    )


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256 (matches usermgr/service.py)."""
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Authenticate a user. Routes to Keycloak or local DB based on auth_type."""
    if settings.auth_type == "local":
        return await _login_local(req, session)
    return await _login_keycloak(req)


async def _login_local(req: LoginRequest, session: AsyncSession) -> TokenResponse:
    """Authenticate against local argus_users table."""
    from app.usermgr.models import ArgusRole, ArgusUser

    result = await session.execute(
        select(ArgusUser, ArgusRole.name.label("role_name"))
        .join(ArgusRole, ArgusUser.role_id == ArgusRole.id)
        .where(ArgusUser.username == req.username)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    user, role_name = row

    if user.password_hash != _hash_password(req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    # Create JWT tokens
    access_token = create_local_token(
        sub=str(user.id),
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role_name,
    )
    # Refresh token — longer expiry
    refresh_token = create_local_token(
        sub=str(user.id),
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role_name,
        expire_minutes=60 * 24 * 7,  # 7 days
    )

    logger.info("Local login: %s (role=%s)", user.username, role_name)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=480 * 60,
        refresh_expires_in=60 * 24 * 7 * 60,
    )


async def _login_keycloak(req: LoginRequest) -> TokenResponse:
    """Authenticate via Keycloak token endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _token_url(),
            data={
                "grant_type": "password",
                "client_id": settings.auth_keycloak_client_id,
                "client_secret": settings.auth_keycloak_client_secret,
                "username": req.username,
                "password": req.password,
            },
        )

    if resp.status_code != 200:
        detail = "Invalid username or password"
        try:
            err = resp.json()
            if err.get("error_description"):
                detail = err["error_description"]
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    data = resp.json()

    # Check if user has an argus-* role
    payload = jose_jwt.get_unverified_claims(data["access_token"])
    token_user = _build_token_user(payload)
    if not token_user.has_argus_role:
        async with httpx.AsyncClient() as client:
            await client.post(
                _logout_url(),
                data={
                    "client_id": settings.auth_keycloak_client_id,
                    "client_secret": settings.auth_keycloak_client_secret,
                    "refresh_token": data["refresh_token"],
                },
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Argus role assigned. Contact your administrator to request access.",
        )

    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        token_type=data["token_type"],
        expires_in=data["expires_in"],
        refresh_expires_in=data["refresh_expires_in"],
    )


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, session: AsyncSession = Depends(get_session)):
    """Refresh an access token."""
    if settings.auth_type == "local":
        return await _refresh_local(req, session)
    return await _refresh_keycloak(req)


async def _refresh_local(req: RefreshRequest, session: AsyncSession) -> TokenResponse:
    """Refresh a local JWT by verifying the refresh token and issuing new tokens."""
    from app.core.auth import _verify_token_local
    from app.usermgr.models import ArgusRole, ArgusUser

    try:
        payload = _verify_token_local(req.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token. Please login again.",
        )

    # Re-fetch user to get current role/status
    user_id = int(payload.get("sub", "0"))
    result = await session.execute(
        select(ArgusUser, ArgusRole.name.label("role_name"))
        .join(ArgusRole, ArgusUser.role_id == ArgusRole.id)
        .where(ArgusUser.id == user_id)
    )
    row = result.first()
    if not row or row[0].status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or inactive")

    user, role_name = row

    access_token = create_local_token(
        sub=str(user.id), username=user.username, email=user.email,
        first_name=user.first_name, last_name=user.last_name, role=role_name,
    )
    refresh_token = create_local_token(
        sub=str(user.id), username=user.username, email=user.email,
        first_name=user.first_name, last_name=user.last_name, role=role_name,
        expire_minutes=60 * 24 * 7,
    )

    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token,
        token_type="bearer", expires_in=480 * 60, refresh_expires_in=60 * 24 * 7 * 60,
    )


async def _refresh_keycloak(req: RefreshRequest) -> TokenResponse:
    """Refresh via Keycloak token endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _token_url(),
            data={
                "grant_type": "refresh_token",
                "client_id": settings.auth_keycloak_client_id,
                "client_secret": settings.auth_keycloak_client_secret,
                "refresh_token": req.refresh_token,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh token. Please login again.",
        )

    data = resp.json()
    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        token_type=data["token_type"],
        expires_in=data["expires_in"],
        refresh_expires_in=data["refresh_expires_in"],
    )


# ---------------------------------------------------------------------------
# User info
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserInfoResponse)
async def get_me(user: CurrentUser):
    """Get the current authenticated user's information."""
    return UserInfoResponse(
        sub=user.sub,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=user.roles,
        realm_roles=user.realm_roles,
        role=user.role,
        is_admin=user.is_admin,
        is_superuser=user.is_superuser,
    )


# ---------------------------------------------------------------------------
# Change password (Local mode only)
# ---------------------------------------------------------------------------

@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Change the current user's password. Local auth only."""
    if settings.auth_type != "local":
        raise HTTPException(status_code=400, detail="Password change is only available in local auth mode")

    from app.usermgr.models import ArgusUser

    result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == int(current_user.sub))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.password_hash != _hash_password(req.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = _hash_password(req.new_password)
    await session.commit()
    logger.info("Password changed for user: %s", user.username)
    return {"status": "ok", "message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout(req: LogoutRequest):
    """Logout by invalidating the refresh token."""
    if settings.auth_type == "local":
        # Local mode: token is stateless, nothing to invalidate
        return {"detail": "Logged out successfully"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _logout_url(),
            data={
                "client_id": settings.auth_keycloak_client_id,
                "client_secret": settings.auth_keycloak_client_secret,
                "refresh_token": req.refresh_token,
            },
        )

    if resp.status_code not in (200, 204):
        logger.warning("Keycloak logout returned status %d", resp.status_code)

    return {"detail": "Logged out successfully"}


# ---------------------------------------------------------------------------
# Auth type info
# ---------------------------------------------------------------------------

@router.get("/type")
async def get_auth_type():
    """Return the current authentication type (local or keycloak)."""
    return {"auth_type": settings.auth_type}
