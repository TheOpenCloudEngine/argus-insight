"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.schemas import LoginRequest, LoginResponse, UserInfo, UserSelfUpdateRequest
from app.core.database import get_session

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
async def get_current_user(
    session: AsyncSession = Depends(get_session),
):
    """Get current user information.

    FIXME: 현재는 인증 없이 argus_users.id=1 사용자를 강제로 조회하여 반환합니다.
           실제 인증이 구현되면 Authorization 헤더의 토큰에서 사용자를 추출하도록
           변경해야 합니다.
    """
    return await service.get_current_user_info(session)


@router.put("/me", response_model=UserInfo)
async def update_current_user(
    req: UserSelfUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update current user's profile.

    Only provided (non-None) fields are updated. Username and role
    cannot be changed through this endpoint.
    """
    try:
        return await service.update_current_user(
            session,
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email,
            phone_number=req.phone_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
