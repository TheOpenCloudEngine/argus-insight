"""Authentication endpoints that proxy to Keycloak. Added for SSO AUTH."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.auth import CurrentUser, TokenUser
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


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
    is_admin: bool


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate a user via Keycloak and return tokens."""
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
    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        token_type=data["token_type"],
        expires_in=data["expires_in"],
        refresh_expires_in=data["refresh_expires_in"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest):
    """Refresh an access token using a refresh token."""
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
        is_admin=user.is_admin,
    )


@router.post("/logout")
async def logout(req: LogoutRequest):
    """Logout by invalidating the refresh token in Keycloak."""
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
