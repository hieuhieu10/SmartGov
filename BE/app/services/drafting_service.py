"""Drafting domain adapter. AI generation runs in the internal AI service."""

import shutil

from app import database as db
from app.auth import is_user_self_hosted
from app.config import settings
from app.models import DocumentType
from app.services.ai_client import ai_client

_INFO = {
    DocumentType.CONG_VAN: ("Công văn", "Văn bản trao đổi, đề nghị"),
    DocumentType.QUYET_DINH: ("Quyết định", "Quyết định về một vấn đề cụ thể"),
    DocumentType.KE_HOACH: ("Kế hoạch", "Kế hoạch triển khai công việc"),
    DocumentType.THONG_BAO: ("Thông báo", "Thông báo nội bộ hoặc bên ngoài"),
    DocumentType.TO_TRINH: ("Tờ trình", "Đề xuất trình cấp có thẩm quyền"),
    DocumentType.BAO_CAO: ("Báo cáo", "Báo cáo kết quả và tình hình"),
}
_REQUIRED = ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"]


class DraftingService:
    def get_document_types(self) -> list[dict]:
        return [
            {
                "type_code": doc_type.value,
                "name": values[0],
                "description": values[1],
                "required_fields": _REQUIRED,
                "optional_fields": [
                    "co_quan_chu_quan", "noi_nhan", "nguoi_ky",
                    "chuc_vu_nguoi_ky", "so_van_ban",
                ],
            }
            for doc_type, values in _INFO.items()
        ]

    def get_document_types_by_code(self) -> dict[str, str]:
        return {doc_type.value: values[0] for doc_type, values in _INFO.items()}

    def validate_input(self, doc_type: DocumentType, input_data: dict) -> list[str]:
        return [field for field in _REQUIRED if not input_data.get(field)]

    def validate_draft_quality(self, doc_type: DocumentType, draft_data: dict, input_data=None):
        if not isinstance(draft_data, dict) or not draft_data:
            raise ValueError("AI không trả về nội dung văn bản hợp lệ.")

    async def draft_document(
        self,
        notebook_id: str,
        doc_type: DocumentType,
        input_data: dict,
        repo_id: str = "",
        current_user: dict = None,
        selected_document_ids: list[str] | None = None,
    ) -> dict:
        engine = "self_hosted" if (
            is_user_self_hosted(current_user) if current_user else settings.is_self_hosted
        ) else "self_hosted"
        selected = selected_document_ids or []
        data = await ai_client.request(
            "/internal/draft/generate",
            repo_id=repo_id,
            user_id=(current_user or {}).get("id", ""),
            engine=engine,
            input_data={
                "document_type": doc_type.value,
                "draft_input": input_data,
                "notebook_id": notebook_id,
                "selected_document_ids": selected,
                "documents": await ai_client.documents(repo_id, selected or None),
            },
        )
        return data["draft_data"]

    async def edit_draft_data(
        self,
        notebook_id: str,
        doc_type: DocumentType,
        draft_data: dict,
        input_data: dict,
        instruction: str,
        current_user: dict = None,
    ) -> tuple[dict, dict]:
        engine = "self_hosted" if (
            is_user_self_hosted(current_user) if current_user else settings.is_self_hosted
        ) else "self_hosted"
        data = await ai_client.request(
            "/internal/draft/edit",
            user_id=(current_user or {}).get("id", ""),
            engine=engine,
            input_data={
                "notebook_id": notebook_id,
                "document_type": doc_type.value,
                "draft_data": draft_data,
                "draft_input": input_data,
                "instruction": instruction,
            },
        )
        return data["draft_data"], data["input_data"]

    async def edit_exported_docx(self, source_path: str, instruction: str, output_path: str) -> int:
        # Legacy tasks have no structured draft. Preserve the file instead of corrupting it.
        shutil.copy2(source_path, output_path)
        return 0


drafting_service = DraftingService()
