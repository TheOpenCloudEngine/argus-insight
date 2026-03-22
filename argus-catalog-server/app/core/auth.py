"""Authentication for FastAPI — supports Keycloak OIDC and Local JWT.

Provides JWT token verification and FastAPI dependency functions.
When auth_type is "keycloak", verifies against Keycloak's JWKS endpoint.
When auth_type is "local", verifies with a local HMAC secret key.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache JWKS keys for 1 hour (Keycloak mode only)
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)
_JWKS_CACHE_KEY = "jwks"

# Local JWT settings
LOCAL_JWT_ALGORITHM = "HS256"
LOCAL_JWT_EXPIRE_MINUTES = 480  # 8 hours
LOCAL_JWT_SECRET_KEY = "argus-catalog-local-jwt-secret-key-change-in-production"


# ---------------------------------------------------------------------------
# TokenUser dataclass
# ---------------------------------------------------------------------------

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
    def _all_roles(self) -> list[str]:
        """Combined roles from both local (roles) and Keycloak (realm_roles)."""
        return self.roles + self.realm_roles

    @property
    def is_admin(self) -> bool:
        return settings.auth_keycloak_admin_role in self._all_roles

    @property
    def is_superuser(self) -> bool:
        return settings.auth_keycloak_superuser_role in self._all_roles

    @property
    def is_user(self) -> bool:
        return settings.auth_keycloak_user_role in self._all_roles

    @property
    def has_argus_role(self) -> bool:
        """Check if the user has any valid role."""
        return self.is_admin or self.is_superuser or self.is_user

    @property
    def role(self) -> str:
        """Return the highest privilege role name."""
        if self.is_admin:
            return "admin"
        if self.is_superuser:
            return "superuser"
        if self.is_user:
            return "user"
        return "none"


# ---------------------------------------------------------------------------
# Keycloak token verification
# ---------------------------------------------------------------------------

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


async def _verify_token_keycloak(token: str) -> dict:
    """Verify and decode a Keycloak JWT token using JWKS."""
    jwks = await _get_jwks()

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


# ---------------------------------------------------------------------------
# Local token creation & verification
# ---------------------------------------------------------------------------

def create_local_token(
    sub: str,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    expire_minutes: int = LOCAL_JWT_EXPIRE_MINUTES,
) -> str:
    """Create a local JWT token for a user."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "preferred_username": username,
        "email": email,
        "given_name": first_name,
        "family_name": last_name,
        "roles": [role],
        "iat": now,
        "exp": now + expire_minutes * 60,
        "iss": "argus-catalog-local",
    }
    return jwt.encode(payload, LOCAL_JWT_SECRET_KEY, algorithm=LOCAL_JWT_ALGORITHM)


def _verify_token_local(token: str) -> dict:
    """Verify and decode a local JWT token."""
    try:
        payload = jwt.decode(
            token,
            LOCAL_JWT_SECRET_KEY,
            algorithms=[LOCAL_JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ---------------------------------------------------------------------------
# Build TokenUser from payload
# ---------------------------------------------------------------------------

def _build_token_user(payload: dict) -> TokenUser:
    """Build a TokenUser from a decoded JWT payload (works for both modes).

    Local mode: roles contain role_id values (e.g. ["argus-admin"]).
    Keycloak mode: realm_roles contain Keycloak realm role names (e.g. ["argus-admin"]).
    Both use the same role_id identifiers, so is_admin/is_superuser/is_user work uniformly.
    """
    if settings.auth_type == "local":
        # Local JWT stores role_id values in "roles" claim
        return TokenUser(
            sub=payload.get("sub", ""),
            username=payload.get("preferred_username", ""),
            email=payload.get("email", ""),
            first_name=payload.get("given_name", ""),
            last_name=payload.get("family_name", ""),
            roles=payload.get("roles", []),
            realm_roles=[],
        )

    # Keycloak mode — realm_roles contain role names matching role_id
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


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------

def _extract_bearer_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(request: Request) -> TokenUser:
    """FastAPI dependency: extract and verify the current user from JWT token."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.auth_type == "local":
        payload = _verify_token_local(token)
    else:
        payload = await _verify_token_keycloak(token)

    user = _build_token_user(payload)
    if not user.has_argus_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No role assigned. Contact your administrator.",
        )
    return user


async def get_optional_user(request: Request) -> TokenUser | None:
    """FastAPI dependency: extract user if token is present, otherwise None."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    try:
        if settings.auth_type == "local":
            payload = _verify_token_local(token)
        else:
            payload = await _verify_token_keycloak(token)
        return _build_token_user(payload)
    except HTTPException:
        return None


async def require_superuser(
    user: Annotated[TokenUser, Depends(get_current_user)],
) -> TokenUser:
    """FastAPI dependency: require superuser or admin role."""
    if not (user.is_admin or user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser or admin role required",
        )
    return user


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
SuperUser = Annotated[TokenUser, Depends(require_superuser)]
AdminUser = Annotated[TokenUser, Depends(require_admin)]
