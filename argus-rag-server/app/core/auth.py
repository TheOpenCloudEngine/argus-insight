"""Authentication — shares JWT tokens with argus-catalog-server."""

import logging
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)
LOCAL_JWT_ALGORITHM = "HS256"
LOCAL_JWT_SECRET_KEY = "argus-catalog-local-jwt-secret-key-change-in-production"


@dataclass
class TokenUser:
    sub: str
    username: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    roles: list[str] = field(default_factory=list)
    realm_roles: list[str] = field(default_factory=list)

    @property
    def _all_roles(self) -> list[str]:
        return self.roles + self.realm_roles

    @property
    def is_admin(self) -> bool:
        return settings.auth_keycloak_admin_role in self._all_roles

    @property
    def has_argus_role(self) -> bool:
        return any(
            r in self._all_roles
            for r in (
                settings.auth_keycloak_admin_role,
                settings.auth_keycloak_superuser_role,
                settings.auth_keycloak_user_role,
            )
        )


async def _get_jwks() -> dict:
    cached = _jwks_cache.get("jwks")
    if cached:
        return cached
    url = (
        f"{settings.auth_keycloak_server_url}/realms/"
        f"{settings.auth_keycloak_realm}/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        jwks = resp.json()
    _jwks_cache["jwks"] = jwks
    return jwks


async def _verify_keycloak(token: str) -> dict:
    jwks = await _get_jwks()
    kid = jwt.get_unverified_header(token).get("kid")
    rsa_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not rsa_key:
        _jwks_cache.pop("jwks", None)
        jwks = await _get_jwks()
        rsa_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not rsa_key:
        raise HTTPException(status_code=401, detail="Key not found")
    issuer = f"{settings.auth_keycloak_server_url}/realms/{settings.auth_keycloak_realm}"
    return jwt.decode(
        token, rsa_key, algorithms=["RS256"], issuer=issuer, options={"verify_aud": False}
    )


def _verify_local(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            LOCAL_JWT_SECRET_KEY,
            algorithms=[LOCAL_JWT_ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _build_user(payload: dict) -> TokenUser:
    if settings.auth_type == "local":
        return TokenUser(
            sub=payload.get("sub", ""),
            username=payload.get("preferred_username", ""),
            email=payload.get("email", ""),
            roles=payload.get("roles", []),
        )
    realm_roles = payload.get("realm_access", {}).get("roles", [])
    client_roles = (
        payload.get("resource_access", {})
        .get(settings.auth_keycloak_client_id, {})
        .get("roles", [])
    )
    return TokenUser(
        sub=payload.get("sub", ""),
        username=payload.get("preferred_username", ""),
        email=payload.get("email", ""),
        roles=client_roles,
        realm_roles=realm_roles,
    )


async def get_current_user(request: Request) -> TokenUser:
    auth = request.headers.get("Authorization", "")
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing token")
    token = parts[1]
    if settings.auth_type == "local":
        payload = _verify_local(token)
    else:
        payload = await _verify_keycloak(token)
    user = _build_user(payload)
    if not user.has_argus_role:
        raise HTTPException(status_code=403, detail="No role assigned")
    return user


async def get_optional_user(request: Request) -> TokenUser | None:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


CurrentUser = Annotated[TokenUser, Depends(get_current_user)]
OptionalUser = Annotated[TokenUser | None, Depends(get_optional_user)]
