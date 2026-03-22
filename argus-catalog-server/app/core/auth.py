"""Keycloak OIDC authentication for FastAPI.

Added for SSO AUTH.

Provides JWT token verification against Keycloak's JWKS endpoint
and FastAPI dependency functions for protecting routes.
"""

import logging
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache JWKS keys for 1 hour
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)
_JWKS_CACHE_KEY = "jwks"


def _keycloak_base_url() -> str:
    return f"{settings.auth_keycloak_server_url}/realms/{settings.auth_keycloak_realm}"


def _jwks_uri() -> str:
    return f"{_keycloak_base_url()}/protocol/openid-connect/certs"


def _issuer() -> str:
    return _keycloak_base_url()


async def _get_jwks() -> dict:
    """Fetch and cache Keycloak JWKS public keys."""
    cached = _jwks_cache.get(_JWKS_CACHE_KEY)
    if cached:
        return cached
    async with httpx.AsyncClient() as client:
        resp = await client.get(_jwks_uri())
        resp.raise_for_status()
        jwks = resp.json()
    _jwks_cache[_JWKS_CACHE_KEY] = jwks
    logger.info("Fetched JWKS from %s (%d keys)", _jwks_uri(), len(jwks.get("keys", [])))
    return jwks


@dataclass
class TokenUser:
    """Represents an authenticated user extracted from a JWT token."""

    sub: str
    username: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    roles: list[str] = field(default_factory=list)
    realm_roles: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return settings.auth_keycloak_admin_role in self.realm_roles


def _extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def _verify_token(token: str) -> dict:
    """Verify and decode a Keycloak JWT token."""
    jwks = await _get_jwks()

    # Get the key ID from the token header
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token header: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    kid = unverified_header.get("kid")
    rsa_key = None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            rsa_key = key
            break

    if not rsa_key:
        # Invalidate cache and retry once
        _jwks_cache.pop(_JWKS_CACHE_KEY, None)
        jwks = await _get_jwks()
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

    if not rsa_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find matching key for token verification",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=_issuer(),
            options={"verify_aud": False, "verify_iss": True},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def _build_token_user(payload: dict) -> TokenUser:
    """Build a TokenUser from a decoded JWT payload."""
    realm_access = payload.get("realm_access", {})
    realm_roles = realm_access.get("roles", [])

    resource_access = payload.get("resource_access", {})
    client_roles = resource_access.get(settings.auth_keycloak_client_id, {}).get("roles", [])

    return TokenUser(
        sub=payload.get("sub", ""),
        username=payload.get("preferred_username", ""),
        email=payload.get("email", ""),
        first_name=payload.get("given_name", ""),
        last_name=payload.get("family_name", ""),
        roles=client_roles,
        realm_roles=realm_roles,
    )


async def get_current_user(request: Request) -> TokenUser:
    """FastAPI dependency: extract and verify the current user from the JWT token."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = await _verify_token(token)
    return _build_token_user(payload)


async def get_optional_user(request: Request) -> TokenUser | None:
    """FastAPI dependency: extract user if token is present, otherwise None."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    try:
        payload = await _verify_token(token)
        return _build_token_user(payload)
    except HTTPException:
        return None


async def require_admin(
    user: Annotated[TokenUser, Depends(get_current_user)],
) -> TokenUser:
    """FastAPI dependency: require the current user to have the admin role."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


# Type aliases for use in route signatures
CurrentUser = Annotated[TokenUser, Depends(get_current_user)]
OptionalUser = Annotated[TokenUser | None, Depends(get_optional_user)]
AdminUser = Annotated[TokenUser, Depends(require_admin)]
