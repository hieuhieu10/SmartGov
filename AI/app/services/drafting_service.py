"""Drafting service for administrative documents under NĐ 30/2020/NĐ-CP.

The service uses the internal document scanner and agent pipeline.

Hỗ trợ 6 loại văn bản:
1. Công văn (cong_van)
2. Quyết định (quyet_dinh)
3. Kế hoạch (ke_hoach)
4. Thông báo (thong_bao)
5. Tờ trình (to_trinh)
6. Báo cáo (bao_cao)
"""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models import DocumentType
from app.agents.prompt_policy import (
    ADMIN_DRAFTING_PROCESS_RULES,
    ADMIN_DRAFTING_ROLE_PROMPT,
    CHATBOT_PROHIBITIONS,
)

logger = logging.getLogger(__name__)

# ─── Document Type Metadata ──────────────────────────────────────────

DOCUMENT_TYPE_INFO = {
    DocumentType.CONG_VAN: {
        "name": "Công văn",
        "description": "Văn bản dùng để trao đổi, giao dịch, đề nghị giữa các cơ quan, tổ chức",
        "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
        "optional_fields": ["co_quan_chu_quan", "noi_nhan", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"],
    },
    DocumentType.QUYET_DINH: {
        "name": "Quyết định",
        "description": "Quyết định cá biệt của cơ quan, tổ chức về một vấn đề cụ thể",
        "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
        "optional_fields": ["co_quan_chu_quan", "can_cu", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"],
    },
    DocumentType.KE_HOACH: {
        "name": "Kế hoạch",
        "description": "Kế hoạch triển khai công việc, hoạt động",
        "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
        "optional_fields": ["co_quan_chu_quan", "muc_dich", "yeu_cau", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"],
    },
    DocumentType.THONG_BAO: {
        "name": "Thông báo",
        "description": "Thông báo nội bộ hoặc bên ngoài về một sự kiện, quyết định, thay đổi",
        "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
        "optional_fields": ["co_quan_chu_quan", "noi_nhan", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"],
    },
    DocumentType.TO_TRINH: {
        "name": "Tờ trình",
        "description": "Văn bản đề xuất, trình bày vấn đề lên cấp trên để xin ý kiến hoặc phê duyệt",
        "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
        "optional_fields": ["co_quan_chu_quan", "noi_nhan", "ly_do", "kien_nghi", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"],
    },
    DocumentType.BAO_CAO: {
        "name": "Báo cáo",
        "description": "Báo cáo kết quả, tình hình, tiến độ công việc",
        "required_fields": ["co_quan_ban_hanh", "trich_yeu", "noi_dung_chinh"],
        "optional_fields": ["co_quan_chu_quan", "ky_bao_cao", "danh_gia", "kien_nghi", "nguoi_ky", "chuc_vu_nguoi_ky", "so_van_ban"],
    },
}


# ─── Prompt Templates ────────────────────────────────────────────────

def _build_prompt(doc_type: DocumentType, input_data: dict,
                  context: str = "", source_filter: str = "") -> str:
    """Build a prompt for drafting a specific document type.

    Args:
        doc_type: Type of document.
        input_data: User-provided input data.
        context: Retrieved context from the internal RAG pipeline.
    """

    type_name = DOCUMENT_TYPE_INFO[doc_type]["name"]
    trich_yeu = input_data.get("trich_yeu", "")
    noi_dung_chinh = input_data.get("noi_dung_chinh", "")

    # Context source instruction
    if context:
        source_instruction = f"""DỮ LIỆU THAM KHẢO TỪ KHO:
{context}

---

DỰA TRÊN DỮ LIỆU THAM KHẢO Ở TRÊN, hãy soạn nội dung {type_name} với thông tin sau:"""
    else:
        source_instruction = f"""DỰA TRÊN TÀI LIỆU NGUỒN trong sổ ghi chú này, hãy soạn nội dung {type_name} với thông tin sau:"""

    if source_filter:
        source_instruction += f"\n\n{source_filter}"

    base_prompt = f"""{ADMIN_DRAFTING_ROLE_PROMPT}

{ADMIN_DRAFTING_PROCESS_RULES}

{CHATBOT_PROHIBITIONS}

{source_instruction}
- Trích yếu: {trich_yeu}
- Yêu cầu nội dung: {noi_dung_chinh}
"""

    # Add type-specific instructions
    if doc_type == DocumentType.CONG_VAN:
        base_prompt += """
Trả về JSON với cấu trúc CHÍNH XÁC (CHỈ JSON thuần, KHÔNG markdown):
{
    "noi_dung": "Nội dung công văn",
    "de_nghi": "Phần đề nghị cuối công văn (nếu có, để rỗng nếu không)"
}

VÍ DỤ FORMAT ĐÚNG cho "noi_dung":
"1. Về công tác triển khai:\\nNội dung chi tiết mục 1.\\n2. Về nguồn lực:\\nNội dung chi tiết mục 2."
"""
    elif doc_type == DocumentType.QUYET_DINH:
        can_cu = input_data.get("can_cu", "")
        base_prompt += f"""
Căn cứ bổ sung (nếu có): {can_cu}

Trả về JSON:
{{
    "can_cu": ["Căn cứ Luật/Nghị định 1;", "Căn cứ 2;"],
    "dieu_khoan": [
        {{"so_dieu": "Điều 1", "noi_dung": "Nội dung điều 1"}},
        {{"so_dieu": "Điều 2", "noi_dung": "Nội dung điều 2"}},
        {{"so_dieu": "Điều 3", "noi_dung": "Quyết định này có hiệu lực kể từ ngày ký./."}}
    ]
}}
"""
    elif doc_type == DocumentType.KE_HOACH:
        muc_dich = input_data.get("muc_dich", "")
        yeu_cau = input_data.get("yeu_cau", "")
        base_prompt += f"""
Mục đích (nếu có): {muc_dich}
Yêu cầu (nếu có): {yeu_cau}

Trả về JSON (KHÔNG viết tiêu đề section — hệ thống tự thêm "I. MỤC ĐÍCH, YÊU CẦU", "II. NỘI DUNG THỰC HIỆN", "III. KINH PHÍ", "IV. TỔ CHỨC THỰC HIỆN"). TUYỆT ĐỐI KHÔNG để rỗng các trường nội dung:
{{
    "phan_mo_dau": "Căn cứ ban hành và câu dẫn vào kế hoạch",
    "muc_dich_yeu_cau": "Chỉ viết nội dung mục I, bắt đầu bằng 1. Mục đích:...",
    "noi_dung_thuc_hien": "Chỉ viết nội dung mục II; mỗi nhiệm vụ có tên nhiệm vụ, nội dung, cơ quan chủ trì, cơ quan phối hợp và thời gian thực hiện",
    "kinh_phi": "Chỉ viết nội dung mục III về nguồn kinh phí, quản lý và thanh quyết toán",
    "to_chuc_thuc_hien": "Chỉ viết nội dung mục IV về phân công trách nhiệm, bắt đầu bằng 1. Đơn vị/chức danh:..."
}}

VÍ DỤ FORMAT ĐÚNG cho "muc_dich_yeu_cau":
"1. Mục đích: Nhằm hoàn thành các chỉ tiêu chuyển đổi số.\\nĐảm bảo triển khai đồng bộ trên 03 trụ cột.\\n2. Yêu cầu: Công tác chuyển đổi số phải thực chất, hiệu quả.\\nGắn kết chặt chẽ với cải cách hành chính."

VÍ DỤ FORMAT ĐÚNG cho "noi_dung_thuc_hien":
"1. Tăng cường lãnh đạo, chỉ đạo: Quán triệt các chủ trương...\\n2. Phát triển hạ tầng số: Phối hợp triển khai mạng...\\n3. Phát triển dữ liệu số: Thực hiện số hóa..."
"""
    elif doc_type == DocumentType.THONG_BAO:
        base_prompt += """
Trả về JSON:
{
    "noi_dung": "Nội dung thông báo"
}

VÍ DỤ FORMAT ĐÚNG cho "noi_dung":
"1. Nội dung chính:\\nChi tiết nội dung mục 1.\\n2. Yêu cầu thực hiện:\\nChi tiết nội dung mục 2."
"""
    elif doc_type == DocumentType.TO_TRINH:
        ly_do = input_data.get("ly_do", "")
        kien_nghi = input_data.get("kien_nghi", "")
        base_prompt += f"""
Lý do trình (nếu có): {ly_do}
Kiến nghị (nếu có): {kien_nghi}

Trả về JSON (KHÔNG viết tiêu đề section — hệ thống tự thêm):
{{
    "su_can_thiet": "Lý do, cơ sở pháp lý, thực tiễn",
    "noi_dung_de_xuat": "Chi tiết đề xuất",
    "kien_nghi": "Kiến nghị cụ thể gửi cấp trên"
}}
"""
    elif doc_type == DocumentType.BAO_CAO:
        ky_bao_cao = input_data.get("ky_bao_cao", "")
        base_prompt += f"""
Kỳ báo cáo (nếu có): {ky_bao_cao}

Trả về JSON (KHÔNG viết tiêu đề section — hệ thống tự thêm):
{{
    "tinh_hinh_chung": "Mô tả bối cảnh, tình hình",
    "ket_qua": "Kết quả đạt được, có số liệu",
    "han_che": "Các vấn đề tồn tại",
    "phuong_huong": "Giải pháp, đề xuất"
}}
"""

    base_prompt += r"""
QUY TẮC BẮT BUỘC:
1. Văn phong hành chính nhà nước Việt Nam, trang trọng, chính xác, ngắn gọn, rõ việc.
2. CHỈ trả về JSON thuần — KHÔNG markdown, KHÔNG giải thích
3. Nội dung phải DỰA TRÊN TÀI LIỆU NGUỒN và thông tin người dùng; KHÔNG đưa `[Nguồn: ...]`, `Điểm: ...`, tên file nguồn, heading nguồn hoặc metadata nội bộ vào JSON.
4. Viết đủ ý nhưng thực tế, không lan man, không văn phong AI/chung chung, không viết tắt tùy tiện.
5. Sử dụng đúng thuật ngữ chuyên ngành từ tài liệu nguồn
6. Đúng cấp hành chính, đúng thẩm quyền cơ quan ban hành. Nếu cơ quan là cấp xã/huyện, chỉ viết nhiệm vụ triển khai, phối hợp, rà soát, tuyên truyền, kiểm tra, tổng hợp, báo cáo, đề xuất cấp có thẩm quyền; không viết nội dung phê duyệt/ban hành chính sách vượt thẩm quyền.
7. Logic nội dung, thời gian và cơ quan phối hợp phải rõ; không lặp ý, không dùng câu khẩu hiệu.

QUY TẮC TRÌNH BÀY (RẤT QUAN TRỌNG):
8. TUYỆT ĐỐI KHÔNG viết lại tiêu đề section (VD: "I. MỤC ĐÍCH, YÊU CẦU" hoặc "Phần I...") — hệ thống đã tự thêm tiêu đề.
9. Mỗi mục đánh số PHẢI viết cùng dòng với nội dung: "1. Mục đích: Nội dung..." — KHÔNG tách số và nội dung ra 2 dòng.
10. PHÂN CẤP ĐÚNG: Sau các phần lớn, bắt đầu bằng **1., 2., 3...**. Tuyệt đối KHÔNG sử dụng chữ số La Mã (I, II...) cho các mục này.
11. Dùng ký tự \n để XUỐNG DÒNG giữa các mục/đoạn khác nhau.
12. KHÔNG viết tất cả nội dung trên 1 dòng duy nhất — phải tách đoạn hợp lý.
"""

    return base_prompt



class DraftingService:
    """Service to draft administrative documents with dual-engine support."""

    def get_document_types(self) -> list[dict]:
        """Get info about all supported document types."""
        result = []
        for dt, info in DOCUMENT_TYPE_INFO.items():
            result.append({
                "type_code": dt.value,
                "name": info["name"],
                "description": info["description"],
                "required_fields": info["required_fields"],
                "optional_fields": info["optional_fields"],
            })
        return result

    def get_document_types_by_code(self) -> dict[str, str]:
        """Map document type code to Vietnamese display name."""
        return {dt.value: info["name"] for dt, info in DOCUMENT_TYPE_INFO.items()}

    def validate_input(self, doc_type: DocumentType, input_data: dict) -> list[str]:
        """Validate required fields for a document type. Returns list of missing fields."""
        info = DOCUMENT_TYPE_INFO[doc_type]
        missing = []
        for field in info["required_fields"]:
            if field not in input_data or not input_data[field]:
                missing.append(field)
        return missing

    def infer_document_type(self, input_data: dict) -> DocumentType:
        """Infer the administrative document type from user-provided text."""
        explicit = (input_data.get("loai_van_ban") or input_data.get("document_type") or "").lower()
        haystack = " ".join(
            str(input_data.get(key, ""))
            for key in ("trich_yeu", "noi_dung_chinh", "muc_dich", "ly_do", "kien_nghi", "can_cu", "ky_bao_cao")
        ).lower()
        text = f"{explicit} {haystack}"

        rules: list[tuple[DocumentType, list[str]]] = [
            (DocumentType.QUYET_DINH, ["quyết định", "quyet dinh", "ban hành quy chế", "phê duyệt", "thành lập", "bổ nhiệm"]),
            (DocumentType.TO_TRINH, ["tờ trình", "to trinh", "trình phê duyệt", "trình ban hành", "đề nghị phê duyệt", "xin chủ trương"]),
            (DocumentType.KE_HOACH, ["kế hoạch", "ke hoach", "triển khai", "tổ chức thực hiện", "tuyên truyền", "tập huấn", "chuyển đổi số"]),
            (DocumentType.BAO_CAO, ["báo cáo", "bao cao", "kết quả", "tình hình", "đánh giá", "sơ kết", "tổng kết"]),
            (DocumentType.THONG_BAO, ["thông báo", "thong bao", "thời gian", "lịch", "mời họp", "triệu tập"]),
            (DocumentType.CONG_VAN, ["công văn", "cong van", "về việc", "đề nghị", "phối hợp", "hướng dẫn"]),
        ]
        for doc_type, keywords in rules:
            if any(keyword in text for keyword in keywords):
                return doc_type
        return DocumentType.CONG_VAN

    async def draft_document(self, _source_id: str, doc_type: DocumentType | None,
                             input_data: dict, repo_id: str = "",
                             current_user: dict = None,
                             selected_document_ids: list[str] | None = None) -> dict:
        """
        Draft a document using the internal AI pipeline.

        Args:
            doc_type: Type of document to draft.
            input_data: User-provided input data.
            repo_id: Repository ID (used in self-hosted mode for retrieval).
            current_user: Current user context (kept for API compatibility).

        Returns:
            Merged dict of AI-generated content + input_data.
        """
        if doc_type is None:
            raise ValueError("Vui lòng chọn loại văn bản trước khi soạn.")
        return await self._draft_self_hosted(
            repo_id, doc_type, input_data,
            selected_document_ids=selected_document_ids,
        )

    async def edit_draft_data(self, _source_id: str, doc_type: DocumentType,
                              draft_data: dict, input_data: dict,
                              instruction: str, current_user: dict = None) -> tuple[dict, dict]:
        """
        Edit the full structured draft, then let the caller export Word again.

        Returns:
            (edited_draft_data, edited_input_data)
        """
        # Editing must be stable and must review the whole exported structure.
        # Server 1 can return empty responses for full-document JSON edits, so edits always use Server 2.
        logger.info("[DraftEdit] Using Server 2 for full-document edit; Server 1 is skipped")
        return await self._edit_draft_data_self_hosted(
            doc_type, draft_data, input_data, instruction
        )

    async def _edit_draft_data_self_hosted(self, doc_type: DocumentType,
                                           draft_data: dict, input_data: dict,
                                           instruction: str) -> tuple[dict, dict]:
        """Edit a complete structured draft using the configured LLM."""
        from app.services.llm_service import llm_service

        system_prompt = """Bạn là biên tập viên văn bản hành chính nhà nước Việt Nam.

Nhiệm vụ: chỉnh sửa bản thảo đã có theo đúng yêu cầu người dùng. Không soạn văn bản mới từ đầu nếu không cần thiết.

Trả về JSON duy nhất:
{
  "draft_data": { ... toàn bộ JSON nội dung đã chỉnh ... },
  "input_data_updates": { ... các trường metadata cần đổi, hoặc {} ... }
}

Quy tắc:
- Giữ nguyên cấu trúc JSON đang có, chỉ thay nội dung cần chỉnh.
- Sau khi chỉnh sửa phải duyệt lại TOÀN BỘ văn bản để bảo đảm bố cục, logic, số thứ tự mục/phần liên tục và không còn phần bị bỏ trống.
- Nếu xóa một phần/mục thì phải sắp xếp lại các phần/mục còn lại, không để nhảy số như I, II, IV hoặc 1, 2, 4.
- Nếu xóa/thêm/sửa bất kỳ phần hoặc mục nào, phải cập nhật đúng trường JSON tương ứng với phần/mục đó; không chuyển nội dung đã xóa sang trường khác.
- Nếu người dùng yêu cầu đổi trích yếu, cơ quan, người ký, nơi nhận hoặc metadata khác thì đưa trường đó vào input_data_updates.
- Không thêm markdown, không giải thích."""
        user_prompt = self._build_edit_user_prompt(doc_type, draft_data, input_data, instruction)
        result = await llm_service.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=8000,
        )
        return self._normalize_edit_payload(result, draft_data, input_data)

    def _build_edit_prompt(self, doc_type: DocumentType, draft_data: dict,
                           input_data: dict, instruction: str) -> str:
        return f"""{ADMIN_DRAFTING_ROLE_PROMPT}

Bạn đang chỉnh sửa một văn bản hành chính đã được hệ thống soạn và xuất Word trước đó.
Hãy dựa trên TÀI LIỆU NGUỒN trong sổ ghi chú này, TOÀN BỘ JSON VĂN BẢN HIỆN TẠI và yêu cầu chỉnh sửa để trả về bản JSON đã chỉnh.

{self._build_edit_user_prompt(doc_type, draft_data, input_data, instruction)}

Trả về JSON duy nhất, đúng cấu trúc:
{{
  "draft_data": {{ ... toàn bộ JSON nội dung đã chỉnh ... }},
  "input_data_updates": {{ ... các trường metadata cần đổi, hoặc {{}} ... }}
}}

QUY TẮC BẮT BUỘC:
1. Chỉ chỉnh theo yêu cầu người dùng, giữ nguyên các phần không liên quan.
2. Nếu yêu cầu cần đối chiếu tài liệu nguồn, chỉ dùng thông tin có trong sổ ghi chú này.
3. draft_data phải là TOÀN BỘ nội dung sau chỉnh sửa, không phải patch/diff.
4. Nếu người dùng yêu cầu đổi trích yếu, cơ quan, người ký, nơi nhận hoặc metadata khác thì đưa trường đó vào input_data_updates.
5. Không thêm markdown, không giải thích, không đưa trích dẫn hoặc metadata nguồn vào nội dung xuất Word.
"""

    def _build_edit_user_prompt(self, doc_type: DocumentType, draft_data: dict,
                                input_data: dict, instruction: str) -> str:
        type_name = DOCUMENT_TYPE_INFO.get(doc_type, {}).get("name", doc_type.value)
        return f"""LOẠI VĂN BẢN: {type_name} ({doc_type.value})

YÊU CẦU CHỈNH SỬA:
{instruction}

INPUT/METADATA HIỆN TẠI:
{json.dumps(input_data or {}, ensure_ascii=False, indent=2)}

TOÀN BỘ JSON NỘI DUNG VĂN BẢN HIỆN TẠI:
{json.dumps(draft_data or {}, ensure_ascii=False, indent=2)}

YÊU CẦU RÀ SOÁT SAU CHỈNH SỬA:
- Trả về toàn bộ JSON sau chỉnh sửa, không trả diff/patch.
- Đọc lại toàn bộ nội dung để bảo đảm các phần/mục còn lại nối tiếp đúng thứ tự.
- Nếu xóa một phần trong văn bản, các phần phía sau phải được sắp xếp lại khi xuất Word.
- Khi người dùng yêu cầu xóa/thêm/sửa phần hoặc mục nào, hãy xác định trường JSON tương ứng theo nội dung hiện tại và cập nhật đúng trường đó; không hardcode theo ví dụ cụ thể.
"""

    def _parse_edit_response(self, raw_response: str, current_draft_data: dict,
                             current_input_data: dict) -> tuple[dict, dict]:
        json_str = self._extract_json(raw_response)
        if not json_str:
            raise ValueError("AI không trả về JSON chỉnh sửa hợp lệ.")
        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError("AI trả về JSON chỉnh sửa không hợp lệ.") from exc
        return self._normalize_edit_payload(payload, current_draft_data, current_input_data)

    def _normalize_edit_payload(self, payload: dict, current_draft_data: dict,
                                current_input_data: dict) -> tuple[dict, dict]:
        if not isinstance(payload, dict):
            raise ValueError("AI không trả về dữ liệu chỉnh sửa hợp lệ.")

        edited_draft = payload.get("draft_data")
        if not isinstance(edited_draft, dict):
            # Backward-compatible: allow the model to return the draft JSON directly.
            edited_draft = {
                key: value
                for key, value in payload.items()
                if key != "input_data_updates"
            }

        input_updates = payload.get("input_data_updates", {})
        if not isinstance(input_updates, dict):
            input_updates = {}

        edited_draft = self._sanitize_draft_data(edited_draft)
        edited_draft = self._remove_citations_from_dict(edited_draft)
        edited_input = {**(current_input_data or {}), **input_updates}
        edited_input = {
            key: value
            for key, value in edited_input.items()
            if value is not None
        }

        if not edited_draft:
            raise ValueError("AI không trả về nội dung văn bản sau chỉnh sửa.")
        return edited_draft, edited_input

    def _text_size(self, value) -> int:
        if isinstance(value, str):
            return len(value.strip())
        if isinstance(value, list):
            return sum(self._text_size(item) for item in value)
        if isinstance(value, dict):
            return sum(self._text_size(item) for item in value.values())
        return 0

    def _is_insufficient_draft(self, doc_type: DocumentType, draft_data: dict, input_data: dict | None = None) -> bool:
        if not isinstance(draft_data, dict) or not draft_data:
            return True

        input_data = input_data or {}
        if doc_type == DocumentType.KE_HOACH:
            content_keys = [
                "custom_sections",
                "muc_dich_yeu_cau",
                "noi_dung_thuc_hien",
                "noi_dung_ke_hoach",
                "noi_dung",
                "kinh_phi",
                "to_chuc_thuc_hien",
                "phu_luc_nhiem_vu",
            ]
            content_size = sum(self._text_size(draft_data.get(key)) for key in content_keys)
            main_size = max(
                self._text_size(draft_data.get("custom_sections")),
                self._text_size(draft_data.get("noi_dung_thuc_hien")),
                self._text_size(draft_data.get("noi_dung_ke_hoach")),
                self._text_size(draft_data.get("noi_dung")),
            )
            user_content = str(input_data.get("noi_dung_chinh") or "").strip()
            only_echoed_user_request = (
                main_size > 0
                and self._text_size(draft_data.get("noi_dung")) <= len(user_content) + 20
                and (draft_data.get("noi_dung") or "").strip() == user_content
            )
            return content_size < 180 or main_size < 120 or only_echoed_user_request

        content_size = self._text_size(draft_data)
        return content_size < 80

    def validate_draft_quality(self, doc_type: DocumentType, draft_data: dict, input_data: dict | None = None):
        if self._is_insufficient_draft(doc_type, draft_data, input_data):
            raise ValueError(
                "Nội dung soạn thảo chưa đủ để xuất văn bản. Hệ thống không xuất file rỗng; vui lòng kiểm tra tài liệu nguồn hoặc thử lại."
            )

    async def _build_source_filter(self, selected_document_ids: list[str]) -> str:
        if not selected_document_ids:
            return ""
        from app.services.document_scanner import get_request_documents
        selected = set(selected_document_ids[:30])
        names = [
            doc.get("filename", "")
            for doc in get_request_documents()
            if str(doc.get("id")) in selected and doc.get("filename")
        ]
        if not names:
            return ""
        lines = "\n".join(f"- {name}" for name in names)
        return (
            "GIỚI HẠN TÀI LIỆU NGUỒN: Người dùng đã chọn tài liệu cụ thể. "
            "Chỉ sử dụng thông tin từ các tài liệu sau; bỏ qua tài liệu khác trong kho/sổ ghi chú:\n"
            f"{lines}"
        )

    async def _draft_self_hosted(self, repo_id: str, doc_type: DocumentType,
                                 input_data: dict,
                                 selected_document_ids: list[str] | None = None) -> dict:
        """
        Draft using self-hosted LangGraph pipeline:
          TemplateExtractor → Planner → Researcher (DocumentScanner) → Writer → Reviewer
        """
        from app.agents.graph import run_agent_graph

        trich_yeu = input_data.get("trich_yeu", "")
        noi_dung = input_data.get("noi_dung_chinh", "")
        user_request = noi_dung or trich_yeu

        doc_type_label = DOCUMENT_TYPE_INFO.get(doc_type, {}).get("name", "Văn bản")

        # Run the agent pipeline
        result = await run_agent_graph(
            user_request=user_request,
            doc_type=doc_type.value,
            doc_type_label=doc_type_label,
            input_data=input_data,
            warehouse_ids=[repo_id],
            selected_document_ids=selected_document_ids or [],
            trich_yeu=trich_yeu,
            max_iterations=2,
        )

        # Extract draft data from agent result
        draft_data = result.get("draft_data", {})
        if not draft_data:
            draft_data = self._parse_draft_response(result.get("draft", ""))
        draft_data = self._sanitize_draft_data(draft_data)

        # Final gate before exporting Word: deterministic checks + LLM review.
        from app.agents.final_reviewer import (
            final_review_document,
            final_fix_draft,
            final_grounding_edit_draft,
            format_final_review_errors,
            has_critical_final_issues,
            has_unrecoverable_schema_issues,
        )

        final_review = await final_review_document(
            doc_type=doc_type.value,
            doc_type_label=doc_type_label,
            draft_data=draft_data,
            input_data=input_data,
            agent_result=result,
        )
        if not final_review.get("pass"):
            issues = final_review.get("issues", [])
            grounded_draft_data = await final_grounding_edit_draft(
                doc_type=doc_type.value,
                doc_type_label=doc_type_label,
                draft_data=draft_data,
                input_data=input_data,
                issues=issues,
                agent_result=result,
            )
            if grounded_draft_data:
                grounded_draft_data = self._sanitize_draft_data(grounded_draft_data)
                grounded_review = await final_review_document(
                    doc_type=doc_type.value,
                    doc_type_label=doc_type_label,
                    draft_data=grounded_draft_data,
                    input_data=input_data,
                    agent_result=result,
                )
                if grounded_review.get("pass"):
                    draft_data = grounded_draft_data
                    final_review = grounded_review
                else:
                    logger.warning(
                        "[Self-Hosted/Agent] Grounding cleanup did not pass final "
                        "review; keeping the original draft data."
                    )

            if not final_review.get("pass") and not has_critical_final_issues(final_review.get("issues", [])):
                fixed_draft_data = await final_fix_draft(
                    doc_type=doc_type.value,
                    doc_type_label=doc_type_label,
                    draft_data=draft_data,
                    input_data=input_data,
                    issues=final_review.get("issues", []),
                )
                if fixed_draft_data:
                    fixed_draft_data = self._sanitize_draft_data(fixed_draft_data)
                    fixed_review = await final_review_document(
                        doc_type=doc_type.value,
                        doc_type_label=doc_type_label,
                        draft_data=fixed_draft_data,
                        input_data=input_data,
                        agent_result=result,
                    )
                    if fixed_review.get("pass"):
                        draft_data = fixed_draft_data
                        final_review = fixed_review

            if not final_review.get("pass"):
                raise ValueError(format_final_review_errors(final_review))

        # Strip citations from the final draft data
        draft_data = self._remove_citations_from_dict(draft_data)

        logger.info(
            f"[Self-Hosted/Agent] Draft complete: "
            f"iterations={result.get('iteration', 0)}, "
            f"pass={result.get('review_pass', 'N/A')}, "
            f"fields={len(draft_data)}"
        )

        merged = {**draft_data, **input_data}
        merged["_raw_response"] = result.get("draft", "")
        merged["document_type"] = doc_type.value
        merged["_agent_iterations"] = result.get("iteration", 0)
        merged["_review_pass"] = result.get("review_pass", False)
        merged["_final_review_pass"] = final_review.get("pass", False)
        merged["_final_review_summary"] = final_review.get("summary", "")
        return merged

    def _parse_draft_response(self, raw_response: str) -> dict:
        """Parse AI's JSON response for drafting."""
        json_str = self._extract_json(raw_response)
        if json_str:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed: {e}")

        # Fallback: return raw text as content
        return {"noi_dung": raw_response}

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text that may contain markdown wrapping."""
        text_stripped = text.strip()
        if text_stripped.startswith("{"):
            return text_stripped

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                candidate = match.group(1).strip()
                if candidate.startswith("{"):
                    return candidate

        match = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return None

    def _remove_citations_from_dict(self, data: dict) -> dict:
        """Recursively remove [Nguồn: ...] citations from all strings in a dict."""
        cleaned = {}
        for k, v in data.items():
            if isinstance(v, str):
                cleaned[k] = self._remove_citations_from_text(v)
            elif isinstance(v, list):
                cleaned_list = []
                for item in v:
                    if isinstance(item, str):
                        cleaned_list.append(self._remove_citations_from_text(item))
                    elif isinstance(item, dict):
                        cleaned_list.append(self._remove_citations_from_dict(item))
                    else:
                        cleaned_list.append(item)
                cleaned[k] = cleaned_list
            elif isinstance(v, dict):
                cleaned[k] = self._remove_citations_from_dict(v)
            else:
                cleaned[k] = v
        return cleaned

    def _sanitize_draft_data(self, data: dict) -> dict:
        """Remove filler/insufficient-data sentences before final review/export."""
        if not isinstance(data, dict):
            return data

        cleaned = {}
        for key, value in data.items():
            cleaned[key] = self._sanitize_value(value)
        return cleaned

    def _sanitize_value(self, value):
        if isinstance(value, str):
            return self._sanitize_text(value)
        if isinstance(value, list):
            result = []
            for item in value:
                cleaned = self._sanitize_value(item)
                if cleaned not in ("", None, [], {}):
                    result.append(cleaned)
            return result
        if isinstance(value, dict):
            return {
                key: cleaned
                for key, item in value.items()
                if (cleaned := self._sanitize_value(item)) not in ("", None, [], {})
            }
        return value

    def _sanitize_text(self, text: str) -> str:
        """Remove sentences/lines that say data is missing instead of drafting content."""
        blocked_patterns = [
            r"không\s+có\s+thông\s+tin",
            r"không\s+tìm\s+thấy\s+dữ\s+liệu",
            r"dữ\s+liệu\s+không\s+đề\s+cập",
            r"chưa\s+rõ\s+thông\s+tin",
            r"không\s+đủ\s+thông\s+tin",
            r"tôi\s+không\s+thể",
        ]
        blocked = re.compile("|".join(blocked_patterns), re.IGNORECASE)

        cleaned_lines = []
        for line in (text or "").splitlines():
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append(line)
                continue
            if blocked.search(stripped):
                continue
            if re.match(r"(?i)^\s*(số|ngày|cơ\s*quan\s*ban\s*hành)\s*:", stripped):
                continue
            if re.match(r"(?i)^\s*kế\s*hoạch\b", stripped):
                continue
            stripped = re.sub(r"(?i)^\s*căn\s*cứ\s*:\s*", "Căn cứ ", stripped)
            cleaned_lines.append(stripped)

        cleaned = "\n".join(cleaned_lines)
        cleaned = re.sub(r"\s*\[Nguồn:[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*\[\s*Điểm\s*:[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*\|\s*Điểm\s*:\s*[0-9.]+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(?im)^\s*(?:\d+[\.\)]\s*)?phần\s+mở\s+đầu\s*:\s*", "", cleaned)
        cleaned = re.sub(r"(?m)^\s*(?:I|II|III|IV|V|VI)\.\s+", "", cleaned)
        cleaned = re.sub(r"\*\*", "", cleaned)
        cleaned = re.sub(r"(?i)\b([A-Za-zÀ-ỹ]+)\s*,\s*\1\b", r"\1", cleaned)
        cleaned = re.sub(r"(?i)\b([A-Za-zÀ-ỹ]+\s+[A-Za-zÀ-ỹ]+)\s*,\s*\1\b", r"\1", cleaned)
        cleaned = self._remove_truncated_tail(cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned

    def _remove_truncated_tail(self, text: str) -> str:
        """Drop obvious truncated trailing fragments left by a cut-off LLM response."""
        lines = (text or "").splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return ""

        last = lines[-1].strip()
        if re.search(r"[.!?。:;…]$", last):
            return "\n".join(lines)

        words = last.split()
        if len(last) <= 24 and (len(words) <= 3 or (words and len(words[-1]) <= 2)):
            lines.pop()
        elif words and len(words[-1]) <= 2:
            lines[-1] = " ".join(words[:-1]).rstrip(" ,;:-")
        return "\n".join(lines)

    def _remove_citations_from_text(self, text: str) -> str:
        """Remove [Nguồn: ...] patterns from text."""
        text = re.sub(r'\s*\[Nguồn:.*?\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r"\s*\[\s*Điểm\s*:[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*\|\s*Điểm\s*:\s*[0-9.]+", "", text, flags=re.IGNORECASE)
        return text

    async def edit_exported_docx(self, source_path: str, instruction: str, output_path: str) -> int:
        """Edit content in an existing exported DOCX without running a new draft pipeline."""
        from docx import Document
        from app.services.llm_service import llm_service

        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError("Không tìm thấy file Word gốc để chỉnh sửa.")

        doc = Document(str(src))
        blocks = _collect_docx_text_blocks(doc)
        if not blocks:
            raise ValueError("File Word không có nội dung văn bản để chỉnh sửa.")

        compact_blocks = [
            {"id": block["id"], "text": block["text"][:1200]}
            for block in blocks
            if block["text"].strip()
        ][:260]
        system_prompt = """Bạn là biên tập viên chỉnh sửa file Word hành chính.

Nhiệm vụ: dựa trên yêu cầu người dùng, chỉ chỉnh các đoạn/cell cần sửa trong file Word đã xuất. Không soạn văn bản mới, không đổi cấu trúc nếu người dùng không yêu cầu.

Trả về JSON duy nhất:
{
  "edits": [
    {"block_id": 1, "new_text": "Nội dung thay thế hoàn chỉnh cho block đó"}
  ]
}

Quy tắc:
- Chỉ dùng block_id có trong danh sách.
- new_text là toàn bộ nội dung mới của block, không phải ghi chú.
- Giữ nguyên số mục, tên cơ quan, thể thức hành chính nếu không có yêu cầu đổi.
- Không thêm markdown, không giải thích."""
        user_prompt = f"""YÊU CẦU CHỈNH SỬA:
{instruction}

DANH SÁCH BLOCK TRONG FILE WORD:
{json.dumps(compact_blocks, ensure_ascii=False, indent=2)}
"""
        result = await llm_service.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=5000,
        )

        edits = result.get("edits", []) if isinstance(result, dict) else []
        edits_by_id = {
            int(edit["block_id"]): str(edit.get("new_text", "")).strip()
            for edit in edits
            if isinstance(edit, dict)
            and str(edit.get("block_id", "")).isdigit()
            and str(edit.get("new_text", "")).strip()
        }
        if not edits_by_id:
            raise ValueError("AI không xác định được phần cần chỉnh trong file Word. Vui lòng mô tả rõ mục/đoạn cần sửa.")

        changed = 0
        for block in blocks:
            new_text = edits_by_id.get(block["id"])
            if new_text is None or new_text == block["text"]:
                continue
            _set_paragraph_text(block["paragraph"], new_text)
            changed += 1

        if changed == 0:
            raise ValueError("Không có nội dung nào được thay đổi trong file Word.")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
        doc.save(str(out))
        return changed


def _collect_docx_text_blocks(doc) -> list[dict]:
    blocks = []
    block_id = 1
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            blocks.append({"id": block_id, "text": text, "paragraph": p})
            block_id += 1
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    text = (p.text or "").strip()
                    if text:
                        blocks.append({"id": block_id, "text": text, "paragraph": p})
                        block_id += 1
    return blocks


def _set_paragraph_text(paragraph, text: str):
    style = paragraph.style
    alignment = paragraph.alignment
    first_line_indent = paragraph.paragraph_format.first_line_indent
    left_indent = paragraph.paragraph_format.left_indent
    space_before = paragraph.paragraph_format.space_before
    space_after = paragraph.paragraph_format.space_after
    line_spacing = paragraph.paragraph_format.line_spacing
    template_run = paragraph.runs[0] if paragraph.runs else None

    paragraph.clear()
    paragraph.style = style
    paragraph.alignment = alignment
    paragraph.paragraph_format.first_line_indent = first_line_indent
    paragraph.paragraph_format.left_indent = left_indent
    paragraph.paragraph_format.space_before = space_before
    paragraph.paragraph_format.space_after = space_after
    paragraph.paragraph_format.line_spacing = line_spacing

    run = paragraph.add_run(text)
    if template_run is not None:
        run.bold = template_run.bold
        run.italic = template_run.italic
        run.underline = template_run.underline
        run.font.name = template_run.font.name
        run.font.size = template_run.font.size


# Singleton
drafting_service = DraftingService()
