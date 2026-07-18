"""
STTNB Authentication — JWT token-based auth with bcrypt password hashing.
Supports role-based access control: system_admin, org_admin, user.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app import database as db

logger = logging.getLogger(__name__)

# ─── Security scheme ─────────────────────────────────────────────────

security = HTTPBearer()


async def require_ai_internal_token(
    x_ai_internal_token: str = Header(default="", alias="X-AI-Internal-Token"),
) -> None:
    """Xác thực request gọi NGƯỢC từ AI service về BE (ví dụ Agent Researcher
    dùng shared retrieval). Dùng lại đúng secret `AI_INTERNAL_TOKEN` mà BE
    cũng dùng để gọi AI — không thêm secret mới, cùng mô hình tin cậy 2 chiều.
    """
    if not settings.ai_internal_token or x_ai_internal_token != settings.ai_internal_token:
        raise HTTPException(status_code=401, detail="Invalid internal AI token")


# ─── Password Hashing ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ─── JWT Token ────────────────────────────────────────────────────────

def create_access_token(user_id: str, username: str, role: str = "user",
                        org_id: str = None) -> str:
    """Create a JWT access token with role and org info."""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "org_id": org_id,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ─── FastAPI Dependencies ─────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency: Extract and validate JWT from Authorization header.
    Returns the current user dict (with role, org_id, org_name, dept_id, dept_name).
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không chứa thông tin người dùng",
        )

    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
        )

    return user


async def require_system_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require system_admin role."""
    if current_user.get("role") != "system_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin hệ thống mới có quyền thực hiện",
        )
    return current_user


async def require_org_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require org_admin or system_admin role."""
    if current_user.get("role") not in ("system_admin", "org_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin đơn vị hoặc admin hệ thống mới có quyền thực hiện",
        )
    return current_user


async def can_access_repo(repo_id: str, current_user: dict) -> dict:
    """
    Check if user can access a repository (either owner or shared within org).
    Returns the repo dict with 'is_owner' flag.
    """
    repo = await db.get_repository_by_id(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kho dữ liệu không tồn tại",
        )

    is_owner = repo["user_id"] == current_user["id"]
    is_system_admin = current_user.get("role") == "system_admin"

    if is_owner or is_system_admin:
        await db.touch_repository(repo_id)
        repo["is_owner"] = True
        return repo

    # Check shared access: same org + public
    if repo.get("is_public"):
        owner = await db.get_user_by_id(repo["user_id"])
        if owner and owner.get("org_id") == current_user.get("org_id") and current_user.get("org_id"):
            await db.touch_repository(repo_id)
            repo["is_owner"] = False
            return repo

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền truy cập kho dữ liệu này",
    )


# ─── AI Engine Resolver ──────────────────────────────────────────────

def get_user_engine(user: dict) -> str:
    """
    Resolve the effective AI engine for a user.

    Priority:
      1. User-level ai_engine (set by admin per user)
      2. Global ai_engine from config.py (default)

    Returns: 'notebooklm' or 'self_hosted'
    """
    user_engine = user.get("ai_engine")
    if user_engine and user_engine in ("notebooklm", "self_hosted"):
        return user_engine
    return settings.ai_engine


def is_user_self_hosted(user: dict) -> bool:
    """Check if a user should use the self-hosted engine."""
    return get_user_engine(user) == "self_hosted"
