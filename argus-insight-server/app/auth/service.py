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
