"""
STTNB Repository Router — CRUD endpoints for data repositories.
Supports shared repos within the same organization.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, can_access_repo
from app.config import settings
from app import database as db
from app.models import (
    RepositoryCategoryCreate,
    RepositoryCategoryResponse,
    RepositoryCategoryUpdate,
    RepositoryCreate,
    RepositoryResponse,
    RepositoryUpdate,
)
from app.services.repository_service import repository_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


def _build_response(repo: dict, doc_count: int, is_shared: bool = False) -> RepositoryResponse:
    """Build RepositoryResponse from repo dict."""
    return RepositoryResponse(
        id=repo["id"],
        name=repo["name"],
        description=repo["description"],
        notebook_id=repo.get("notebook_id"),
        category_id=repo.get("category_id"),
        category_name=repo.get("category_name"),
        document_count=doc_count,
        is_public=bool(repo.get("is_public", 0)),
        is_shared=is_shared,
        owner_name=repo.get("owner_name"),
        created_at=repo["created_at"],
        updated_at=repo["updated_at"],
    )


def _build_category_response(category: dict, is_shared: bool = False) -> RepositoryCategoryResponse:
    """Build RepositoryCategoryResponse from category dict."""
    return RepositoryCategoryResponse(
        id=category["id"],
        name=category["name"],
        description=category.get("description") or "",
        is_public=bool(category.get("is_public", 0)),
        is_shared=is_shared,
        owner_name=category.get("owner_name"),
        repository_count=int(category.get("repository_count") or 0),
        created_at=category["created_at"],
        updated_at=category["updated_at"],
    )


async def _ensure_own_category(category_id: str | None, current_user: dict):
    if not category_id:
        return None
    category = await db.get_repository_category_by_id(category_id)
    if not category or category["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh mục không tồn tại hoặc không thuộc tài khoản của bạn",
        )
    return category


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    req: RepositoryCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Tạo kho dữ liệu mới.
    
    Tự động tạo kết nối với máy chủ xử lý.
    """
    try:
        await _ensure_own_category(req.category_id, current_user)
        repo = await repository_service.create_repository(
            user_id=current_user["id"],
            name=req.name,
            description=req.description,
            category_id=req.category_id,
            current_user=current_user,
        )
        return _build_response(repo, 0)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024


@router.get("/storage-usage")
async def get_storage_usage(current_user: dict = Depends(get_current_user)):
    """Dung lượng tài liệu người dùng đã upload so với quota được cấp."""
    used_bytes = await db.get_user_total_document_bytes(current_user["id"])
    limit_bytes = settings.max_user_upload_bytes
    return {
        "used_bytes": used_bytes,
        "limit_bytes": limit_bytes,
        "used_label": _format_bytes(used_bytes),
        "limit_label": _format_bytes(limit_bytes),
        "percent": round((used_bytes / limit_bytes) * 100, 2) if limit_bytes > 0 else 0,
    }


@router.get("/categories", response_model=list[RepositoryCategoryResponse])
async def list_categories(current_user: dict = Depends(get_current_user)):
    """Liệt kê danh mục cá nhân và danh mục chia sẻ có kho được chia sẻ trong đơn vị."""
    result = []

    categories = await db.get_repository_categories_by_user(current_user["id"])
    for category in categories:
        result.append(_build_category_response(category, is_shared=False))

    org_id = current_user.get("org_id")
    if org_id:
        shared = await db.get_shared_repository_categories(org_id, current_user["id"])
        for category in shared:
            result.append(_build_category_response(category, is_shared=True))

    return result


@router.post("/categories", response_model=RepositoryCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    req: RepositoryCategoryCreate,
    current_user: dict = Depends(get_current_user),
):
    """Tạo danh mục để nhóm kho dữ liệu."""
    category = await db.create_repository_category(
        current_user["id"], req.name, req.description, req.is_public
    )
    return _build_category_response(category)


@router.put("/categories/{category_id}", response_model=RepositoryCategoryResponse)
async def update_category(
    category_id: str,
    req: RepositoryCategoryUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Cập nhật danh mục cá nhân."""
    await _ensure_own_category(category_id, current_user)
    updated = await db.update_repository_category(
        category_id, name=req.name, description=req.description, is_public=req.is_public
    )
    return _build_category_response(updated)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Xóa danh mục cá nhân. Kho trong danh mục sẽ chuyển về chưa phân loại."""
    await _ensure_own_category(category_id, current_user)
    await db.delete_repository_category(category_id)


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(current_user: dict = Depends(get_current_user)):
    """
    Liệt kê kho dữ liệu: kho cá nhân + kho chia sẻ từ đơn vị.
    """
    result = []

    # User's own repos
    repos = await db.get_repositories_by_user(current_user["id"])
    for repo in repos:
        docs = await db.get_documents_by_repository(repo["id"])
        result.append(_build_response(repo, len(docs), is_shared=False))

    # Shared repos from same org
    org_id = current_user.get("org_id")
    if org_id:
        shared = await db.get_shared_repositories(org_id, current_user["id"])
        for repo in shared:
            docs = await db.get_documents_by_repository(repo["id"])
            result.append(_build_response(repo, len(docs), is_shared=True))

    return result


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Chi tiết 1 kho dữ liệu (bao gồm kho chia sẻ cùng đơn vị)."""
    repo = await can_access_repo(repo_id, current_user)
    docs = await db.get_documents_by_repository(repo_id)
    is_shared = not repo.get("is_owner", True)
    return _build_response(repo, len(docs), is_shared=is_shared)


@router.put("/{repo_id}", response_model=RepositoryResponse)
async def update_repository(
    repo_id: str,
    req: RepositoryUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Cập nhật kho dữ liệu (chỉ chủ sở hữu)."""
    repo = await can_access_repo(repo_id, current_user)
    if not repo.get("is_owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ chủ sở hữu mới có quyền chỉnh sửa kho",
        )

    field_set = getattr(req, "model_fields_set", getattr(req, "__fields_set__", set()))
    category_id_set = "category_id" in field_set
    if category_id_set:
        await _ensure_own_category(req.category_id, current_user)

    updated = await db.update_repository(
        repo_id, name=req.name, description=req.description,
        is_public=req.is_public, category_id=req.category_id,
        category_id_set=category_id_set,
    )
    docs = await db.get_documents_by_repository(repo_id)
    return _build_response(updated, len(docs))


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Xóa kho dữ liệu (chỉ chủ sở hữu hoặc system_admin).
    
    Xóa toàn bộ dữ liệu liên quan, bao gồm tất cả tài liệu và lịch sử chat.
    """
    repo = await can_access_repo(repo_id, current_user)
    if not repo.get("is_owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ chủ sở hữu mới có quyền xóa kho",
        )
    try:
        await repository_service.delete_repository(repo_id, current_user["id"], current_user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
