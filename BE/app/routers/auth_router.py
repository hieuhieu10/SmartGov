"""
STTNB Auth Router — Login only (registration is admin-only via admin_router).
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, status

from app.auth import verify_password, create_access_token, get_current_user, hash_password
from app import database as db
from app.models import LoginRequest, AuthResponse, UserInfo, ChangePasswordRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """
    Đăng nhập bằng username và password.
    
    Trả về JWT token (expire sau 24 giờ).
    Tài khoản do admin đơn vị hoặc admin hệ thống tạo.
    """
    user = await db.get_user_by_username(req.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
        )

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
        )

    token = create_access_token(
        user["id"], user["username"],
        role=user.get("role", "user"),
        org_id=user.get("org_id"),
    )
    logger.info(f"User logged in: {user['username']} (role={user.get('role')})")

    return AuthResponse(
        access_token=token,
        user_id=user["id"],
        username=user["username"],
        full_name=user.get("full_name", ""),
        role=user.get("role", "user"),
        org_id=user.get("org_id"),
        org_name=user.get("org_name"),
    )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Lấy thông tin người dùng hiện tại (bao gồm đơn vị, phòng ban, vai trò)."""
    return UserInfo(
        id=current_user["id"],
        username=current_user["username"],
        full_name=current_user.get("full_name", ""),
        role=current_user.get("role", "user"),
        org_id=current_user.get("org_id"),
        org_name=current_user.get("org_name"),
        dept_id=current_user.get("dept_id"),
        dept_name=current_user.get("dept_name"),
        created_at=current_user.get("created_at"),
    )


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """Người dùng tự thay đổi mật khẩu của chính mình."""
    # current_user might not have the correct password hash since we return without password
    # Let's get the full user record from DB
    user = await db.get_user_by_username(current_user["username"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại",
        )

    if not verify_password(req.old_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không đúng",
        )

    new_hash = hash_password(req.new_password)
    await db.update_user(user["id"], password_hash=new_hash)
    
    logger.info(f"User changed password: {user['username']}")
    return {"message": "Đổi mật khẩu thành công"}
