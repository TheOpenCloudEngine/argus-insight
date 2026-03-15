"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException

from app.auth import service
from app.auth.schemas import LoginRequest, LoginResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate and return an access token."""
    user = service.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = service.create_token(user["username"], user["role"])
    return LoginResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
async def get_current_user():
    """Get current user information.

    Note: In production, this should extract the user from the
    Authorization header token. Currently returns a placeholder.
    """
    # TODO: Extract user from token in Authorization header
    return UserInfo(username="admin", role="admin")
