"""Trích xuất dữ liệu có cấu trúc từ một văn bản hành chính đơn lẻ.

Khác với `summary_service` (map-reduce nhiều văn bản góp ý), đây là một lệnh
gọi LLM duy nhất trên nội dung một file, trả JSON theo đúng schema mà
`document_dataset_service` (BE) và `nd30_exporter` đã dùng cho response mock
trước đây — để FE/BE không cần đổi contract khi AI thật đi vào hoạt động.
"""

from __future__ import annotations

import json
import logging

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Giới hạn ký tự đưa vào 1 lần gọi để tránh vượt context window.
_MAX_CHARS = 12000

_SYSTEM_PROMPT = (
    "Bạn là chuyên viên hành chính trích xuất dữ liệu có cấu trúc từ văn bản "
    "hành chính tiếng Việt. Chỉ dựa vào nội dung được cung cấp, TUYỆT ĐỐI không "
    "bịa thông tin; trường nào không có trong văn bản thì để chuỗi rỗng hoặc "
    "mảng rỗng. Trả lời DUY NHẤT bằng một object JSON hợp lệ đúng khung yêu cầu, "
    "KHÔNG kèm giải thích, KHÔNG dùng rào ```; không suy nghĩ thành tiếng, không "
    "dùng thẻ <think>. /no_think"
)

_SKELETON = {
    "co_quan_chu_quan": "",
    "co_quan_ban_hanh": "",
    "so_ky_hieu": "",
    "dia_danh": "",
    "ngay_ban_hanh": "",
    "loai_van_ban": "",
    "trich_yeu": "",
    "noi_dung": ["..."],
    "nguoi_ky": "",
    "chuc_vu": "",
    "noi_nhan": ["..."],
    "bang_du_lieu": {
        "tieu_de": "",
        "headers": ["..."],
        "rows": [["..."]],
    },
}

_USER_TEMPLATE = """\
Trích dữ liệu từ VĂN BẢN dưới đây, trả JSON đúng khung:
{skeleton}

QUY TẮC:
- "co_quan_chu_quan": cơ quan cấp trên ban hành/quản lý (nếu có), ví dụ "ỦY BAN
  NHÂN DÂN TỈNH ...".
- "co_quan_ban_hanh": cơ quan/đơn vị trực tiếp ký/ban hành văn bản.
- "so_ky_hieu": số và ký hiệu văn bản, ví dụ "123/QĐ-UBND".
- "loai_van_ban": loại văn bản viết HOA, ví dụ "QUYẾT ĐỊNH", "KẾ HOẠCH", "CÔNG VĂN".
- "trich_yeu": trích yếu/tên văn bản (thường sau "Về việc ...").
- "noi_dung": mỗi phần tử là một đoạn/Điều/mục nội dung chính, GIỮ NGUYÊN thứ tự
  và văn phong gốc, không tóm tắt, không bịa thêm.
- "nguoi_ky", "chuc_vu": người ký và chức vụ ở phần ký tên, nếu có.
- "noi_nhan": danh sách nơi nhận, nếu có.
- "bang_du_lieu": nếu văn bản có MỘT bảng dữ liệu rõ ràng (ví dụ danh mục nhiệm
  vụ), trích tiêu đề bảng + headers + rows. Nếu KHÔNG có bảng nào, để headers=[]
  và rows=[].
- Chỉ xuất JSON, không thêm chữ nào khác.

VĂN BẢN:
{content}
"""

_DEFAULT_BODY_PROFILE = {
    "preserve_numbering": True,
    "font_size": 14,
    "indent": 1.25,
    "before": 6,
    "after": 6,
    "line": 1.15,
}

_DEFAULT_LAYOUT = {
    "header_widths_cm": [6.75, 9.92],
    "signature_widths_cm": [8.29, 8.63],
    "title_separator": True,
    "date_in_header": True,
    "national_font_size": 12,
    "left_header_line_length": 9,
    "right_header_line_length": 27,
}


class DatasetService:
    async def extract(self, markdown: str, filename: str = "") -> dict:
        content = (markdown or "").strip()
        if not content:
            raise ValueError("Không có nội dung để trích xuất dataset")
        if len(content) > _MAX_CHARS:
            content = content[:_MAX_CHARS] + "\n...(đã lược bớt)"

        user_prompt = _USER_TEMPLATE.format(
            skeleton=json.dumps(_SKELETON, ensure_ascii=False, indent=2),
            content=content,
        )
        data = await llm_service.chat_json(
            _SYSTEM_PROMPT, user_prompt, temperature=0.1, max_tokens=4096
        )
        if not isinstance(data, dict) or not data:
            raise ValueError("AI không trích xuất được dữ liệu từ văn bản")
        logger.info("Dataset extracted for %s: %d đoạn nội dung", filename, len(data.get("noi_dung") or []))
        return self._to_document_data(data)

    def _to_document_data(self, data: dict) -> dict:
        noi_dung = [str(item).strip() for item in (data.get("noi_dung") or []) if str(item).strip()]
        noi_nhan = [str(item).strip() for item in (data.get("noi_nhan") or []) if str(item).strip()]
        trich_yeu = str(data.get("trich_yeu") or "").strip()

        table = data.get("bang_du_lieu") or {}
        headers = [str(h).strip() for h in (table.get("headers") or []) if str(h).strip()]
        rows = [
            [str(cell).strip() if cell is not None else "" for cell in row]
            for row in (table.get("rows") or [])
            if isinstance(row, list)
        ]

        document_data = {
            "co_quan_chu_quan": str(data.get("co_quan_chu_quan") or "").strip(),
            "co_quan_ban_hanh": str(data.get("co_quan_ban_hanh") or "").strip(),
            "so_ky_hieu": str(data.get("so_ky_hieu") or "").strip(),
            "dia_danh": str(data.get("dia_danh") or "").strip(),
            "ngay_ban_hanh": str(data.get("ngay_ban_hanh") or "").strip(),
            "loai_van_ban": str(data.get("loai_van_ban") or "").strip() or "VĂN BẢN",
            "trich_yeu": trich_yeu,
            "trich_yeu_dong": [trich_yeu] if trich_yeu else [],
            "noi_dung": noi_dung,
            "thua_lenh": [],
            "chu_ky_dong": [],
            "chuc_vu": str(data.get("chuc_vu") or "").strip(),
            "nguoi_ky": str(data.get("nguoi_ky") or "").strip(),
            "noi_nhan": noi_nhan,
            "body_profile": dict(_DEFAULT_BODY_PROFILE),
            "layout": dict(_DEFAULT_LAYOUT),
            "phu_luc": [],
        }
        if headers:
            document_data["phu_luc"].append({
                "tieu_de": str(table.get("tieu_de") or "").strip() or "PHỤ LỤC",
                "noi_dung": [],
                "landscape": len(headers) > 4,
                "bang": [{"headers": headers, "rows": rows}],
            })
        return document_data


dataset_service = DatasetService()
