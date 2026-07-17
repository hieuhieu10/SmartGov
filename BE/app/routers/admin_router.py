"""
STTNB Admin Router — CRUD for organizations, departments, and users.
Only accessible by system_admin and org_admin roles.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import hash_password, require_system_admin, require_org_admin, get_current_user
from app import database as db
from app.models import (
    OrgCreate, OrgUpdate, OrgResponse,
    DeptCreate, DeptUpdate, DeptResponse,
    AdminUserCreate, AdminUserUpdate, AdminUserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Administration"])


# ═══════ Organizations ═══════

@router.post("/organizations", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(req: OrgCreate, admin: dict = Depends(require_system_admin)):
    """Tạo đơn vị mới (chỉ admin hệ thống)."""
    org = await db.create_organization(
        name=req.name,
        description=req.description,
        max_accounts=req.max_accounts,
    )
    logger.info(f"Org created: {org['name']} by {admin['username']}")
    return OrgResponse(**org, dept_count=0, user_count=0)


@router.get("/organizations", response_model=list[OrgResponse])
async def list_orgs(admin: dict = Depends(require_org_admin)):
    """Danh sách đơn vị."""
    if admin.get("role") == "system_admin":
        orgs = await db.get_all_organizations()
    else:
        # org_admin only sees their own org
        org = await db.get_organization_by_id(admin.get("org_id"))
        orgs = [org] if org else []
    return [OrgResponse(**o) for o in orgs]


@router.get("/organizations/{org_id}", response_model=OrgResponse)
async def get_org(org_id: str, admin: dict = Depends(require_org_admin)):
    """Chi tiết đơn vị."""
    if admin.get("role") != "system_admin" and admin.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Không có quyền xem đơn vị này")
    org = await db.get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Đơn vị không tồn tại")
    return OrgResponse(**org)


@router.put("/organizations/{org_id}", response_model=OrgResponse)
async def update_org(org_id: str, req: OrgUpdate, admin: dict = Depends(require_org_admin)):
    """Cập nhật đơn vị (system_admin hoặc org_admin của đơn vị đó)."""
    if admin.get("role") != "system_admin" and admin.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa đơn vị này")
    if req.max_accounts is not None and admin.get("role") != "system_admin":
        raise HTTPException(status_code=403, detail="Chỉ admin hệ thống mới được cấu hình giới hạn tài khoản")
    org = await db.get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Đơn vị không tồn tại")
    if req.max_accounts is not None and req.max_accounts > 0 and org.get("user_count", 0) > req.max_accounts:
        raise HTTPException(
            status_code=400,
            detail=f"Đơn vị hiện có {org.get('user_count', 0)} tài khoản, không thể đặt giới hạn thấp hơn.",
        )
    updated = await db.update_organization(
        org_id,
        name=req.name,
        description=req.description,
        max_accounts=req.max_accounts,
    )
    return OrgResponse(**updated)


async def _ensure_org_account_quota(org_id: str | None, exclude_user_id: str | None = None):
    """Validate organization max account quota before creating/moving a user."""
    if not org_id:
        return
    org = await db.get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Đơn vị không tồn tại")
    max_accounts = int(org.get("max_accounts") or 0)
    if max_accounts <= 0:
        return

    users = await db.get_users_by_org(org_id)
    current_count = len([u for u in users if u.get("id") != exclude_user_id])
    if current_count + 1 > max_accounts:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Đơn vị '{org['name']}' đã đạt giới hạn {max_accounts} tài khoản. "
                "Vui lòng tăng giới hạn trước khi thêm hoặc chuyển tài khoản."
            ),
        )


@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(org_id: str, admin: dict = Depends(require_system_admin)):
    """Xóa đơn vị (chỉ admin hệ thống)."""
    org = await db.get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Đơn vị không tồn tại")
    await db.delete_organization(org_id)
    logger.info(f"Org deleted: {org['name']} by {admin['username']}")


# ═══════ Departments ═══════

@router.post("/organizations/{org_id}/departments", response_model=DeptResponse,
             status_code=status.HTTP_201_CREATED)
async def create_dept(org_id: str, req: DeptCreate, admin: dict = Depends(require_org_admin)):
    """Tạo phòng ban trong đơn vị."""
    if admin.get("role") != "system_admin" and admin.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Không có quyền thêm phòng ban cho đơn vị này")
    org = await db.get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Đơn vị không tồn tại")
    dept = await db.create_department(org_id=org_id, name=req.name, description=req.description)
    logger.info(f"Dept created: {dept['name']} in {org['name']}")
    return DeptResponse(**dept, user_count=0)


@router.get("/organizations/{org_id}/departments", response_model=list[DeptResponse])
async def list_depts(org_id: str, current_user: dict = Depends(get_current_user)):
    """Danh sách phòng ban của đơn vị (ai cùng đơn vị đều xem được)."""
    if (current_user.get("role") != "system_admin"
            and current_user.get("org_id") != org_id):
        raise HTTPException(status_code=403, detail="Không có quyền xem phòng ban đơn vị này")
    depts = await db.get_departments_by_org(org_id)
    return [DeptResponse(**d) for d in depts]


@router.put("/departments/{dept_id}", response_model=DeptResponse)
async def update_dept(dept_id: str, req: DeptUpdate, admin: dict = Depends(require_org_admin)):
    """Cập nhật phòng ban."""
    dept = await db.get_department_by_id(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Phòng ban không tồn tại")
    if admin.get("role") != "system_admin" and admin.get("org_id") != dept["org_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền sửa phòng ban này")
    updated = await db.update_department(dept_id, name=req.name, description=req.description)
    return DeptResponse(**updated)


@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dept(dept_id: str, admin: dict = Depends(require_org_admin)):
    """Xóa phòng ban."""
    dept = await db.get_department_by_id(dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Phòng ban không tồn tại")
    if admin.get("role") != "system_admin" and admin.get("org_id") != dept["org_id"]:
        raise HTTPException(status_code=403, detail="Không có quyền xóa phòng ban này")
    await db.delete_department(dept_id)
    logger.info(f"Dept deleted: {dept['name']}")


# ═══════ Users ═══════

@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(req: AdminUserCreate, admin: dict = Depends(require_org_admin)):
    """Tạo tài khoản người dùng (admin đơn vị hoặc hệ thống)."""
    # org_admin can only create users within their org and always uses Server 1.
    effective_ai_engine = req.ai_engine
    if admin.get("role") == "org_admin":
        if req.org_id and req.org_id != admin.get("org_id"):
            raise HTTPException(status_code=403, detail="Không có quyền tạo user cho đơn vị khác")
        if not req.org_id:
            req.org_id = admin.get("org_id")
        if req.role == "system_admin":
            raise HTTPException(status_code=403, detail="Không có quyền tạo admin hệ thống")
        effective_ai_engine = "notebooklm"

    # Check username uniqueness
    existing = await db.get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=409, detail=f"Tên đăng nhập '{req.username}' đã tồn tại")
    await _ensure_org_account_quota(req.org_id)

    password_hash = hash_password(req.password)
    user = await db.create_user(
        username=req.username,
        password_hash=password_hash,
        full_name=req.full_name,
        role=req.role,
        org_id=req.org_id,
        dept_id=req.dept_id,
        ai_engine=effective_ai_engine,
    )
    logger.info(f"User created by admin: {req.username} (role={req.role}, org={req.org_id}, ai_engine={effective_ai_engine})")
    return AdminUserResponse(**user)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(admin: dict = Depends(require_org_admin)):
    """Danh sách tài khoản."""
    if admin.get("role") == "system_admin":
        users = await db.get_all_users()
    else:
        # org_admin sees only users in their org
        users = await db.get_users_by_org(admin.get("org_id"))
    return [AdminUserResponse(**u) for u in users]


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(user_id: str, req: AdminUserUpdate, admin: dict = Depends(require_org_admin)):
    """Cập nhật tài khoản."""
    target = await db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    # org_admin can only edit users in their org
    if admin.get("role") == "org_admin":
        if target.get("org_id") != admin.get("org_id"):
            raise HTTPException(status_code=403, detail="Không có quyền sửa user đơn vị khác")
        if req.role == "system_admin":
            raise HTTPException(status_code=403, detail="Không có quyền gán admin hệ thống")
        if req.org_id and req.org_id != admin.get("org_id"):
            raise HTTPException(status_code=403, detail="Không có quyền chuyển user sang đơn vị khác")

    kwargs = {}
    if req.full_name is not None:
        kwargs["full_name"] = req.full_name
    if req.role is not None:
        kwargs["role"] = req.role
    if req.org_id is not None:
        if req.org_id != target.get("org_id"):
            await _ensure_org_account_quota(req.org_id, exclude_user_id=user_id)
        kwargs["org_id"] = req.org_id
    if req.dept_id is not None:
        kwargs["dept_id"] = req.dept_id
    if req.password:
        kwargs["password_hash"] = hash_password(req.password)
    if req.ai_engine is not None:
        if admin.get("role") != "system_admin":
            raise HTTPException(status_code=403, detail="Chỉ admin hệ thống mới được đổi máy chủ xử lý")
        # Empty string resets to global default (NULL in DB)
        kwargs["ai_engine"] = req.ai_engine if req.ai_engine else None

    user = await db.update_user(user_id, **kwargs)
    return AdminUserResponse(**user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, admin: dict = Depends(require_org_admin)):
    """Xóa tài khoản."""
    target = await db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    # Cannot delete yourself
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Không thể xóa chính mình")

    # org_admin can only delete users in their org
    if admin.get("role") == "org_admin":
        if target.get("org_id") != admin.get("org_id"):
            raise HTTPException(status_code=403, detail="Không có quyền xóa user đơn vị khác")
        if target.get("role") in ("system_admin", "org_admin"):
            raise HTTPException(status_code=403, detail="Không có quyền xóa admin")

    await db.delete_user(user_id)
    logger.info(f"User deleted: {target['username']} by {admin['username']}")
