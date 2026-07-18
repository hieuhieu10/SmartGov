"""
STTNB Models — Pydantic schemas for API responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, Field


def _to_str(v: object) -> str:
    """Convert datetime (or any value) to ISO string."""
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v) if v is not None else ""


DateTimeStr = Annotated[str, BeforeValidator(_to_str)]
"""A string field that serializes database datetime values."""


# ─── Processing Status ───────────────────────────────────────────────

class TaskStatus(str, Enum):
    """Status of a long-running background processing task (e.g. drafting)."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    GENERATING_MINUTES = "generating_minutes"
    EXPORTING_WORD = "exporting_word"
    COMPLETED = "completed"
    ERROR = "error"


class HealthResponse(BaseModel):
    """Health check response."""
    model_config = {"populate_by_name": True}
    status: str = "ok"
    service: str = "STTNB - Speech To Text Notebook"
    version: str = "2.0.0"
    notebooklm_auth: str = Field(default="unknown", serialization_alias="ai_service")


# ─── Auth Schemas ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50, description="Tên đăng nhập")
    password: str = Field(..., min_length=6, max_length=100, description="Mật khẩu")
    full_name: str = Field(default="", max_length=100, description="Họ tên đầy đủ")


class ChangePasswordRequest(BaseModel):
    """User changes their own password."""
    old_password: str = Field(..., description="Mật khẩu hiện tại")
    new_password: str = Field(..., min_length=6, max_length=100, description="Mật khẩu mới")


class LoginRequest(BaseModel):
    """User login request."""
    username: str = Field(..., description="Tên đăng nhập")
    password: str = Field(..., description="Mật khẩu")


class AuthResponse(BaseModel):
    """Authentication response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    full_name: str
    role: str = "user"
    org_id: Optional[str] = None
    org_name: Optional[str] = None


class UserInfo(BaseModel):
    """Current user info."""
    id: str
    username: str
    full_name: str
    role: str = "user"
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    dept_id: Optional[str] = None
    dept_name: Optional[str] = None
    ai_engine: Optional[str] = None
    created_at: Optional[DateTimeStr] = None


# ─── Organization & Department Schemas ─────────────────────────────

class OrgCreate(BaseModel):
    """Create organization."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    max_accounts: int = Field(
        default=0,
        ge=0,
        description="Số tài khoản tối đa của đơn vị. 0 nghĩa là không giới hạn.",
    )


class OrgUpdate(BaseModel):
    """Update organization."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    max_accounts: Optional[int] = Field(
        None,
        ge=0,
        description="Số tài khoản tối đa của đơn vị. 0 nghĩa là không giới hạn.",
    )


class OrgResponse(BaseModel):
    """Organization response."""
    id: str
    name: str
    description: str
    max_accounts: int = 0
    dept_count: int = 0
    user_count: int = 0
    created_at: DateTimeStr
    updated_at: DateTimeStr


class DeptCreate(BaseModel):
    """Create department."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class DeptUpdate(BaseModel):
    """Update department."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class DeptResponse(BaseModel):
    """Department response."""
    id: str
    org_id: str
    name: str
    description: str
    user_count: int = 0
    created_at: Optional[DateTimeStr] = None


# ─── Admin User Management Schemas ─────────────────────────────────

class AdminUserCreate(BaseModel):
    """Admin creates a user."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str = Field(default="", max_length=100)
    role: str = Field(default="user", pattern="^(user|org_admin|system_admin)$")
    org_id: Optional[str] = None
    dept_id: Optional[str] = None
    ai_engine: Optional[str] = Field(
        None,
        pattern="^(self_hosted)$",
        description="Máy chủ xử lý cho user: self_hosted hoặc null (dùng mặc định hệ thống)",
    )


class AdminUserUpdate(BaseModel):
    """Admin updates a user."""
    full_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role: Optional[str] = Field(None, pattern="^(user|org_admin|system_admin)$")
    org_id: Optional[str] = None
    dept_id: Optional[str] = None
    ai_engine: Optional[str] = Field(
        None,
        pattern="^(self_hosted|)$",
        description="Máy chủ xử lý: self_hosted. Gửi giá trị rỗng '' để reset về mặc định hệ thống.",
    )


class AdminUserResponse(BaseModel):
    """User info for admin views."""
    id: str
    username: str
    full_name: str
    role: str = "user"
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    dept_id: Optional[str] = None
    dept_name: Optional[str] = None
    ai_engine: Optional[str] = None
    created_at: Optional[DateTimeStr] = None


# ─── Repository Schemas ──────────────────────────────────────────────

class RepositoryCategoryCreate(BaseModel):
    """Create repository category request."""
    name: str = Field(..., min_length=1, max_length=200, description="Tên danh mục")
    description: str = Field(default="", max_length=500, description="Mô tả danh mục")
    is_public: bool = False


class RepositoryCategoryUpdate(BaseModel):
    """Update repository category request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None


class RepositoryCategoryResponse(BaseModel):
    """Repository category info response."""
    id: str
    name: str
    description: str = ""
    is_public: bool = False
    is_shared: bool = False
    owner_name: Optional[str] = None
    repository_count: int = 0
    created_at: DateTimeStr
    updated_at: DateTimeStr


class RepositoryCreate(BaseModel):
    """Create repository request."""
    name: str = Field(..., min_length=1, max_length=200, description="Tên kho dữ liệu")
    description: str = Field(default="", max_length=500, description="Mô tả kho")
    category_id: Optional[str] = None


class RepositoryUpdate(BaseModel):
    """Update repository request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    category_id: Optional[str] = None


class RepositoryResponse(BaseModel):
    """Repository info response."""
    id: str
    name: str
    description: str
    notebook_id: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    document_count: int = 0
    is_public: bool = False
    is_shared: bool = False
    owner_name: Optional[str] = None
    created_at: DateTimeStr
    updated_at: DateTimeStr


class DocumentResponse(BaseModel):
    """Document info response."""
    id: str
    repository_id: str
    filename: str
    folder_key: str = "draft"
    file_size: int
    file_type: str
    processing_status: str = "queued"
    progress_message: str = ""
    error_message: str = ""
    chunk_count: int = 0
    processed_at: Optional[DateTimeStr] = None
    uploaded_at: DateTimeStr


class DocumentVersionResponse(BaseModel):
    """Immutable snapshot created whenever a document is uploaded or saved."""
    id: str
    document_id: str
    version_number: int
    filename: str
    file_size: int
    file_type: str
    changed_by_name: str = ""
    change_type: str = "edited"
    created_at: DateTimeStr
    is_current: bool = False


class DatasetField(BaseModel):
    """A table-like field/column extracted from a document."""
    key: str = Field(description="Stable key for FE binding, vd: noi_dung_gop_y")
    label: str = Field(description="Column label shown to users")
    value_type: str = Field(default="text", description="Data type hint for FE rendering")
    required: bool = Field(default=False, description="Whether the value is expected")
    description: str = Field(default="", description="Short explanation of this field")


class DocumentDatasetResponse(BaseModel):
    """Structured dataset extracted from an uploaded document."""
    title: str = Field(description="Document title or extracted trich yeu")
    content: list[str] = Field(
        default_factory=list,
        description="Main document body, usually document_data.noi_dung",
    )
    fields: list[DatasetField] = Field(
        default_factory=list,
        description="Columns found or expected in document tables",
    )
    rows: list[dict[str, str]] = Field(
        default_factory=list,
        description="Table rows keyed by fields[].key",
    )
    document_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw AI-style administrative document payload for storage/export",
    )
    source: str = Field(default="mock", description="mock | ai | manual")
    filename: str = ""
    message: str = ""


class DocumentDatasetWordRequest(BaseModel):
    """Request to render/export an AI-style administrative document JSON."""
    document_data: dict[str, Any] = Field(
        ...,
        description="AI/toolnd30-compatible document JSON",
    )
    filename: str = Field(
        default="van-ban.docx",
        max_length=200,
        description="Suggested output filename",
    )


class RevisionTaskResponse(BaseModel):
    """Revision task summary for the review workflow."""
    id: str
    title: str
    status: str
    progress_message: str = ""
    error_message: str = ""
    reject_reason: str = ""
    output_ready: bool = False
    created_at: DateTimeStr
    updated_at: DateTimeStr


class RevisionReviewResponse(BaseModel):
    """Data needed by FE to render original vs proposed review."""
    task_id: str
    status: str
    title: str
    original: dict[str, Any]
    proposed: dict[str, Any]
    changes: list[dict[str, Any]] = Field(default_factory=list)
    extracted_comments: list[dict[str, Any]] = Field(default_factory=list)


class RevisionRejectRequest(BaseModel):
    """Reason for rejecting a proposed revision."""
    reason: str = Field(default="", max_length=2000)


# ─── Chat Schemas ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Chat message request."""
    message: str = Field(..., min_length=1, max_length=5000, description="Nội dung câu hỏi")


class ChatMessage(BaseModel):
    """A single chat message."""
    id: str
    role: str
    content: str
    created_at: DateTimeStr


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    repository_id: str
    messages: list[ChatMessage]


# ─── Drafting Schemas ────────────────────────────────────────────────

class DocumentType(str, Enum):
    """Supported administrative document types (NĐ 30/2020/NĐ-CP)."""
    CONG_VAN = "cong_van"
    QUYET_DINH = "quyet_dinh"
    KE_HOACH = "ke_hoach"
    THONG_BAO = "thong_bao"
    TO_TRINH = "to_trinh"
    BAO_CAO = "bao_cao"


class DraftRequest(BaseModel):
    """Request to draft an administrative document."""
    document_type: DocumentType = Field(
        ...,
        description="Loại văn bản cần soạn. Người dùng phải chọn rõ loại văn bản.",
    )
    input_data: dict = Field(
        ...,
        description="Thông tin đầu vào cho văn bản. Các trường tùy thuộc loại văn bản."
    )
    selected_document_ids: list[str] = Field(
        default_factory=list,
        description="Danh sách ID tài liệu nguồn người dùng chọn để soạn. Để trống thì hệ thống dùng toàn bộ tài liệu trong kho.",
    )


class DraftEditRequest(BaseModel):
    """Request to edit an already exported Word draft."""
    instruction: str = Field(
        ...,
        min_length=5,
        description="Yêu cầu chỉnh sửa nội dung trên file Word đã xuất.",
    )


class DraftTypeInfo(BaseModel):
    """Information about a draft document type."""
    type_code: str
    name: str
    description: str
    required_fields: list[str]
    optional_fields: list[str]


class DraftTaskResponse(BaseModel):
    """Response after submitting a draft request."""
    task_id: str
    status: TaskStatus
    document_type: str
    message: str


class DraftStatusResponse(BaseModel):
    """Status of a drafting task."""
    task_id: str
    status: TaskStatus
    document_type: str
    progress_message: str
    error_message: str
    output_ready: bool = False


# ─── Custom Template Schemas ─────────────────────────────────────────

class TemplateHeading(BaseModel):
    """A heading/section extracted from a template file."""
    key: str = Field(description="Tên đầu mục, vd: cong_tac_chi_dao")
    title: str = Field(description="Tiêu đề đầu mục, vd: I. CÔNG TÁC CHỈ ĐẠO")
    description: str = Field(default="", description="Mô tả nội dung cần viết")
    required: bool = Field(default=True, description="Có bắt buộc không")


# Keep for backward compat
TemplatePlaceholder = TemplateHeading


class TemplateResponse(BaseModel):
    """Response for a custom document template."""
    id: str
    name: str
    description: str
    doc_type: str = ""
    doc_type_label: str = ""
    headings: list[TemplateHeading] = []
    status: str
    error_message: str = ""
    created_at: DateTimeStr
    updated_at: DateTimeStr


class TemplateGenerateRequest(BaseModel):
    """Request to generate a document from a custom template."""
    input_data: dict[str, str] = Field(
        default_factory=dict,
        description="Gợi ý/nội dung cho từng đầu mục: {heading_key: text}"
    )
    repo_id: str = Field(
        ..., description="ID kho dữ liệu nguồn (bắt buộc)"
    )
    selected_document_ids: list[str] = Field(
        default_factory=list,
        description="Danh sách ID tài liệu nguồn người dùng chọn. Để trống thì hệ thống dùng toàn bộ tài liệu trong kho.",
    )


class TemplateGenerateResponse(BaseModel):
    """Response after submitting a template generation request."""
    task_id: str
    status: str
    message: str
