"""Authentication service.

Provides basic authentication functionality. In production, this should be
extended with proper user storage, password hashing, and JWT token management.
"""

import hashlib
import hmac
import json
import logging
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserInfo
from app.usermgr.models import ArgusRole, ArgusUser

logger = logging.getLogger(__name__)

# Secret key for token signing - should be configured via settings in production
_SECRET_KEY = "argus-insight-server-secret-change-me"

# Token expiration time in seconds (default: 24 hours)
_TOKEN_EXPIRY = 86400

# In-memory user store (placeholder - replace with database in production)
_USERS: dict[str, dict] = {
    "admin": {"password_hash": hashlib.sha256(b"admin").hexdigest(), "role": "admin"},
}


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> dict | None:
    """Authenticate a user. Returns user info dict or None if failed."""
    user = _USERS.get(username)
    if not user:
        return None

    if not hmac.compare_digest(user["password_hash"], _hash_password(password)):
        return None

    return {"username": username, "role": user["role"]}


def create_token(username: str, role: str) -> str:
    """Create a simple base64-encoded token.

    Note: This is a simplified token implementation. For production,
    use a proper JWT library (e.g., python-jose or PyJWT).
    """
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + _TOKEN_EXPIRY,
    }
    data = json.dumps(payload).encode()
    signature = hmac.new(_SECRET_KEY.encode(), data, hashlib.sha256).hexdigest()
    token_data = json.dumps({"payload": payload, "sig": signature}).encode()
    return urlsafe_b64encode(token_data).decode()


def verify_token(token: str) -> dict | None:
    """Verify a token and return the payload. Returns None if invalid."""
    try:
        token_data = json.loads(urlsafe_b64decode(token))
        payload = token_data["payload"]
        signature = token_data["sig"]

        # Verify signature
        data = json.dumps(payload).encode()
        expected_sig = hmac.new(_SECRET_KEY.encode(), data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None


async def get_current_user_info(session: AsyncSession) -> UserInfo:
    """Return the current user information.

    FIXME: 현재는 인증 없이 argus_users.id=1 사용자를 강제로 조회하여 반환합니다.
           실제 인증이 구현되면 Authorization 헤더의 토큰에서 사용자를 추출하고,
           토큰의 username으로 사용자를 조회하도록 변경해야 합니다.
    """
    logger.info("Fetching current user info: forcing argus_users.id=1")
    result = await session.execute(
        select(ArgusUser, ArgusRole.name.label("role_name"))
        .join(ArgusRole, ArgusUser.role_id == ArgusRole.id)
        .where(ArgusUser.id == 1)
    )
    row = result.one_or_none()
    if row is None:
        logger.error("Default user (id=1) not found in argus_users")
        raise ValueError("Default user not found")

    user, role_name = row
    logger.info("Current user resolved: username=%s, role=%s", user.username, role_name)
    return UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number or "",
        role=role_name,
    )


async def update_current_user(
    session: AsyncSession,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
) -> UserInfo:
    """Update the current user's profile and return the updated info.

    FIXME: 현재는 argus_users.id=1 사용자를 강제로 업데이트합니다.
           인증 구현 후 토큰 기반으로 변경 필요.
    """
    logger.info("Updating current user info: forcing argus_users.id=1")
    result = await session.execute(
        select(ArgusUser).where(ArgusUser.id == 1)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("Default user not found")

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if email is not None:
        user.email = email
    if phone_number is not None:
        user.phone_number = phone_number

    await session.commit()
    await session.refresh(user)

    # Fetch role name
    role_result = await session.execute(
        select(ArgusRole.name).where(ArgusRole.id == user.role_id)
    )
    role_name = role_result.scalar_one()

    logger.info("User updated: username=%s", user.username)
    return UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number or "",
        role=role_name,
    )
